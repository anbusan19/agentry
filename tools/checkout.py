"""
tools/checkout.py

Completes the current cart's checkout: schedules a delivery slot if needed,
selects the platform wallet (e.g. Zepto Cash), and places the order. This is
the only tool in the project that can spend real money, so it requires an
explicit confirm=True — the agent must have a real reason to believe the
user wants this specific order placed (a fresh check_wallet_balance/
view_cart in the same turn, or an explicit user instruction) before passing
it, never as a default.

Zepto's path was ported from the pre-existing prototype this hackathon
submission builds on (see README's Disclosure section) for the address/
wallet-selection/place-order sequence, then adapted to the current site's
actual DOM (data-testid selectors, aria-labelled stepper buttons, and a
delivery-slot-scheduling step the original didn't need to handle).

NOTE: the path from "Click to Pay" through wallet selection to a placed
order was not exercised against a live cart during development — that
click sits right at the boundary of real settlement, and testing stopped
short of it deliberately. Verify this against a real cart with a small
order before trusting it unattended, on Zepto or the newer platforms below.

Blinkit support (added for the Strands port) follows the same shape — open
the cart, schedule a slot if one is offered, pay, pick the platform wallet,
place the order. Its cart is opened via the confirmed-live /cart URL (see
view_cart.py) rather than hunting for a "view cart" click target, but
everything past that point (delivery scheduling, wallet selection, placing
the order) uses the generic click/text heuristics already in this project
(js_click, a widened wallet-name pattern covering "Blinkit Money") rather
than Zepto-confirmed selectors, since it hasn't been run against a live
cart all the way through to a placed order. Given the irreversible,
spends-real-money nature of this tool, do not call it with confirm=True on
Blinkit without deliberately testing the whole flow (small cart, watched
run, headless=False) first.

The actual work happens in _checkout_impl, run on the single dedicated
Playwright thread via run_on_playwright_thread — see tools/_session.py's
module docstring for why that's required (not optional) whenever a tool
touches a Page.
"""

import re

from strands import tool

from knowledge.budget import record_spend
from tools._session import PLATFORMS, get_page, js_click, run_on_playwright_thread

_WALLET_PATTERN = (
    r"zepto cash|zepto wallet|blinkit money|"
    r"wallet balance|platform cash|gift card"
)


@tool
def checkout(confirm: bool = False, platform: str = "zepto") -> dict:
    """
    Complete checkout for whatever is currently in the cart: schedule a
    delivery slot if one is required, pay with the storefront's platform
    wallet (e.g. Zepto Cash), and place the order. This spends real money.

    Only call this with confirm=True, and only when there's a clear reason
    to believe this exact order (checked via view_cart / check_wallet_balance
    moments earlier) is what the user wants placed right now.

    Args:
        confirm: Must be explicitly True to do anything. Defaults to False
            so an accidental or speculative call can't place an order.
        platform: Which storefront — "zepto" (default) or "blinkit". The
            path through wallet selection to a placed order hasn't been
            run end-to-end on either — be extra cautious calling this with
            confirm=True; consider a small test order run manually first.

    Returns:
        A dict with status ("paid", "wallet_not_available", "not_confirmed",
        or "error"), and on "paid" an "amount_paid" float and "order_id".
    """
    return run_on_playwright_thread(_checkout_impl, confirm, platform)


def _checkout_impl(confirm: bool, platform: str) -> dict:
    if not confirm:
        return {
            "status": "not_confirmed",
            "note": "checkout requires confirm=True — nothing was done.",
        }
    if platform not in PLATFORMS:
        return {"status": "error", "error": f"Unknown platform {platform!r} — use one of {list(PLATFORMS)}."}

    storefront_url = PLATFORMS[platform]["url"]
    page = get_page(platform)
    try:
        if platform == "zepto":
            page.goto(f"{storefront_url}?cart=open", wait_until="domcontentloaded", timeout=40000)
            page.wait_for_selector("text=Bill Summary", timeout=10000)
        else:
            # Blinkit: /cart is directly navigable, confirmed live (see
            # view_cart.py).
            page.goto(f"{storefront_url}/cart", wait_until="domcontentloaded", timeout=40000)
            page.wait_for_timeout(1200)

        js_click(page, "select delivery options|schedule delivery")
        page.wait_for_timeout(1500)
        if page.locator("text=Schedule your order").is_visible():
            page.locator("button, div").filter(has_text=re.compile(r"^\d{1,2}\s*-\s*\d{1,2}\s*(AM|PM)$")).first.click()
            page.wait_for_timeout(500)
            js_click(page, r"^confirm$")
            page.wait_for_timeout(1500)

        js_click(page, r"click to pay|proceed to pay|place order")
        page.wait_for_timeout(2000)

        wallet_selected = page.evaluate(
            """(pattern) => {
                const re = new RegExp(pattern, 'i');
                const inputs = Array.from(document.querySelectorAll('input[type="radio"], input[type="checkbox"]'));
                for (const inp of inputs) {
                    const label = inp.closest('label') || inp.parentElement;
                    if (re.test(label?.textContent?.trim() ?? '')) {
                        inp.click();
                        return true;
                    }
                }
                const el = Array.from(document.querySelectorAll('div, label, button, span, [role="radio"], [role="checkbox"]')).find(
                    e => re.test(e.textContent?.trim() ?? '') && e.offsetParent !== null
                );
                if (el) { el.click(); return true; }
                return false;
            }""",
            _WALLET_PATTERN,
        )
        page.wait_for_timeout(1000)

        if not wallet_selected:
            return {"status": "wallet_not_available", "note": "No platform wallet option found — order was not placed."}

        placed = js_click(page, r"place order|pay now|confirm order|pay ₹")
        if not placed:
            return {"status": "error", "error": "Could not find the Place Order / Pay Now button."}

        page.wait_for_timeout(5000)

        confirmation = page.evaluate(
            """() => {
                const idText = document.body.innerText.match(/#?([A-Z0-9]{6,20})/)?.[1];
                const total = document.querySelector('[class*="total" i], [class*="amount" i]');
                return { orderId: idText || null, total: total?.textContent?.trim().slice(0, 30) || null };
            }"""
        )

        current_url = page.url
        is_confirmed = (
            "order" in current_url
            or "success" in current_url
            or "confirmed" in current_url
            or page.locator("text=/order placed|order confirmed|on the way/i").is_visible()
        )
        if not is_confirmed:
            return {"status": "error", "error": f"Order placement may have failed. URL: {current_url}"}

        match = re.search(r"[\d.]+", confirmation.get("total") or "")
        amount_paid = float(match.group(0)) if match else None
        if amount_paid is not None:
            record_spend(amount_paid)

        order_prefix = {"zepto": "ZP", "blinkit": "BL"}.get(platform, platform.upper())
        return {
            "status": "paid",
            "amount_paid": amount_paid,
            "order_id": f"{order_prefix}-{confirmation['orderId']}" if confirmation.get("orderId") else None,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
