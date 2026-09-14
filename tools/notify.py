"""
tools/notify.py

Telegram notification tool for Agentry.

Adapted from the Telegram integration in the pre-existing prototype this
hackathon submission builds on (see README's Disclosure section). That
version ran a full bot with inbound commands (/order, /search, /budget, ...);
Agentry only needs the agent to speak, not listen, so this is a plain
outbound call to the Bot API's sendMessage/sendPhoto endpoints instead of a
bot process.

image_path was added for checkout()'s Blinkit UPI path: since Blinkit Money
is app-exclusive (see checkout.py), the only way to actually get money to
Blinkit through this project is a UPI QR code the user scans themselves,
and a QR code sent as plain text is useless — the user needs the actual
image. Uses sendPhoto (multipart) instead of sendMessage when image_path is
given; falls back to a text-only message with a note if the file is
missing rather than silently sending nothing.
"""

import os
from pathlib import Path

import requests
from strands import tool

TELEGRAM_API_BASE = "https://api.telegram.org"


@tool
def notify_user(message: str, image_path: str = "") -> str:
    """
    Send a Telegram message to the user, optionally with an image attached.

    Use this when a real decision is needed (an item is out of stock, a price
    jumped, a substitution needs a human call), to report that an order is
    complete, or to hand the user a UPI QR code to pay (checkout's
    "awaiting_manual_payment" result gives you a qr_image_path — pass it
    here as image_path so the user can actually see and scan it). Don't use
    it for routine step-by-step narration.

    Args:
        message: The plain-text message to send. Keep it short and specific.
            Used as the photo caption when image_path is given.
        image_path: Optional path to a local image file (e.g. a UPI QR
            screenshot from checkout) to send along with the message. Omit
            for a plain text message.

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

    if image_path:
        path = Path(image_path)
        if not path.is_file():
            return f"notify_user failed: image_path {image_path!r} does not exist — nothing was sent."
        url = f"{TELEGRAM_API_BASE}/bot{token}/sendPhoto"
        try:
            with path.open("rb") as photo:
                response = requests.post(
                    url,
                    data={"chat_id": chat_id, "caption": message},
                    files={"photo": photo},
                    timeout=30,
                )
                response.raise_for_status()
        except requests.RequestException as exc:
            return f"notify_user failed: {exc}"
        return "Photo + message sent to user via Telegram."

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
