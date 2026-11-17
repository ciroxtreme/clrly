import os
import sys
import json
import time
import requests
import random
from patchright.sync_api import sync_playwright

CLAUDE_COOKIES_JSON = os.environ.get("CLAUDE_COOKIES_JSON")
CLAUDE_ORG_ID = os.environ.get("CLAUDE_ORG_ID")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
WEBSHARE_ROTATING_PROXY = os.environ.get("WEBSHARE_ROTATING_PROXY")
PROMPT = sys.argv[1] if len(sys.argv) > 1 else "Halo Claude, apakah sesi ini aktif?"

def send_telegram_msg(text: str):
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        print(f"[TG] {text}")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text
    }
    try:
        requests.post(url, data=payload, timeout=10)
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

    launch_args = [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage"
    ]
    
    launch_kwargs = {
        "headless": True,
        "args": launch_args
    }
    
    if WEBSHARE_ROTATING_PROXY:
        print(f"🌐 [Proxy] Mengaktifkan Residential/Rotating Proxy...")
        launch_kwargs["proxy"] = {"server": WEBSHARE_ROTATING_PROXY}

    print(f"🚀 [Patchright Stealth Engine] Menyiapkan browser anti-detect dengan {len(playwright_cookies)} cookies...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_kwargs)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="en-US",
            timezone_id="America/New_York",
        )
        
        added_count = 0
        for c in playwright_cookies:
            try:
                context.add_cookies([c])
                added_count += 1
            except Exception as e:
                print(f"Peringatan cookie {c.get('name')}: {e}")
                
        print(f"✅ [Patchright] Berhasil menginjeksi {added_count}/{len(playwright_cookies)} cookies ke sesi browser.")
        page = context.new_page()

        print("1. Membuka https://claude.ai/chats dengan Patchright...")
        try:
            page.goto("https://claude.ai/chats", wait_until="commit", timeout=30000)
        except Exception as e:
            print(f"Peringatan saat goto: {e}")
            
        print("⏳ Menunggu rendering dan deteksi DOM...")
        for i in range(10):
            time.sleep(2)
            try:
                url = page.url
                title = page.title()
                html_len = len(page.content())
                body_txt = page.evaluate("() => document.body ? document.body.innerText.substring(0, 100).replace(/\\n/g, ' ') : ''")
                print(f"[{i*2}s] URL: {url} | Title: '{title}' | HTML: {html_len}B | Body: '{body_txt}'")
            except Exception as e:
                print(f"Error inspecting: {e}")

            if page.locator("div[contenteditable='true'], div.ProseMirror, textarea").count() > 0:
                print("✨ Input chat sudah siap!")
                break

        page_title = page.title()
        print(f"Final Page Title: {page_title}")
        print(f"Final URL: {page.url}")

        # Cari elemen input chat Claude
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
                if loc.is_visible(timeout=2000):
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
            
            send_telegram_msg(f"🤖 [CLAUDE RELAY VIA PATCHRIGHT]\n\nTuan Ciro, Claude menjawab:\n\n{reply_text}")
        else:
            print("⚠️ Kotak input chat belum terlihat, mendeteksi halaman...")
            page_content = page.content()
            if "Just a moment" in page_content or "challenges.cloudflare.com" in page_content:
                msg = "🛡️ [CLAUDE RELAY] Sesi terhadang Cloudflare Challenge!"
            elif "login" in page.url.lower() or "Log in" in page_title:
                msg = "🔒 [CLAUDE RELAY] Terlempar ke halaman Login (Cookie sesi Claude perlu diperbarui)."
            else:
                msg = f"⚠️ [CLAUDE RELAY] Halaman termuat: '{page_title}' ({page.url})"
            
            print(msg)
            send_telegram_msg(msg)

        browser.close()

if __name__ == "__main__":
    main()
