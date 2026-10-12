#!/bin/bash
# Starts the bot for a local test. The token is typed hidden and is not stored in a file or in shell history.
cd "$(dirname "$0")/.." || exit 1
CONFIG="${1:-config.json}"
[ -f "$CONFIG" ] || { echo "No $CONFIG. Run: cp examples/config.example.json config.json"; exit 1; }
read -r -s -p "Paste the token from @BotFather (hidden), then Enter: " TELEGRAM_BOT_TOKEN
echo
export TELEGRAM_BOT_TOKEN
PYTHONPATH=src python3 -m ref_bot --config "$CONFIG"
