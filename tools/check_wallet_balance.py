"""
tools/check_wallet_balance.py

Reads the storefront's platform wallet balance (e.g. Zepto Cash) directly
from the account/settings page, so the agent can answer "how much Zepto
Cash do I have" or check funds before checkout without needing anything in
the cart at all.

This replaces an earlier version that tried to reach the balance by
advancing a cart through checkout to the payment-method screen — that path
was never verified live (it sits right at the boundary of real settlement)
and turned out to be unnecessary anyway: the storefront's own /account page
shows the balance directly, with no cart or checkout involved.
"""

import re

from strands import tool

from tools._session import STOREFRONT_URL, get_page

_BALANCE_RE = re.compile(r"available balance:\s*₹\s?([\d,]+(?:\.\d+)?)", re.IGNORECASE)


@tool
def check_wallet_balance() -> dict:
    """
    Read the storefront's platform wallet balance (e.g. Zepto Cash) from
    the account page. Use this to answer a balance question directly, or
    to check there's enough funds before calling checkout.

    Returns:
        A dict with status ("ok" or "error") and, on success, "wallet"
        (e.g. "Zepto Cash & Gift Card") and "balance" (float).
    """
    page = get_page()
    try:
        page.goto(f"{STOREFRONT_URL}/account", wait_until="domcontentloaded", timeout=40000)
        page.wait_for_selector("text=Available Balance", timeout=10000)

        body = page.evaluate("() => document.body.innerText")
        match = _BALANCE_RE.search(body)
        if not match:
            return {"status": "error", "error": "Could not find a balance on the account page."}

        wallet_line = next((l for l in body.split("\n") if "cash" in l.lower() or "gift card" in l.lower()), "Zepto Cash")

        return {"status": "ok", "wallet": wallet_line.strip(), "balance": float(match.group(1).replace(",", ""))}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
