import json
from pathlib import Path

MAX_TEXT = 1000


class ConfigError(ValueError):
    pass


def _text(value, name, required=True, limit=MAX_TEXT):
    if value is None and not required:
        return ""
    if not isinstance(value, str) or (required and not value.strip()):
        raise ConfigError(f"{name}: expected non-empty text")
    if len(value) > limit:
        raise ConfigError(f"{name}: longer than {limit} characters")
    return value.strip()


def validate_config(raw):
    """Returns a normalized config or raises ConfigError. The bot token is NOT part of the config (environment variable)."""
    if not isinstance(raw, dict):
        raise ConfigError("config must be a JSON object")
    cfg = {
        "business_name": _text(raw.get("business_name"), "business_name", limit=80),
        "greeting": _text(raw.get("greeting"), "greeting"),
        "contacts": _text(raw.get("contacts"), "contacts"),
        "fallback": _text(raw.get("fallback", "Не знаю відповіді. Оберіть пункт меню або передайте запит менеджеру."), "fallback"),
        "handoff_prompt": _text(raw.get("handoff_prompt", "Напишіть ваше питання одним повідомленням, і я передам його менеджеру."), "handoff_prompt"),
        "handoff_done": _text(raw.get("handoff_done", "Передано менеджеру. Ми відповімо вам."), "handoff_done"),
    }
    owner = raw.get("owner_chat_id")
    if owner is not None and (not isinstance(owner, int) or isinstance(owner, bool)):
        raise ConfigError("owner_chat_id: expected an integer or null")
    cfg["owner_chat_id"] = owner
    faq = raw.get("faq", [])
    if not isinstance(faq, list) or len(faq) > 30:
        raise ConfigError("faq: expected a list of at most 30 items")
    cfg["faq"] = [{"q": _text(i.get("q") if isinstance(i, dict) else None, "faq.q", limit=120),
                   "a": _text(i.get("a") if isinstance(i, dict) else None, "faq.a")} for i in faq]
    catalog = raw.get("catalog", [])
    if not isinstance(catalog, list) or len(catalog) > 10:
        raise ConfigError("catalog: expected a list of at most 10 categories")
    out = []
    for c in catalog:
        if not isinstance(c, dict):
            raise ConfigError("catalog category must be an object")
        items = c.get("items", [])
        if not isinstance(items, list) or not items or len(items) > 30:
            raise ConfigError("catalog.items: expected 1 to 30 items")
        norm = []
        for it in items:
            if not isinstance(it, dict):
                raise ConfigError("catalog item must be an object")
            price = it.get("price")
            if not isinstance(price, (int, float, str)) or isinstance(price, bool):
                raise ConfigError("catalog.price: expected a number or text")
            norm.append({"name": _text(it.get("name"), "catalog.name", limit=120), "price": str(price).strip(),
                         "description": _text(it.get("description"), "catalog.description", required=False)})
        out.append({"category": _text(c.get("category"), "catalog.category", limit=60), "items": norm})
    cfg["catalog"] = out
    return cfg


def load_config(path):
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ConfigError(f"cannot read config: {e}") from e
    return validate_config(raw)
