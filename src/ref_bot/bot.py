"""Bot logic without network: handle_update(update) returns a list of Telegram API calls (method, payload)."""
import re
import time

RATE_LIMIT = 20      # messages per chat per window
RATE_WINDOW = 60.0
MSG_LIMIT = 3500     # Telegram allows 4096; leave a margin


def _tokens(text):
    return {t for t in re.findall(r"[\w']+", text.lower()) if len(t) >= 3}


def match_faq(text, faq, threshold=0.5):
    """Index of the FAQ entry whose question shares enough words with the text, or None. Never guesses below the threshold."""
    words = _tokens(text)
    best, best_score = None, 0.0
    for i, item in enumerate(faq):
        q = _tokens(item["q"])
        if not q or not words:
            continue
        score = len(words & q) / len(q)
        if score > best_score:
            best, best_score = i, score
    return best if best_score >= threshold else None


def _clip(text):
    return text if len(text) <= MSG_LIMIT else text[: MSG_LIMIT - 1] + "…"


def _kb(rows):
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in rows]}


class Bot:
    def __init__(self, cfg, clock=time.monotonic):
        self.cfg = cfg
        self.clock = clock
        self.awaiting = set()      # chats that pressed "send a request to the manager"
        self.hits = {}             # chat_id -> list of timestamps

    # --- menus ---------------------------------------------------------------------
    def main_menu(self):
        rows = []
        if self.cfg["catalog"]:
            rows.append([("Каталог", "cat")])
        if self.cfg["faq"]:
            rows.append([("Питання й відповіді", "faq")])
        rows.append([("Контакти", "contacts")])
        if self.cfg["owner_chat_id"] is not None:
            rows.append([("Передати запит менеджеру", "handoff")])
        return _kb(rows)

    def _msg(self, chat_id, text, markup=None):
        payload = {"chat_id": chat_id, "text": _clip(text)}
        if markup:
            payload["reply_markup"] = markup
        return ("sendMessage", payload)

    def _limited(self, chat_id):
        now = self.clock()
        hits = [t for t in self.hits.get(chat_id, []) if now - t < RATE_WINDOW]
        hits.append(now)
        self.hits[chat_id] = hits
        return len(hits) > RATE_LIMIT

    # --- updates ---------------------------------------------------------------------
    def handle_update(self, update):
        if not isinstance(update, dict):
            return []
        if "callback_query" in update:
            return self._callback(update["callback_query"])
        msg = update.get("message")
        if isinstance(msg, dict):
            return self._message(msg)
        return []

    def _message(self, msg):
        chat = msg.get("chat") or {}
        sender = msg.get("from") or {}
        chat_id = chat.get("id")
        if chat.get("type") != "private" or chat_id is None or sender.get("is_bot"):
            return []                                  # private chats only, never talk to bots
        text = msg.get("text")
        if not isinstance(text, str) or not text.strip():
            return [self._msg(chat_id, "Я розумію лише текстові повідомлення. Оберіть пункт меню.", self.main_menu())]
        if self._limited(chat_id):
            return [self._msg(chat_id, "Забагато повідомлень. Спробуйте за хвилину.")] if len(self.hits[chat_id]) == RATE_LIMIT + 1 else []
        text = text.strip()
        if text.split()[0].split("@")[0] in ("/start", "/menu", "/help"):
            self.awaiting.discard(chat_id)
            return [self._msg(chat_id, f"{self.cfg['greeting']}", self.main_menu())]
        if chat_id in self.awaiting:
            return self._forward(chat_id, sender, text)
        i = match_faq(text, self.cfg["faq"])
        if i is not None:
            return [self._msg(chat_id, self.cfg["faq"][i]["a"], self.main_menu())]
        return [self._msg(chat_id, self.cfg["fallback"], self.main_menu())]

    def _forward(self, chat_id, sender, text):
        self.awaiting.discard(chat_id)
        owner = self.cfg["owner_chat_id"]
        if owner is None:
            return [self._msg(chat_id, self.cfg["contacts"], self.main_menu())]
        who = " ".join(x for x in (sender.get("first_name"), f"@{sender['username']}" if sender.get("username") else None) if x) or "клієнт"
        note = f"Запит від клієнта: {who} (чат {chat_id})\n\n{text[:1500]}"
        return [self._msg(owner, note), self._msg(chat_id, self.cfg["handoff_done"], self.main_menu())]

    def _callback(self, cb):
        calls = []
        cid = cb.get("id")
        if cid:
            calls.append(("answerCallbackQuery", {"callback_query_id": cid}))
        msg = cb.get("message") or {}
        chat = msg.get("chat") or {}
        chat_id = chat.get("id")
        data = cb.get("data")
        if chat.get("type") != "private" or chat_id is None or not isinstance(data, str):
            return calls
        if self._limited(chat_id):
            return calls
        cfg = self.cfg
        if data == "menu":
            calls.append(self._msg(chat_id, cfg["greeting"], self.main_menu()))
        elif data == "cat" and cfg["catalog"]:
            rows = [[(c["category"], f"cat:{i}")] for i, c in enumerate(cfg["catalog"])] + [[("Меню", "menu")]]
            calls.append(self._msg(chat_id, "Оберіть категорію:", _kb(rows)))
        elif re.fullmatch(r"cat:\d{1,2}", data) and int(data[4:]) < len(cfg["catalog"]):
            c = cfg["catalog"][int(data[4:])]
            lines = [f"{c['category']}:"] + [f"- {it['name']}: {it['price']}" + (f" ({it['description']})" if it["description"] else "") for it in c["items"]]
            calls.append(self._msg(chat_id, "\n".join(lines), _kb([[("Інші категорії", "cat")], [("Меню", "menu")]])))
        elif data == "faq" and cfg["faq"]:
            rows = [[(f["q"][:60], f"faq:{i}")] for i, f in enumerate(cfg["faq"])] + [[("Меню", "menu")]]
            calls.append(self._msg(chat_id, "Оберіть питання:", _kb(rows)))
        elif re.fullmatch(r"faq:\d{1,2}", data) and int(data[4:]) < len(cfg["faq"]):
            calls.append(self._msg(chat_id, cfg["faq"][int(data[4:])]["a"], _kb([[("Інші питання", "faq")], [("Меню", "menu")]])))
        elif data == "contacts":
            calls.append(self._msg(chat_id, cfg["contacts"], self.main_menu()))
        elif data == "handoff" and cfg["owner_chat_id"] is not None:
            self.awaiting.add(chat_id)
            calls.append(self._msg(chat_id, cfg["handoff_prompt"]))
        return calls
