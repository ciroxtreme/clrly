import os
import sys
import json
import time
import uuid
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
        print("Error: CLAUDE_COOKIES_JSON not set!")
        sys.exit(1)

    cookies_dict = json.loads(CLAUDE_COOKIES_JSON)
    org_id = CLAUDE_ORG_ID or cookies_dict.get("lastActiveOrg", "227876df-8a25-471d-b09a-1e3058dcc3d0")
    proxy_cfg = {"http": WEBSHARE_ROTATING_PROXY, "https": WEBSHARE_ROTATING_PROXY} if WEBSHARE_ROTATING_PROXY else None

    cookie_str = "; ".join([f"{k}={v}" for k, v in cookies_dict.items()])
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        "Referer": "https://claude.ai/",
        "Origin": "https://claude.ai",
        "Content-Type": "application/json",
        "Accept": "*/*",
        "Cookie": cookie_str
    }

    print("Refreshing Claude Session keepalive...")
    new_uuid = str(uuid.uuid4())
    create_payload = {
        "uuid": new_uuid,
        "name": f"Keepalive-{int(time.time())}"
    }

    try:
        r = cffi_requests.post(
            f"https://claude.ai/api/organizations/{org_id}/chat_conversations",
            json=create_payload,
            impersonate="chrome124",
            proxies=proxy_cfg,
            headers=headers,
            timeout=25
        )
    except Exception as e:
        print(f"Connection error: {e}")
        sys.exit(1)

    print(f"Heartbeat response status: {r.status_code}")

    if r.status_code in (200, 201):
        print("SUCCESS! Claude session is alive and valid.")
        for k, v in r.cookies.items():
            if v and cookies_dict.get(k) != v:
                cookies_dict[k] = v
                print(f"Updated cookie: {k}")

        cookies_dict["sessionKeyLC"] = str(int(time.time() * 1000))
        with open("refreshed_session.json", "w") as f:
            json.dump(cookies_dict, f)
        print("refreshed_session.json ready.")

        try:
            cffi_requests.delete(
                f"https://claude.ai/api/organizations/{org_id}/chat_conversations/{new_uuid}",
                impersonate="chrome124",
                proxies=proxy_cfg,
                headers=headers,
                timeout=10
            )
        except Exception:
            pass
    else:
        print(f"Claude returned status {r.status_code}: {r.text[:200]}")
        send_telegram_alert(f"Claude Keepalive Status: {r.status_code}")
        sys.exit(1)

if __name__ == "__main__":
    main()
