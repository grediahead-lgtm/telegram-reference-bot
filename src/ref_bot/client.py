import json
import os
import ssl
import time
import urllib.error
import urllib.request

API = "https://api.telegram.org"


def _context():
    """TLS context WITH certificate checking. Python from python.org on macOS ships without CA certificates, so use the system bundle."""
    for cafile in ("/etc/ssl/cert.pem", "/private/etc/ssl/cert.pem"):
        if os.path.exists(cafile):
            return ssl.create_default_context(cafile=cafile)
    return ssl.create_default_context()


class Client:
    """Minimal Telegram Bot API client (long polling). The token is read by the caller from the environment and never logged."""

    def __init__(self, token, base=API, timeout=40):
        if not token or ":" not in token:
            raise ValueError("a Telegram bot token is required (environment variable TELEGRAM_BOT_TOKEN)")
        self._token = token
        self._url = f"{base}/bot{token}/"
        self.timeout = timeout
        self._ctx = _context()

    def call(self, method, payload=None):
        data = json.dumps(payload or {}).encode("utf-8")
        req = urllib.request.Request(self._url + method, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=self._ctx) as r:
                body = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return {"ok": False, "error": f"HTTP {e.code}"}
        except Exception as e:  # noqa: BLE001 - network problems must not crash the loop
            why = str(getattr(e, "reason", "") or "")[:100].replace(self._token, "***")
            return {"ok": False, "error": type(e).__name__ + (f": {why}" if why else "")}
        return body


def check_token(client):
    """getMe: (True, '@username') or (False, reason). Lets the owner see WHICH bot the token belongs to before polling starts."""
    res = client.call("getMe")
    if res.get("ok") and isinstance(res.get("result"), dict):
        u = res["result"]
        return True, "@" + str(u.get("username", "?")) + (" (" + str(u["first_name"]) + ")" if u.get("first_name") else "")
    return False, str(res.get("error", "Telegram rejected the request"))


def run(client, bot, stop=lambda: False, sleep=time.sleep, max_loops=None, log=lambda text: None):
    """Long-polling loop. Network errors back off (1..30 s); failed sends never stop the loop; message text is never logged."""
    offset, delay, loops, last_error = None, 1, 0, None
    while not stop() and (max_loops is None or loops < max_loops):
        loops += 1
        res = client.call("getUpdates", {"offset": offset, "timeout": 30, "allowed_updates": ["message", "callback_query"]})
        if not res.get("ok"):
            if res.get("error") != last_error:                # report a new kind of error once, never the message texts or the token
                log("Telegram error: " + str(res.get("error", "unknown")))
                last_error = res.get("error")
            sleep(delay)
            delay = min(delay * 2, 30)
            continue
        delay, last_error = 1, None
        for upd in res.get("result", []):
            offset = upd.get("update_id", 0) + 1
            for method, payload in bot.handle_update(upd):
                client.call(method, payload)
