"""
tools/remove_from_cart.py

Removes (or reduces the quantity of) a product already in the cart.

Zepto's path is not a port — worked out directly against the live
storefront. The cart drawer's own line items don't expose an easily
reachable quantity stepper (unlike a product page's, which carries a clean
aria-labelled "Decrease quantity by one" button) — but decreasing on the
product page updates the same live cart via the site's SPA state, so that's
the reliable path used here instead of fighting the cart drawer's DOM.

Blinkit support (added for the Strands port) follows the same shape — go
to the product page, click the stepper's '-' down to zero — but via
tools/_session.py's glyph-based stepper_click instead of Zepto's confirmed
aria-label, since Blinkit's stepper carries no aria-label at all.
"""

import re

from strands import tool

from tools._session import PLATFORMS, get_page, stepper_click


@tool
def remove_from_cart(product_url: str, quantity: int = 0, platform: str = "zepto") -> dict:
    """
    Remove a product from the cart, or reduce its quantity.

    Args:
        product_url: The storefront product path, as returned by
            search_products or add_to_cart — e.g.
            "/pn/fortune-chakki-fresh-atta/pvid/...".
        quantity: How many units to remove. 0 (default) removes it
            entirely, however many units are in the cart.
        platform: Which storefront this product_url is from — "zepto"
            (default) or "blinkit".

    Returns:
        A dict with status ("ok" or "error"), the item's "name", how many
        units were actually removed ("removed"), and whether it's now fully
        "cleared" from the cart. Call view_cart afterwards to confirm the
        cart's new contents/total.
    """
    if platform not in PLATFORMS:
        return {"status": "error", "error": f"Unknown platform {platform!r} — use one of {list(PLATFORMS)}."}

    storefront_url = PLATFORMS[platform]["url"]
    page = get_page(platform)
    try:
        full_url = product_url if product_url.startswith("http") else f"{storefront_url}{product_url}"
        page.goto(full_url, wait_until="domcontentloaded", timeout=40000)
        page.wait_for_timeout(1000)

        if platform == "zepto":
            decrease = page.get_by_role("button", name="Decrease quantity by one")
            visible = decrease.is_visible()
        else:
            visible = None  # checked per-click below via stepper_click's return value

        if platform == "zepto" and not visible:
            return {"status": "ok", "removed": 0, "cleared": True, "note": "Item was not in the cart."}

        name_el = page.query_selector('h1, [class*="product-name"], [class*="productName"]')
        name = name_el.inner_text().strip() if name_el else None

        removed = 0
        max_clicks = quantity if quantity > 0 else 50  # safety cap for "remove all"

        if platform == "zepto":
            while decrease.is_visible() and removed < max_clicks:
                decrease.click()
                page.wait_for_timeout(400)
                removed += 1
            cleared = not decrease.is_visible()
        else:
            while removed < max_clicks:
                if not stepper_click(page, increase=False):
                    break
                page.wait_for_timeout(400)
                removed += 1
            if removed == 0:
                return {"status": "ok", "removed": 0, "cleared": True, "note": "Item was not in the cart."}
            # Best-effort: after decrementing, the '+'/'−' stepper being gone
            # again usually means it dropped back to a bare "Add" button.
            try:
                cleared = not page.get_by_role(
                    "button", name=re.compile("increase quantity", re.I)
                ).first.is_visible()
            except Exception:
                cleared = removed >= max_clicks and quantity == 0

        return {"status": "ok", "name": name, "removed": removed, "cleared": cleared}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
