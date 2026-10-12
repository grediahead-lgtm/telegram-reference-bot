import argparse
import os
import sys

from .bot import Bot
from .client import Client, check_token, run
from .config import ConfigError, load_config


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ref_bot", description="FAQ and catalog bot for a small business.")
    ap.add_argument("--config", required=True)
    ap.add_argument("--check", action="store_true", help="validate the config and exit")
    a = ap.parse_args(argv)
    try:
        cfg = load_config(a.config)
    except ConfigError as e:
        print(f"Config error: {e}", file=sys.stderr)
        return 2
    if a.check:
        print(f"Config OK: {len(cfg['faq'])} FAQ, {len(cfg['catalog'])} categories")
        return 0
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    try:
        client = Client(token)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    ok, who = check_token(client)
    if not ok:
        print(f"Telegram rejected the token or is unreachable: {who}", file=sys.stderr)
        return 2
    print(f"Connected as {who}. Open THIS bot in Telegram and send /start. Press Ctrl+C to stop.")
    try:
        run(client, Bot(cfg), log=lambda t: print(t, file=sys.stderr))
    except KeyboardInterrupt:
        print("Stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
