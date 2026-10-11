"""Telegram Bot API client (standard library urllib only).

Security rule: NEVER log the bot token, URLs containing the token,
headers, or full responses. Log only method names and error descriptions.
"""

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger("telegram")
logger.setLevel(logging.INFO)


class TelegramError(Exception):
    """Raised when Telegram Bot API returns ok: false or fails."""


def _get_bot_token() -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or token == "not-set":
        raise TelegramError("TELEGRAM_BOT_TOKEN environment variable not set")
    return token


def call(method: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Execute a Telegram Bot API method via HTTPS POST."""
    token = _get_bot_token()
    url = f"https://api.telegram.org/bot{token}/{method}"

    data_bytes = None
    headers = {}
    if payload is not None:
        data_bytes = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            result = json.loads(raw)
            if not result.get("ok"):
                desc = result.get("description", "Unknown error")
                logger.error("Telegram API call %s failed: %s", method, desc)
                raise TelegramError(desc)
            return result
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
            desc = body.get("description", str(exc))
        except Exception:
            desc = str(exc)
        logger.error("Telegram API HTTP error on %s: %s", method, desc)
        raise TelegramError(desc)
    except urllib.error.URLError as exc:
        logger.error("Telegram API network error on %s: %s", method, exc.reason)
        raise TelegramError(f"Network error: {exc.reason}")


def send_message(
    chat_id: Any,
    text: str,
    reply_markup: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Send a text message, optionally with an inline keyboard."""
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return call("sendMessage", payload)


def send_audio(
    chat_id: Any,
    audio_url: str,
    caption: Optional[str] = None,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """Send an audio file using a public/presigned HTTPS URL."""
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "audio": audio_url,
    }
    if caption:
        payload["caption"] = caption
    if title:
        payload["title"] = title
    return call("sendAudio", payload)


def answer_callback(callback_query_id: str, text: Optional[str] = None) -> Dict[str, Any]:
    """Acknowledge a callback button press."""
    payload: Dict[str, Any] = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    return call("answerCallbackQuery", payload)


def set_webhook(url: str, secret_token: str) -> Dict[str, Any]:
    """Configure the Telegram webhook URL and secret token."""
    payload = {
        "url": url,
        "secret_token": secret_token,
        "allowed_updates": ["message", "callback_query"],
    }
    return call("setWebhook", payload)


def get_webhook_info() -> Dict[str, Any]:
    """Query current webhook configuration status."""
    return call("getWebhookInfo")
