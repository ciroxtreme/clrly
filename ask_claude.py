import os
import sys
import json
import time
import urllib.request
import urllib.parse
from playwright.sync_api import sync_playwright

CLAUDE_COOKIES_JSON = os.environ.get("CLAUDE_COOKIES_JSON")
CLAUDE_ORG_ID = os.environ.get("CLAUDE_ORG_ID")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
PROMPT = sys.argv[1] if len(sys.argv) > 1 else "Halo Claude, apakah sesi ini aktif?"

def send_telegram_msg(text: str):
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        print(f"[TG] {text}")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text
    }).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"})
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"[TG Error] {e}")

def main():
    if not CLAUDE_COOKIES_JSON:
        print("Error: CLAUDE_COOKIES_JSON not set!")
        sys.exit(1)

    cookies_dict = json.loads(CLAUDE_COOKIES_JSON)
    playwright_cookies = []
    for k, v in cookies_dict.items():
        clean_k = k.strip()
        clean_v = str(v).strip()
        if not clean_k or not clean_v or clean_k.startswith("q=") or clean_k.startswith("v="):
            continue
        
        # Format cookie Playwright yang 100% valid:
        # Gunakan 'domain' dan 'path' eksplisit untuk semua cookie.
        # Khusus prefix __Host-, domain tidak boleh diawali titik (tidak boleh .claude.ai melainkan claude.ai) dan harus secure=True
        if clean_k.startswith("__Host-"):
            c_obj = {
                "name": clean_k,
                "value": clean_v,
                "domain": "claude.ai",
                "path": "/",
                "secure": True,
            }
        else:
            c_obj = {
                "name": clean_k,
                "value": clean_v,
                "domain": ".claude.ai",
                "path": "/",
            }
        playwright_cookies.append(c_obj)

    print(f"🚀 Menyiapkan browser dengan {len(playwright_cookies)} cookies...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 15; Infinix X6880 Build/AP3A.240905.015.A2; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/157.0.8103.38 Mobile Safari/537.36",
            viewport={"width": 393, "height": 851},
            is_mobile=True,
            has_touch=True,
            locale="id-ID",
            timezone_id="Asia/Jakarta",
        )
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        
        # Tambahkan cookies satu per satu agar jika ada 1 cookie minor yang ditolak, tidak menggagalkan seluruh proses
        added_count = 0
        for c in playwright_cookies:
            try:
                context.add_cookies([c])
                added_count += 1
            except Exception as e:
                print(f"Peringatan cookie {c.get('name')}: {e}")
                
        print(f"✅ Berhasil menginjeksi {added_count}/{len(playwright_cookies)} cookies ke sesi browser.")
        page = context.new_page()

        print("1. Membuka https://claude.ai/new...")
        page.goto("https://claude.ai/new", wait_until="networkidle", timeout=60000)
        time.sleep(5)

        # Cek apakah lolos masuk ke chat room
        page_title = page.title()
        print(f"Title: {page_title}")
        print(f"Current URL: {page.url}")
        
        # Cari input chat Claude (contenteditable atau textarea atau p)
        input_selectors = [
            "div[contenteditable='true']",
            "fieldset div[contenteditable='true']",
            "div.ProseMirror",
            "textarea[placeholder*='Reply' i]",
            "textarea"
        ]
        
        input_box = None
        for sel in input_selectors:
            loc = page.locator(sel).first
            try:
                if loc.is_visible(timeout=3000):
                    input_box = loc
                    print(f"Ditemukan input element dengan selector: {sel}")
                    break
            except Exception:
                continue

        if input_box:
            print(f"✅ SESI CLAUDE AKTIF & TERVERIFIKASI! Mengetik prompt: '{PROMPT}'...")
            input_box.click()
            try:
                input_box.fill(PROMPT)
            except Exception:
                page.keyboard.type(PROMPT)
            time.sleep(1)
            
            # Cari tombol kirim
            send_btn = page.locator("button[aria-label*='Send' i], button:has(svg), div[role='button']:has-text('Send')").last
            try:
                if send_btn.is_visible(timeout=2000):
                    send_btn.click()
                else:
                    input_box.press("Enter")
            except Exception:
                input_box.press("Enter")
                
            print("⏳ Menunggu respon dari Claude...")
            time.sleep(15)
            
            # Ambil respon Claude terakhir
            responses = page.locator("div[data-is-streaming='false'], div[class*='font-claude-message'], div[class*='standard-markdown'], div[class*='prose']").all_inner_texts()
            reply_text = responses[-1] if responses else "Berhasil mengirim pesan ke Claude!"
            
            print("\n" + "="*40 + " CLAUDE REPLY " + "="*40)
            print(reply_text)
            print("="*94 + "\n")
            
            send_telegram_msg(f"🤖 [CLAUDE RELAY BERHASIL!]\n\nTuan Ciro, Claude menjawab:\n\n{reply_text}")
        else:
            print("⚠️ Kotak input chat belum terlihat, mengambil screenshot status...")
            page.screenshot(path="claude_status.png")
            page_content = page.content()
            # Cek apakah ada Cloudflare challenge
            if "Just a moment" in page_content or "challenges.cloudflare.com" in page_content:
                print("🛡️ Cloudflare Turnstile menghadang!")
                send_telegram_msg("🛡️ [CLAUDE RELAY] Terhalang Cloudflare Challenge!")
            elif "login" in page.url.lower() or "Log in" in page_title:
                print("🔒 Halaman redirect ke Login (Sesi kadaluarsa atau cookie butuh refresh)!")
                send_telegram_msg("🔒 [CLAUDE RELAY] Terlempar ke halaman Login (cookie expired/invalid).")
            else:
                print(f"⚠️ Sesi Claude belum menampilkan input chat. Title: {page_title}")
                send_telegram_msg(f"⚠️ [CLAUDE RELAY] Status page: {page_title} ({page.url})")

        browser.close()

if __name__ == "__main__":
    main()
