"""
tools/view_cart.py

Reads back the current cart contents and bill total, without touching
checkout. Lets the agent (or, through it, the user) ask "what's in my cart
right now" or confirm a total before committing to checkout.

Not a port — the original prototype folded cart-reading into its combined
order pipeline rather than exposing it standalone. The scraping approach
here (slice the cart drawer's plain text between the "Coupons & offers" and
"Bill Summary" markers, then parse item lines) was worked out directly
against the live storefront, which renders the cart as full-page content
under a `?cart=open` query flag rather than a real modal.
"""

import re

from strands import tool

from tools._session import STOREFRONT_URL, get_page


def _parse_items(section: str) -> list[dict]:
    lines = [l.strip() for l in section.split("\n") if l.strip()]
    weight_re = re.compile(r"^\d+\s*(pack|pc|pcs)\b.*\(", re.IGNORECASE)
    price_re = re.compile(r"^₹\s?[\d,.]+$")

    items = []
    for i, line in enumerate(lines):
        if not weight_re.match(line):
            continue
        name = lines[i - 1] if i > 0 else None
        if not name:
            continue

        prices = [l for l in lines[i + 1 : i + 5] if price_re.match(l)]
        qty_line = next((l for l in lines[i + 1 : i + 5] if l.isdigit()), None)

        items.append(
            {
                "name": name,
                "quantity": int(qty_line) if qty_line else 1,
                # last price after MRP-strikethrough is the payable one
                "price": prices[-1] if prices else None,
            }
        )
    return items


@tool
def view_cart() -> dict:
    """
    Read the current cart contents and total, without proceeding to
    checkout. Use this to confirm what's in the cart or to answer a user's
    question about their current order before calling checkout.

    Returns:
        A dict with status ("ok" or "error"), "items" (list of
        {name, quantity, price}), and "total" (the amount payable, e.g.
        "₹83" — this already reflects delivery/handling fees and discounts).
    """
    page = get_page()
    try:
        page.goto(f"{STOREFRONT_URL}?cart=open", wait_until="domcontentloaded", timeout=40000)
        try:
            page.wait_for_selector("text=Bill Summary", timeout=8000)
        except Exception:
            # An empty cart doesn't open a drawer at all — it just leaves you
            # on the home page. Absence of "Bill Summary" means empty, not
            # broken.
            return {"status": "ok", "items": [], "total": "₹0", "note": "Cart is empty."}
        page.wait_for_timeout(500)

        sections = page.evaluate(
            """() => {
                const body = document.body.innerText;
                const itemsStart = body.indexOf('Coupons & offers');
                const billStart = body.indexOf('Bill Summary');
                return {
                    items: (itemsStart !== -1 && billStart !== -1) ? body.slice(itemsStart, billStart) : '',
                    bill: billStart !== -1 ? body.slice(billStart, billStart + 400) : '',
                };
            }"""
        )

        items = _parse_items(sections["items"])

        to_pay_match = re.search(r"To Pay\n([^\n]*\n)?(₹[\d,.]+)", sections["bill"])
        total = to_pay_match.group(2) if to_pay_match else None

        if not items:
            return {"status": "ok", "items": [], "total": total, "note": "Cart appears to be empty."}

        return {"status": "ok", "items": items, "total": total}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
