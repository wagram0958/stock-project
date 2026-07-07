#!/usr/bin/env python3
"""Hermes Discord notifier — reads .env, sends plain-text webhook."""
import json, os, sys, urllib.request

def load_webhook():
    env = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    for line in open(env):
        if line.startswith("DISCORD_WEBHOOK_URL="):
            return line.split("=", 1)[1].strip()
    raise ValueError(".env missing DISCORD_WEBHOOK_URL")

def send(message: str):
    url = load_webhook()
    data = json.dumps({"content": message}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req)
        return True
    except Exception as e:
        print(f"Discord send failed: {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    msg = sys.argv[1] if len(sys.argv) > 1 else "Hermes heartbeat ping"
    ok = send(msg)
    sys.exit(0 if ok else 1)
