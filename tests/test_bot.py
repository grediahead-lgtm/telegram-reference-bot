import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from ref_bot import Bot, ConfigError, match_faq, validate_config  # noqa: E402
from ref_bot.client import Client, check_token, run  # noqa: E402

HERE = os.path.dirname(__file__)
RAW = json.load(open(os.path.join(HERE, "..", "examples", "config.example.json"), encoding="utf-8"))


def cfg(**over):
    raw = json.loads(json.dumps(RAW))
    raw.update(over)
    return validate_config(raw)


def msg(text, chat=1, ctype="private", is_bot=False, **extra):
    return {"update_id": 1, "message": {"chat": {"id": chat, "type": ctype}, "from": {"id": chat, "is_bot": is_bot, **extra}, "text": text}}


def cb(data, chat=1):
    return {"update_id": 2, "callback_query": {"id": "q1", "data": data, "message": {"chat": {"id": chat, "type": "private"}}}}


class Config(unittest.TestCase):
    def test_example_is_valid(self):
        c = cfg()
        self.assertEqual(len(c["faq"]), 3)
        self.assertEqual(c["catalog"][0]["items"][0]["price"], "1200")

    def test_rejects_bad_input(self):
        bad = [{}, {**RAW, "greeting": ""}, {**RAW, "owner_chat_id": "5"}, {**RAW, "owner_chat_id": True},
               {**RAW, "faq": [{"q": "x"}]}, {**RAW, "faq": "no"}, {**RAW, "catalog": [{"category": "A", "items": []}]},
               {**RAW, "catalog": [{"category": "A", "items": [{"name": "n", "price": None}]}]}, {**RAW, "greeting": "x" * 1001}, []]
        for b in bad:
            with self.assertRaises(ConfigError, msg=str(b)[:60]):
                validate_config(b)


class Matching(unittest.TestCase):
    def test_matches_and_does_not_guess(self):
        faq = cfg()["faq"]
        self.assertEqual(match_faq("як підібрати розмір лежака для кота", faq), 0)
        self.assertEqual(match_faq("яка доставка", faq), 1)
        self.assertIsNone(match_faq("яка сьогодні погода", faq))
        self.assertIsNone(match_faq("", faq))


class Flows(unittest.TestCase):
    def test_start_shows_menu_without_handoff_when_no_owner(self):
        (m, p), = Bot(cfg()).handle_update(msg("/start"))
        self.assertEqual(m, "sendMessage")
        labels = [b["text"] for row in p["reply_markup"]["inline_keyboard"] for b in row]
        self.assertIn("Каталог", labels)
        self.assertNotIn("Передати запит менеджеру", labels)

    def test_menu_has_handoff_when_owner_set(self):
        (_, p), = Bot(cfg(owner_chat_id=99)).handle_update(msg("/menu"))
        self.assertIn("Передати запит менеджеру", [b["text"] for row in p["reply_markup"]["inline_keyboard"] for b in row])

    def test_catalog_navigation(self):
        bot = Bot(cfg())
        calls = bot.handle_update(cb("cat"))
        self.assertEqual(calls[0][0], "answerCallbackQuery")
        self.assertIn("Лежаки", json.dumps(calls[1][1], ensure_ascii=False))
        items = bot.handle_update(cb("cat:0"))[1][1]["text"]
        self.assertIn("Лежак M (приклад): 1200", items)
        self.assertIn("(приклад позиції)", items)

    def test_invalid_callback_data_is_ignored(self):
        bot = Bot(cfg())
        for data in ("cat:99", "cat:-1", "faq:abc", "handoff", "../x", "cat:0;drop", ""):
            calls = bot.handle_update(cb(data))
            self.assertEqual([c[0] for c in calls], ["answerCallbackQuery"], data)

    def test_faq_by_free_text_and_fallback(self):
        bot = Bot(cfg())
        self.assertIn("15–20 см", bot.handle_update(msg("як підібрати розмір лежака"))[0][1]["text"])
        self.assertEqual(bot.handle_update(msg("яка погода"))[0][1]["text"], bot.cfg["fallback"])

    def test_handoff_forwards_once_to_owner(self):
        bot = Bot(cfg(owner_chat_id=99))
        bot.handle_update(cb("handoff", chat=5))
        calls = bot.handle_update(msg("Хочу замовити лежак", chat=5, first_name="Анна", username="anna"))
        self.assertEqual(calls[0][1]["chat_id"], 99)
        self.assertIn("Анна @anna", calls[0][1]["text"])
        self.assertIn("Хочу замовити лежак", calls[0][1]["text"])
        self.assertEqual(calls[1][1]["chat_id"], 5)
        again = bot.handle_update(msg("ще раз", chat=5))
        self.assertTrue(all(c[1]["chat_id"] == 5 for c in again))   # no second forward without pressing the button

    def test_id_command_shows_only_the_users_own_chat_id(self):
        (m, p), = Bot(cfg()).handle_update(msg("/id", chat=777))
        self.assertEqual((p["chat_id"], p["text"]), (777, "Ваш chat id: 777"))

    def test_groups_bots_and_non_text_are_handled_safely(self):
        bot = Bot(cfg())
        self.assertEqual(bot.handle_update(msg("/start", ctype="group")), [])
        self.assertEqual(bot.handle_update(msg("/start", is_bot=True)), [])
        photo = {"update_id": 3, "message": {"chat": {"id": 1, "type": "private"}, "from": {"id": 1}, "photo": []}}
        self.assertIn("лише текстові", bot.handle_update(photo)[0][1]["text"])
        for junk in (None, [], "x", {"foo": 1}, {"message": "x"}, {"callback_query": {}}):
            bot.handle_update(junk)                                  # must not raise

    def test_rate_limit(self):
        t = [0.0]
        bot = Bot(cfg(), clock=lambda: t[0])
        sent = [len(bot.handle_update(msg("яка погода"))) for _ in range(30)]
        self.assertEqual(sum(sent[:20]), 20)
        self.assertEqual(sent[20], 1)                                # one polite warning
        self.assertEqual(sum(sent[21:]), 0)                          # then silence
        t[0] = 61.0
        self.assertEqual(len(bot.handle_update(msg("яка погода"))), 1)

    def test_payload_limits_and_plain_text(self):
        long_cfg = cfg(greeting="г" * 1000)
        bot = Bot(long_cfg)
        calls = bot.handle_update(cb("cat"))
        for _, p in calls[1:]:
            self.assertNotIn("parse_mode", p)
            for row in p.get("reply_markup", {}).get("inline_keyboard", []):
                for b in row:
                    self.assertLessEqual(len(b["callback_data"].encode()), 64)
        big = Bot(cfg(owner_chat_id=9))
        big.handle_update(cb("handoff"))
        forwarded = big.handle_update(msg("я" * 5000))[0][1]["text"]
        self.assertLessEqual(len(forwarded), 3500)


class FakeClient:
    def __init__(self, responses):
        self.responses, self.sent = list(responses), []

    def call(self, method, payload=None):
        self.sent.append((method, payload))
        if method == "getUpdates":
            return self.responses.pop(0) if self.responses else {"ok": True, "result": []}
        return {"ok": True}


class Startup(unittest.TestCase):
    def test_check_token_names_the_bot_or_explains(self):
        class C:
            def __init__(self, r):
                self.r = r

            def call(self, method, payload=None):
                return self.r
        self.assertEqual(check_token(C({"ok": True, "result": {"username": "shop_bot", "first_name": "Shop"}})), (True, "@shop_bot (Shop)"))
        self.assertEqual(check_token(C({"ok": False, "error": "HTTP 401"})), (False, "HTTP 401"))

    def test_errors_are_logged_once_per_kind_without_secrets(self):
        client = FakeClient([{"ok": False, "error": "HTTP 401"}] * 3 + [{"ok": True, "result": []}, {"ok": False, "error": "URLError"}])
        logs = []
        run(client, Bot(cfg()), sleep=lambda s: None, max_loops=5, log=logs.append)
        self.assertEqual(logs, ["Telegram error: HTTP 401", "Telegram error: URLError"])


class Loop(unittest.TestCase):
    def test_processes_updates_advances_offset_and_survives_errors(self):
        client = FakeClient([{"ok": False, "error": "URLError"}, {"ok": True, "result": [{**msg("/start"), "update_id": 10}]}])
        sleeps = []
        run(client, Bot(cfg()), sleep=sleeps.append, max_loops=3)
        self.assertEqual(sleeps, [1])                                # one backoff after the error
        polls = [p for m, p in client.sent if m == "getUpdates"]
        self.assertEqual(polls[2]["offset"], 11)
        self.assertTrue(any(m == "sendMessage" for m, _ in client.sent))

    def test_backoff_grows_and_caps(self):
        client = FakeClient([{"ok": False}] * 8)
        sleeps = []
        run(client, Bot(cfg()), sleep=sleeps.append, max_loops=8)
        self.assertEqual(sleeps, [1, 2, 4, 8, 16, 30, 30, 30])

    def test_client_requires_a_token(self):
        for bad in ("", None, "no-colon"):
            with self.assertRaises(ValueError):
                Client(bad)


class HttpClient(unittest.TestCase):
    """The real Client against a local fake Telegram API (no internet, fake token)."""

    def test_call_posts_json_and_handles_errors(self):
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer
        seen = []

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                seen.append((self.path, body))
                code = 502 if self.path.endswith("/boom") else 200
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok": true, "result": []}')

        srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            c = Client("123:fake", base=f"http://127.0.0.1:{srv.server_address[1]}", timeout=3)
            self.assertTrue(c.call("sendMessage", {"chat_id": 1, "text": "x"})["ok"])
            self.assertEqual(seen[0][0], "/bot123:fake/sendMessage")
            self.assertEqual(c.call("boom")["error"], "HTTP 502")
        finally:
            srv.shutdown()
            srv.server_close()
        dead = Client("123:fake", base="http://127.0.0.1:9", timeout=1)
        res = dead.call("getUpdates")
        self.assertFalse(res["ok"])
        self.assertNotIn("123:fake", res["error"])               # the token never appears in error text
        self.assertTrue(res["error"].startswith("URLError"))


if __name__ == "__main__":
    unittest.main()
