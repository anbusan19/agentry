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

Blinkit support (added for the Strands port) tries a short list of likely
account-page paths — /account (confirmed live, links to "Wallet Details")
and /account/wallet (confirmed as the real route the "Wallet Details" link
goes to) — and a wider wallet-name pattern, since Blinkit doesn't advertise
a Zepto-Cash-style wallet as prominently. Whether it actually renders a
balance line there is still unconfirmed (the wallet page loaded but never
showed balance text in testing — inconclusive, not "broken"). If none of
the candidate pages show a recognizable balance line, this returns a clear
"not_found" rather than a guessed number.
"""

import re

from strands import tool

from tools._session import PLATFORMS, get_page

_BALANCE_RE = re.compile(
    r"(available balance|wallet balance)\s*:?\s*₹\s?([\d,]+(?:\.\d+)?)", re.IGNORECASE
)

ACCOUNT_PATHS = {
    "zepto": ["/account"],
    "blinkit": ["/account", "/account/wallet"],
}


@tool
def check_wallet_balance(platform: str = "zepto") -> dict:
    """
    Read the storefront's platform wallet balance (e.g. Zepto Cash) from
    the account page. Use this to answer a balance question directly, or
    to check there's enough funds before calling checkout.

    Args:
        platform: Which storefront — "zepto" (default) or "blinkit". If
            Blinkit turns out not to expose a platform-wallet balance the
            way Zepto does, this will come back "not_found" rather than a
            made-up number.

    Returns:
        A dict with status ("ok", "not_found", or "error") and, on success,
        "wallet" (e.g. "Zepto Cash & Gift Card") and "balance" (float).
    """
    if platform not in PLATFORMS:
        return {"status": "error", "error": f"Unknown platform {platform!r} — use one of {list(PLATFORMS)}."}

    storefront_url = PLATFORMS[platform]["url"]
    page = get_page(platform)
    try:
        if platform == "zepto":
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

        # Blinkit: try each candidate account path until one shows a
        # recognizable balance line.
        for path in ACCOUNT_PATHS.get(platform, ["/account"]):
            try:
                page.goto(f"{storefront_url}{path}", wait_until="domcontentloaded", timeout=40000)
                page.wait_for_timeout(1500)
                body = page.evaluate("() => document.body.innerText")
                match = _BALANCE_RE.search(body)
                if match:
                    wallet_line = next(
                        (
                            l
                            for l in body.split("\n")
                            if any(k in l.lower() for k in ("cash", "gift card", "wallet", "money"))
                        ),
                        "Wallet",
                    )
                    return {
                        "status": "ok",
                        "wallet": wallet_line.strip(),
                        "balance": float(match.group(2).replace(",", "")),
                    }
            except Exception:
                continue

        return {
            "status": "not_found",
            "error": (
                f"No recognizable wallet balance found on {platform}'s account page(s). "
                "This platform may not expose a platform-wallet balance the way Zepto does, "
                "or the account page path/markup differs from what was guessed here."
            ),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
