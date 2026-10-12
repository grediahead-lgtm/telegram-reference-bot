import json
import time
import urllib.error
import urllib.request

API = "https://api.telegram.org"


class Client:
    """Minimal Telegram Bot API client (long polling). The token is read by the caller from the environment and never logged."""

    def __init__(self, token, base=API, timeout=40):
        if not token or ":" not in token:
            raise ValueError("a Telegram bot token is required (environment variable TELEGRAM_BOT_TOKEN)")
        self._url = f"{base}/bot{token}/"
        self.timeout = timeout

    def call(self, method, payload=None):
        data = json.dumps(payload or {}).encode("utf-8")
        req = urllib.request.Request(self._url + method, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                body = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return {"ok": False, "error": f"HTTP {e.code}"}
        except Exception as e:  # noqa: BLE001 - network problems must not crash the loop
            return {"ok": False, "error": type(e).__name__}
        return body


def run(client, bot, stop=lambda: False, sleep=time.sleep, max_loops=None):
    """Long-polling loop. Network errors back off (1..30 s); failed sends never stop the loop; message text is never logged."""
    offset, delay, loops = None, 1, 0
    while not stop() and (max_loops is None or loops < max_loops):
        loops += 1
        res = client.call("getUpdates", {"offset": offset, "timeout": 30, "allowed_updates": ["message", "callback_query"]})
        if not res.get("ok"):
            sleep(delay)
            delay = min(delay * 2, 30)
            continue
        delay = 1
        for upd in res.get("result", []):
            offset = upd.get("update_id", 0) + 1
            for method, payload in bot.handle_update(upd):
                client.call(method, payload)
