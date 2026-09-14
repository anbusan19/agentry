"""
tools/view_cart.py

Reads back the current cart contents and bill total, without touching
checkout. Lets the agent (or, through it, the user) ask "what's in my cart
right now" or confirm a total before committing to checkout.

Zepto's path is not a port — the original prototype folded cart-reading
into its combined order pipeline rather than exposing it standalone. The
scraping approach here (slice the cart drawer's plain text between the
"Coupons & offers" and "Bill Summary" markers, then parse item lines) was
worked out directly against the live storefront, which renders the cart as
full-page content under a `?cart=open` query flag rather than a real modal.

Blinkit support (added for the Strands port) was confirmed live: /cart is
a real, directly-navigable page (checked by loading it after adding an
item), so this goes straight there rather than hunting for a "view cart"
click target from the home page. Its bill section reads "Items total" for
the item-only subtotal (price *after* the label, like Zepto) but "TOTAL"
for the final payable amount has the price *before* the label
("₹107\nTOTAL", not "TOTAL\n₹107") — confirmed against a real cart with one
item — so the generic total regex below checks both orders.
"""

import re

from strands import tool

from tools._session import PLATFORMS, get_page

_WEIGHT_RE = re.compile(r"^\d+\s*(pack|pc|pcs)\b.*\(", re.IGNORECASE)
_PRICE_RE = re.compile(r"^₹\s?[\d,.]+$")


def _parse_items(section: str) -> list[dict]:
    lines = [l.strip() for l in section.split("\n") if l.strip()]

    items = []
    for i, line in enumerate(lines):
        if not _WEIGHT_RE.match(line):
            continue
        name = lines[i - 1] if i > 0 else None
        if not name:
            continue

        prices = [l for l in lines[i + 1 : i + 5] if _PRICE_RE.match(l)]
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


_WEIGHT_LINE_RE = re.compile(r"^\d+\.?\d*\s*(ml|g|kg|l|ltr|litre|pack|pc|pcs)\b", re.IGNORECASE)


def _parse_items_generic(body: str) -> list[dict]:
    """Blinkit cart item parse. Confirmed against a real one-item cart,
    whose full body reads (line per \\n):
        My Cart / Share / Delivery in 10 minutes / Shipment of 1 item /
        Amul Gold Tricone Butterscotch Ice Cream Cone / 120 ml / ₹40 / U /
        1 / 5 / Bill details / Items total / ₹40 / Delivery charge / ₹30 /
        Handling charge / ₹7 / Small cart charge / ₹30 / Grand total /
        ₹107 / Feeding India donation / ... / ₹1 / Tip your delivery
        partner / ... / ₹20 / ₹30 / ₹50 / Custom / Cancellation Policy /
        ... / ₹107 / TOTAL / Proceed
    Everything from "Bill details" onward is charges/donation/tip/policy
    text, not items — a naive whole-body scan for "name near a ₹price"
    misreads several of those lines as items (the tip suggestion chips, the
    cancellation-policy paragraph). So this only scans the slice between
    "Shipment of N item" and "Bill details", which is where the actual line
    items live."""
    start = body.find("Shipment of")
    end = body.find("Bill details")
    section = body[start:end] if start != -1 and end != -1 and end > start else body

    lines = [l.strip() for l in section.split("\n") if l.strip()]
    items = []
    seen_names = set()
    for i, line in enumerate(lines):
        if _PRICE_RE.match(line) or not line or len(line) < 3:
            continue
        if re.match(r"^shipment of \d+ items?$", line, re.I) or _WEIGHT_LINE_RE.match(line):
            continue
        nearby = lines[i + 1 : i + 4]
        prices = [l for l in nearby if _PRICE_RE.match(l)]
        if not prices or line in seen_names:
            continue
        qty_line = next((l for l in nearby if l.isdigit() and int(l) < 50), None)
        seen_names.add(line)
        items.append({"name": line, "quantity": int(qty_line) if qty_line else 1, "price": prices[-1]})
    return items


@tool
def view_cart(platform: str = "zepto") -> dict:
    """
    Read the current cart contents and total, without proceeding to
    checkout. Use this to confirm what's in the cart or to answer a user's
    question about their current order before calling checkout.

    Args:
        platform: Which storefront — "zepto" (default) or "blinkit". Both
            verified against a live logged-in session.

    Returns:
        A dict with status ("ok" or "error"), "items" (list of
        {name, quantity, price}), and "total" (the amount payable, e.g.
        "₹83" — this already reflects delivery/handling fees and discounts).
    """
    if platform not in PLATFORMS:
        return {"status": "error", "error": f"Unknown platform {platform!r} — use one of {list(PLATFORMS)}."}

    storefront_url = PLATFORMS[platform]["url"]
    page = get_page(platform)
    try:
        if platform == "zepto":
            page.goto(f"{storefront_url}?cart=open", wait_until="domcontentloaded", timeout=40000)
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

        # Blinkit: /cart is directly navigable, confirmed live.
        page.goto(f"{storefront_url}/cart", wait_until="domcontentloaded", timeout=40000)
        page.wait_for_timeout(1500)

        body = page.evaluate("() => document.body.innerText")
        if not re.search(r"(total|to pay)", body, re.I):
            return {"status": "ok", "items": [], "total": "₹0", "note": "Cart appears to be empty (no bill total found)."}

        items = _parse_items_generic(body)
        # Try "Grand total"/"To Pay" (label-then-price) first — a bare
        # "total" pattern would wrongly match inside "Items total" (the
        # item-only subtotal, not what's payable) since that appears
        # earlier in the bill. Fall back to Blinkit's final "₹107\nTOTAL",
        # which has the price *before* the all-caps label instead of after.
        total_match = (
            re.search(r"(grand total|to pay)\D{0,20}?(₹\s?[\d,.]+)", body, re.I)
            or re.search(r"(₹\s?[\d,.]+)\D{0,10}?\bTOTAL\b", body)
        )
        total = None
        if total_match:
            total = next((g for g in total_match.groups() if g and g.startswith("₹")), None)

        if not items:
            return {"status": "ok", "items": [], "total": total, "note": "Cart appears to be empty."}
        return {"status": "ok", "items": items, "total": total}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
