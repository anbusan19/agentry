"""
tools/check_wallet_balance.py

Advances the cart to the payment-method screen and reads off the platform
wallet's balance (e.g. Zepto Cash), without selecting a payment method or
placing the order. Lets the agent answer "do I have enough Zepto Cash for
this?" before committing to checkout.

NOTE: the click from the cart's "Click to Pay" screen through to the
payment-method list was not verified against the live site — testing
stopped there deliberately, since that button sits right at the boundary
of the storefront's real checkout flow. Confirm this against a real cart
before relying on it.
"""

import re

from strands import tool

from tools._session import STOREFRONT_URL, get_page, js_click

_BALANCE_RE = re.compile(r"(zepto cash|zepto wallet)[^\d₹]*₹\s?([\d,]+(?:\.\d+)?)", re.IGNORECASE)


@tool
def check_wallet_balance() -> dict:
    """
    Advance the current cart to the payment-method screen and read the
    storefront's platform wallet balance (e.g. Zepto Cash), without
    selecting it or placing the order. Use this to check whether there's
    enough balance before calling checkout.

    Returns:
        A dict with status ("ok", "no_wallet", or "error"), and on "ok" a
        "balance" float and "wallet" name. On "no_wallet", the cart reached
        the payment screen but no platform wallet option was found.
    """
    page = get_page()
    try:
        page.goto(f"{STOREFRONT_URL}?cart=open", wait_until="domcontentloaded", timeout=40000)
        page.wait_for_selector("text=Bill Summary", timeout=10000)

        # A delivery slot may need to be scheduled before payment options unlock.
        js_click(page, "select delivery options|schedule delivery")
        page.wait_for_timeout(1500)
        if page.locator("text=Schedule your order").is_visible():
            page.locator("button, div").filter(has_text=re.compile(r"^\d{1,2}\s*-\s*\d{1,2}\s*(AM|PM)$")).first.click()
            page.wait_for_timeout(500)
            js_click(page, r"^confirm$")
            page.wait_for_timeout(1500)

        js_click(page, r"click to pay|proceed to pay")
        page.wait_for_timeout(2000)

        body = page.evaluate("() => document.body.innerText")
        match = _BALANCE_RE.search(body)
        if not match:
            return {"status": "no_wallet", "note": "No platform wallet balance found on the payment screen."}

        return {"status": "ok", "wallet": match.group(1), "balance": float(match.group(2).replace(",", ""))}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
