#!/usr/bin/env python3
"""Configure Telegram Bot API webhook for ShramShield.

Reads TELEGRAM_BOT_TOKEN and TELEGRAM_WEBHOOK_SECRET from environment variables.
Pass the API Gateway base URL with --api.
Never logs or prints tokens or secrets.
"""

import argparse
import json
import os
import sys

# Add backend/src to sys.path so we can import common.telegram
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC_DIR = os.path.join(_BACKEND_DIR, "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from common import telegram


def main() -> int:
    parser = argparse.ArgumentParser(description="Set Telegram webhook for ShramShield API Gateway")
    parser.add_argument("--api", required=True, help="API Gateway base URL (e.g. https://xyz.execute-api.ap-south-1.amazonaws.com)")
    args = parser.parse_args()

    api_base = args.api.rstrip("/")
    webhook_url = f"{api_base}/telegram/webhook"

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    webhook_secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()

    if not bot_token or bot_token == "not-set":
        print("ERROR: TELEGRAM_BOT_TOKEN environment variable is not set.", file=sys.stderr)
        return 1

    if not webhook_secret or webhook_secret == "not-set":
        print("ERROR: TELEGRAM_WEBHOOK_SECRET environment variable is not set.", file=sys.stderr)
        return 1

    print(f"Setting webhook to: {webhook_url}")
    try:
        resp = telegram.set_webhook(url=webhook_url, secret_token=webhook_secret)
        print("setWebhook response:", resp.get("description", "OK"))
    except telegram.TelegramError as exc:
        print(f"ERROR calling setWebhook: {exc}", file=sys.stderr)
        return 1

    print("Fetching webhook info...")
    try:
        info_resp = telegram.get_webhook_info()
        result = info_resp.get("result", {})
        print("Webhook info:")
        print(f"  URL: {result.get('url')}")
        print(f"  Pending update count: {result.get('pending_update_count')}")
        if result.get("last_error_message"):
            print(f"  Last error: {result.get('last_error_message')}")
        if result.get("last_error_date"):
            print(f"  Last error date: {result.get('last_error_date')}")
        return 0
    except telegram.TelegramError as exc:
        print(f"ERROR calling getWebhookInfo: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
