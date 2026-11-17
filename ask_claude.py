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

def send_telegram_photo(caption: str, photo_path: str):
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID and os.path.exists(photo_path)):
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    try:
        with open(photo_path, "rb") as f:
            requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption}, files={"photo": f}, timeout=20)
    except Exception as e:
        print(f"[TG Photo Error] {e}")

def try_solve_turnstile(page, timeout=35):
    """
    Menembus Cloudflare Turnstile Challenge via deteksi frame dan interaksi koordinat/selector.
    """
    print("🛡️ [Turnstile Solver] Memantau dan menembus Cloudflare Challenge...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        title = (page.title() or "").lower()
        url = page.url.lower()
        
        # Jika sudah tidak ada challenge di URL dan title, cek input
        if "challenge" not in url and "just a moment" not in title and "tunggu sebentar" not in title:
            if page.locator("div[contenteditable='true'], div.ProseMirror, textarea").count() > 0:
                print("🎉 [Turnstile Solver] Lolos dari Cloudflare! Halaman chat aktif.")
                return True

        # 1. Cari frame challenges.cloudflare.com
        for frame in page.frames:
            if "challenges.cloudflare.com" in frame.url or "cloudflare" in frame.url:
                try:
                    candidates = [
                        "input[type='checkbox']",
                        "#challenge-stage",
                        ".ctp-checkbox-label",
                        ".cb-i",
                        "label[for]",
                        "body"
                    ]
                    for sel in candidates:
                        target = frame.locator(sel).first
                        if target.is_visible(timeout=1000):
                            print(f"👉 [Turnstile Solver] Klik checkbox Turnstile di dalam frame ({sel})...")
                            target.click(force=True, timeout=2000)
                            time.sleep(3)
                            break
                except Exception:
                    pass

        # 2. Fallback: Deteksi iframe locator di main frame lalu klik koordinat
        try:
            iframe_loc = page.locator("iframe[src*='challenges.cloudflare.com'], iframe[title*='Cloudflare security challenge'], iframe[title*='Turnstile']").first
            if iframe_loc.count() > 0 and iframe_loc.is_visible(timeout=1000):
                box = iframe_loc.bounding_box()
                if box and box['width'] > 0 and box['height'] > 0:
                    click_x = box['x'] + random.uniform(28, 35)
                    click_y = box['y'] + (box['height'] / 2) + random.uniform(-2, 2)
                    print(f"🎯 [Turnstile Solver] Klik koordinat checkbox ({int(click_x)}, {int(click_y)})...")
                    page.mouse.move(click_x - random.uniform(20, 40), click_y - random.uniform(15, 30))
                    time.sleep(0.15)
                    page.mouse.click(click_x, click_y)
                    time.sleep(3)
        except Exception:
            pass

        time.sleep(1.5)

    return False

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

    print(f"🚀 [Patchright Stealth Engine] Menyiapkan browser anti-detect dengan {len(playwright_cookies)} cookies...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage"
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
        
        added_count = 0
        for c in playwright_cookies:
            try:
                context.add_cookies([c])
                added_count += 1
            except Exception as e:
                print(f"Peringatan cookie {c.get('name')}: {e}")
                
        print(f"✅ [Patchright] Berhasil menginjeksi {added_count}/{len(playwright_cookies)} cookies ke sesi browser.")
        page = context.new_page()

        print("1. Membuka https://claude.ai/new dengan Patchright...")
        try:
            page.goto("https://claude.ai/new", wait_until="commit", timeout=30000)
        except Exception as e:
            print(f"Peringatan saat goto: {e}")
            
        print("⏳ Menunggu initial loading (5 detik)...")
        time.sleep(5)

        # Cek apakah ada Cloudflare challenge redirect
        if "challenge" in page.url or "tunggu sebentar" in page.title().lower() or "just a moment" in page.title().lower():
            print("🛡️ [CLAUDE RELAY] Terdeteksi Cloudflare Turnstile Challenge! Menjalankan Turnstile Solver...")
            try_solve_turnstile(page, timeout=30)
            time.sleep(5)

        page_title = page.title()
        print(f"Title: {page_title}")
        print(f"Current URL: {page.url}")
        
        screenshot_file = "claude_screen.png"
        try:
            page.screenshot(path=screenshot_file, timeout=5000)
        except Exception as e:
            print(f"Gagal screenshot: {e}")

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
            
            send_telegram_msg(f"🤖 [CLAUDE RELAY VIA PATCHRIGHT]\n\nTuan Ciro, Claude menjawab:\n\n{reply_text}")
        else:
            print("⚠️ Kotak input chat belum terlihat, mendeteksi halaman...")
            page_content = page.content()
            if "Just a moment" in page_content or "challenges.cloudflare.com" in page_content:
                msg = "🛡️ [CLAUDE RELAY] Sesi terhadang Cloudflare Challenge!"
            elif "login" in page.url.lower() or "Log in" in page_title:
                msg = "🔒 [CLAUDE RELAY] Terlempar ke halaman Login (Cookie sesi Claude perlu diperbarui)."
            else:
                msg = f"⚠️ [CLAUDE RELAY] Halaman termuat: {page_title} ({page.url})"
            
            print(msg)
            send_telegram_msg(msg)
            if os.path.exists(screenshot_file):
                send_telegram_photo(f"Status Layar Claude ({page_title})", screenshot_file)

        browser.close()

if __name__ == "__main__":
    main()
