"""
tools/checkout.py

Completes the current cart's checkout: schedules a delivery slot if needed,
selects the platform wallet (e.g. Zepto Cash), and places the order. This is
the only tool in the project that can spend real money, so it requires an
explicit confirm=True — the agent must have a real reason to believe the
user wants this specific order placed (a fresh check_wallet_balance/
view_cart in the same turn, or an explicit user instruction) before passing
it, never as a default.

Ported from the pre-existing prototype this hackathon submission builds on
(see README's Disclosure section) for the address/wallet-selection/place-
order sequence, then adapted to the current site's actual DOM (data-testid
selectors, aria-labelled stepper buttons, and a delivery-slot-scheduling
step the original didn't need to handle).

NOTE: the path from "Click to Pay" through wallet selection to a placed
order was not exercised against a live cart during development — that
click sits right at the boundary of real settlement, and testing stopped
short of it deliberately. Verify this against a real cart with a small
order before trusting it unattended.
"""

import re

from strands import tool

from tools._session import STOREFRONT_URL, get_page, js_click


@tool
def checkout(confirm: bool = False) -> dict:
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

    Returns:
        A dict with status ("paid", "wallet_not_available", "not_confirmed",
        or "error"), and on "paid" an "amount_paid" float and "order_id".
    """
    if not confirm:
        return {
            "status": "not_confirmed",
            "note": "checkout requires confirm=True — nothing was done.",
        }

    page = get_page()
    try:
        page.goto(f"{STOREFRONT_URL}?cart=open", wait_until="domcontentloaded", timeout=40000)
        page.wait_for_selector("text=Bill Summary", timeout=10000)

        js_click(page, "select delivery options|schedule delivery")
        page.wait_for_timeout(1500)
        if page.locator("text=Schedule your order").is_visible():
            page.locator("button, div").filter(has_text=re.compile(r"^\d{1,2}\s*-\s*\d{1,2}\s*(AM|PM)$")).first.click()
            page.wait_for_timeout(500)
            js_click(page, r"^confirm$")
            page.wait_for_timeout(1500)

        js_click(page, r"click to pay|proceed to pay")
        page.wait_for_timeout(2000)

        wallet_selected = page.evaluate(
            """() => {
                const inputs = Array.from(document.querySelectorAll('input[type="radio"], input[type="checkbox"]'));
                for (const inp of inputs) {
                    const label = inp.closest('label') || inp.parentElement;
                    if (/zepto cash|zepto wallet|wallet balance/i.test(label?.textContent?.trim() ?? '')) {
                        inp.click();
                        return true;
                    }
                }
                const el = Array.from(document.querySelectorAll('div, label, button, span, [role="radio"], [role="checkbox"]')).find(
                    e => /zepto cash|zepto wallet|wallet balance/i.test(e.textContent?.trim() ?? '') && e.offsetParent !== null
                );
                if (el) { el.click(); return true; }
                return false;
            }"""
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
        return {
            "status": "paid",
            "amount_paid": float(match.group(0)) if match else None,
            "order_id": f"ZP-{confirmation['orderId']}" if confirmation.get("orderId") else None,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
