"""
tools/check_wallet_balance.py

Reads the storefront's platform wallet balance (e.g. Zepto Cash) directly
from the account/settings page, so the agent can answer "how much Zepto
Cash do I have" or check funds before checkout without needing anything in
the cart at all.

Zepto's path replaces an earlier version that tried to reach the balance by
advancing a cart through checkout to the payment-method screen — that path
was never verified live (it sits right at the boundary of real settlement)
and turned out to be unnecessary anyway: the storefront's own /account page
shows the balance directly, with no cart or checkout involved.

Blinkit is different, confirmed live: Blinkit Money is app-exclusive. It
doesn't appear on /account or /account/wallet, and it doesn't appear on
the web payment-method screen either — that screen only ever offers
Wallets (empty on web), cards, Netbanking, UPI, Cash, and Pay Later (see
checkout.py's docstring for a screenshot-confirmed rundown). An earlier
version of this file guessed the payment screen would show a Blinkit Money
balance the account pages didn't — that guess was tested against real
screenshots and turned out wrong, so it's gone; don't reintroduce a
payment-screen scrape for a Blinkit wallet balance without new evidence
that it's actually there.

Given that, check_wallet_balance always reports Blinkit Money as
"not_found" rather than trying account paths that are known not to show
it. checkout.py handles the Blinkit case for real: payment_method=
"blinkit_money" reports insufficient balance immediately (it can't be
paid from a wallet that doesn't exist on web), and payment_method="upi"
drives the actual working payment path (UPI QR code) instead.

The actual work happens in _check_wallet_balance_impl, run on the single
dedicated Playwright thread via run_on_playwright_thread — see
tools/_session.py's module docstring for why that's required (not
optional) whenever a tool touches a Page.
"""

import re

from strands import tool

from tools._session import PLATFORMS, get_page, run_on_playwright_thread

_BALANCE_RE = re.compile(
    r"(available balance|wallet balance)\s*:?\s*₹\s?([\d,]+(?:\.\d+)?)", re.IGNORECASE
)


@tool
def check_wallet_balance(platform: str = "zepto") -> dict:
    """
    Read the storefront's platform wallet balance (e.g. Zepto Cash) from
    the account page. Use this to answer a balance question directly, or
    to check there's enough funds before calling checkout.

    Args:
        platform: Which storefront — "zepto" (default) or "blinkit".
            Blinkit Money is confirmed app-exclusive (not reachable on the
            web storefront at all), so this always returns "not_found" for
            platform="blinkit" — don't retry it or treat it as a transient
            failure. For Blinkit, skip straight to
            checkout(payment_method="upi") instead of trying to fund or
            verify a wallet balance first.

    Returns:
        A dict with status ("ok", "not_found", or "error") and, on
        success, "wallet" (e.g. "Zepto Cash & Gift Card") and "balance"
        (float).
    """
    return run_on_playwright_thread(_check_wallet_balance_impl, platform)


def _check_wallet_balance_impl(platform: str) -> dict:
    if platform not in PLATFORMS:
        return {"status": "error", "error": f"Unknown platform {platform!r} — use one of {list(PLATFORMS)}."}

    if platform == "blinkit":
        return {
            "status": "not_found",
            "error": (
                "Blinkit Money is app-exclusive — confirmed not reachable on Blinkit's web "
                "storefront (not on /account, not on the web payment-method screen). Use "
                "checkout(platform='blinkit', payment_method='upi') to pay instead."
            ),
        }

    storefront_url = PLATFORMS[platform]["url"]
    page = get_page(platform)
    try:
        page.goto(f"{storefront_url}/account", wait_until="domcontentloaded", timeout=40000)
        page.wait_for_selector("text=Available Balance", timeout=10000)
        body = page.evaluate("() => document.body.innerText")
        match = _BALANCE_RE.search(body)
        if not match:
            return {"status": "error", "error": "Could not find a balance on the account page."}
        wallet_line = next(
            (l for l in body.split("\n") if "cash" in l.lower() or "gift card" in l.lower()), "Zepto Cash"
        )
        return {"status": "ok", "wallet": wallet_line.strip(), "balance": float(match.group(2).replace(",", ""))}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
