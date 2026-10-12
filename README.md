# telegram-reference-bot

A small Telegram bot for a small business: answers frequent questions, shows a price catalog, and passes a customer's request to the owner. Python standard library only, no database, no web server. Configure it with one JSON file.

## What it does
- `/start` shows a menu: **Catalog**, **Questions and answers**, **Contacts**, **Send a request to the manager** (only if you set an owner chat).
- Free-text questions are matched against your FAQ by shared words. **If nothing matches well enough, it does not guess**: it shows the fallback text and the menu.
- A request to the manager is forwarded once to the owner's chat (name, @username, chat id, the message).
- Private chats only. Other bots and groups are ignored. Rate limit per chat (20 messages per minute). Plain text only, no markup injection.
- The bot token is **never** in the config or logs: set the environment variable `TELEGRAM_BOT_TOKEN`. Message texts are not logged.

## Quick start
1. Create a bot with @BotFather and copy its token.
2. Copy `examples/config.example.json` to `config.json` and edit texts, FAQ, catalog. To get your own chat id, use any "get my id" bot and put it in `owner_chat_id`, or leave `null` to disable requests to a manager.
3. Check the file, then run:
```bash
PYTHONPATH=src python3 -m ref_bot --config config.json --check
TELEGRAM_BOT_TOKEN=123456:your-token PYTHONPATH=src python3 -m ref_bot --config config.json
```
Local test with your own bot: `bash scripts/run_local.sh` (asks for the token, hidden). Send `/id` to the bot to see your chat id for `owner_chat_id`.

Tests (no internet, fake token): `python3 -m unittest discover -s tests`.

## Config fields
`business_name`, `greeting`, `contacts` (required text), `faq` (up to 30 items `{q, a}`), `catalog` (up to 10 categories with 1 to 30 items `{name, price, description?}`), `owner_chat_id` (integer or null), optional `fallback`, `handoff_prompt`, `handoff_done`. The file is validated on start; mistakes are reported with the field name.

## Limits (read this)
- It is a reference bot, not a shop: no payments, no orders, no stock, no database. Prices and answers are only what you write in the config.
- Matching is by shared words (3+ letters), not by meaning. Write FAQ questions the way customers ask.
- Long polling from your own computer or server; if the process stops, the bot stops. Put it under a process manager for production.
- Texts in the example are Ukrainian placeholders: replace them.

MIT license.

---

# telegram-reference-bot (українською)

Невеликий Telegram-бот для малого бізнесу: відповідає на часті питання, показує каталог із цінами й передає запит клієнта власнику. Лише стандартна бібліотека Python, без бази даних і веб-сервера. Налаштування в одному JSON-файлі.

**Швидкий старт:** створіть бота через @BotFather, скопіюйте `examples/config.example.json` у `config.json`, замініть тексти, перевірте (`--check`) і запустіть із токеном у змінній `TELEGRAM_BOT_TOKEN`. Токен не зберігається в конфігу й логах.

**Важливо:** якщо питання не збігається з вашим FAQ достатньо добре, бот не вгадує, а показує запасний текст і меню. Це довідник, а не магазин: без оплат, замовлень і складу.
