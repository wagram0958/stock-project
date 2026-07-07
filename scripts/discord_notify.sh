#!/usr/bin/env bash
# Hermes Discord notifier — sends $1 as plain text to webhook from .env
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WEBHOOK=$(grep '^DISCORD_WEBHOOK_URL=' "$(dirname "$SCRIPT_DIR")/.env" | cut -d= -f2-)
MSG="${1:-Hermes heartbeat ping}"
# Use python for proper JSON encoding to handle unicode/emoji
RESULT=$(python3 -c "
import json,sys
print(json.dumps({'content': sys.argv[1]}))" "$MSG")
CODE=$(curl -s -w "\n%{http_code}" -H "Content-Type: application/json" -d "$RESULT" "$WEBHOOK" | tail -1)
[ "$CODE" = "204" ] && exit 0 || { echo "Discord HTTP $CODE"; exit 1; }
