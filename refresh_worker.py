import os
import sys
import json
import time
import requests
from curl_cffi import requests as cffi_requests

CLAUDE_COOKIES_JSON = os.environ.get("CLAUDE_COOKIES_JSON")
CLAUDE_ORG_ID = os.environ.get("CLAUDE_ORG_ID")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
WEBSHARE_ROTATING_PROXY = os.environ.get("WEBSHARE_ROTATING_PROXY")

def send_telegram_alert(text: str):
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        print(f"[TG ALERT] {text}")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"[TG Error] {e}")

def main():
    if not CLAUDE_COOKIES_JSON:
        print("❌ Error: CLAUDE_COOKIES_JSON not set!")
        sys.exit(1)

    cookies_dict = json.loads(CLAUDE_COOKIES_JSON)
    org_id = CLAUDE_ORG_ID or cookies_dict.get("lastActiveOrg", "227876df-8a25-471d-b09a-1e3058dcc3d0")
    proxy_cfg = {"http": WEBSHARE_ROTATING_PROXY, "https": WEBSHARE_ROTATING_PROXY} if WEBSHARE_ROTATING_PROXY else None

    cookie_str = "; ".join([f"{k}={v}" for k, v in cookies_dict.items()])
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        "Referer": "https://claude.ai/",
        "Origin": "https://claude.ai",
        "Accept": "application/json",
        "Cookie": cookie_str
    }

    print("🔄 [Claude Evergreen Refresher] Mengirim heartbeat keepalive ke Anthropic...")
    
    # Heartbeat endpoint 1: Cek list percakapan (memperbarui timestamp sessionKeyLC & activitySessionId)
    try:
        r = cffi_requests.get(
            f"https://claude.ai/api/organizations/{org_id}/chat_conversations?limit=1",
            impersonate="chrome124",
            proxies=proxy_cfg,
            headers=headers,
            timeout=25
        )
    except Exception as e:
        print(f"⚠️ Koneksi heartbeat error: {e}")
        sys.exit(1)

    print(f"Heartbeat response status: {r.status_code}")

    if r.status_code == 200:
        print("✅ SESI CLAUDE SEHAT & BUGAR! (Status 200 OK)")
        
        # Tangkap jika ada Set-Cookie baru dari server (Cloudflare/Anthropic token rolling)
        updated_any = False
        for k, v in r.cookies.items():
            if v and cookies_dict.get(k) != v:
                cookies_dict[k] = v
                updated_any = True
                print(f"✨ Cookie diperbarui oleh server: {k}")

        cookies_dict["sessionKeyLC"] = str(int(time.time() * 1000))
        
        # Tulis ke file untuk di-commit ke GitHub Secret jika ada perubahan
        with open("refreshed_session.json", "w") as f:
            json.dump(cookies_dict, f)
        print("📁 refreshed_session.json siap di-sync.")
        
    elif r.status_code in (401, 403):
        err_body = r.text[:300]
        print(f"🚨 [CRITICAL] Sesi terdeteksi kadaluarsa / invalid: {err_body}")
        alert_msg = (
            "🚨 [ALERT CLAUDE RELAY] Sesi Claude Terputus!\n\n"
            f"Server Anthropic menolak sesi aktif (Status {r.status_code}).\n"
            "Masa berlaku sessionKey habis atau logout terdeteksi. Silakan ekspor cookie baru dari claude.ai untuk Tuan Ciro!"
        )
        send_telegram_alert(alert_msg)
        sys.exit(1)
    else:
        print(f"⚠️ Respon tidak biasa dari Claude: Status {r.status_code}")

if __name__ == "__main__":
    main()
