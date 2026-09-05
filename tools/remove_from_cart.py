"""
tools/remove_from_cart.py

Removes (or reduces the quantity of) a product already in the cart.

Not a port — worked out directly against the live storefront. The cart
drawer's own line items don't expose an easily reachable quantity stepper
(unlike a product page's, which carries a clean aria-labelled
"Decrease quantity by one" button) — but decreasing on the product page
updates the same live cart via the site's SPA state, so that's the
reliable path used here instead of fighting the cart drawer's DOM.
"""

from strands import tool

from tools._session import STOREFRONT_URL, get_page


@tool
def remove_from_cart(product_url: str, quantity: int = 0) -> dict:
    """
    Remove a product from the cart, or reduce its quantity.

    Args:
        product_url: The storefront product path, as returned by
            search_products or add_to_cart — e.g.
            "/pn/fortune-chakki-fresh-atta/pvid/...".
        quantity: How many units to remove. 0 (default) removes it
            entirely, however many units are in the cart.

    Returns:
        A dict with status ("ok" or "error"), the item's "name", how many
        units were actually removed ("removed"), and whether it's now fully
        "cleared" from the cart. Call view_cart afterwards to confirm the
        cart's new contents/total.
    """
    page = get_page()
    try:
        full_url = product_url if product_url.startswith("http") else f"{STOREFRONT_URL}{product_url}"
        page.goto(full_url, wait_until="domcontentloaded", timeout=40000)
        page.wait_for_timeout(1000)

        decrease = page.get_by_role("button", name="Decrease quantity by one")
        if not decrease.is_visible():
            return {"status": "ok", "removed": 0, "cleared": True, "note": "Item was not in the cart."}

        name_el = page.query_selector('h1, [class*="product-name"], [class*="productName"]')
        name = name_el.inner_text().strip() if name_el else None

        removed = 0
        max_clicks = quantity if quantity > 0 else 50  # safety cap for "remove all"
        while decrease.is_visible() and removed < max_clicks:
            decrease.click()
            page.wait_for_timeout(400)
            removed += 1

        return {"status": "ok", "name": name, "removed": removed, "cleared": not decrease.is_visible()}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
