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
    cookie_str = "; ".join([f"{k}={v}" for k, v in cookies_dict.items()])
    org_id = CLAUDE_ORG_ID or cookies_dict.get("lastActiveOrg", "227876df-8a25-471d-b09a-1e3058dcc3d0")

    proxy_cfg = {"http": WEBSHARE_ROTATING_PROXY, "https": WEBSHARE_ROTATING_PROXY} if WEBSHARE_ROTATING_PROXY else None

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        "Referer": "https://claude.ai/",
        "Origin": "https://claude.ai",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "Cookie": cookie_str
    }

    print("🚀 [Claude Relay Engine] Menginisialisasi sesi percakapan baru...")
    new_uuid = str(uuid.uuid4())
    create_payload = {
        "uuid": new_uuid,
        "name": f"Session-{int(time.time())}"
    }

    r_create = cffi_requests.post(
        f"https://claude.ai/api/organizations/{org_id}/chat_conversations",
        json=create_payload,
        impersonate="chrome124",
        proxies=proxy_cfg,
        headers=headers,
        timeout=20
    )

    if r_create.status_code not in (200, 201):
        err_msg = f"❌ [CLAUDE RELAY ERROR] Gagal inisialisasi room (Status {r_create.status_code}): {r_create.text[:200]}"
        print(err_msg)
        send_telegram_msg(err_msg)
        sys.exit(1)

    print(f"✅ Sesi percakapan siap ({new_uuid}). Mengetik instruksi: '{PROMPT}'...")
    completion_payload = {
        "prompt": PROMPT,
        "timezone": "Asia/Jakarta",
        "model": "claude-sonnet-5-5",
        "attachments": [],
        "files": []
    }
    headers["Referer"] = f"https://claude.ai/chat/{new_uuid}"

    r_stream = cffi_requests.post(
        f"https://claude.ai/api/organizations/{org_id}/chat_conversations/{new_uuid}/completion",
        json=completion_payload,
        impersonate="chrome124",
        proxies=proxy_cfg,
        headers=headers,
        timeout=120,
        stream=True
    )

    full_response = []
    print("\n" + "="*40 + " CLAUDE REPLY " + "="*40 + "\n")
    for line in r_stream.iter_lines():
        if line:
            decoded = line.decode("utf-8", errors="replace")
            if decoded.startswith("data: "):
                try:
                    data = json.loads(decoded[6:])
                    if data.get("type") == "completion":
                        comp = data.get("completion", "")
                        print(comp, end="", flush=True)
                        full_response.append(comp)
                except Exception:
                    pass
    print("\n\n" + "="*95 + "\n")

    reply_text = "".join(full_response)
    if reply_text:
        send_telegram_msg(f"🤖 [CLAUDE 3.5 SONNET RELAY]\n\nTuan Ciro, Claude menjawab:\n\n{reply_text}")

if __name__ == "__main__":
    main()
