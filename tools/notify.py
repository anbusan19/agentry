"""
tools/notify.py

Telegram notification tool for Agentry.

Adapted from the Telegram integration in the pre-existing prototype this
hackathon submission builds on (see README's Disclosure section). That
version ran a full bot with inbound commands (/order, /search, /budget, ...);
Agentry only needs the agent to speak, not listen, so this is a plain
outbound call to the Bot API's sendMessage endpoint instead of a bot process.
"""

import os

import requests
from strands import tool

TELEGRAM_API_BASE = "https://api.telegram.org"


@tool
def notify_user(message: str) -> str:
    """
    Send a Telegram message to the user.

    Use this when a real decision is needed (an item is out of stock, a price
    jumped, a substitution needs a human call) or to report that an order is
    complete. Don't use it for routine step-by-step narration.

    Args:
        message: The plain-text message to send. Keep it short and specific.

    Returns:
        A short status string confirming the message was sent, or an error
        description if it wasn't.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        return (
            "notify_user failed: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set "
            "in the environment — message not sent."
        )

    url = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"
    try:
        response = requests.post(
            url,
            json={"chat_id": chat_id, "text": message},
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"notify_user failed: {exc}"

    return "Message sent to user via Telegram."
