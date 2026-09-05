"""
tools/add_to_cart.py

Adds one product to the cart, split out of the original combined
browser_automation tool. Takes a product_url (as returned by
search_products) or a plain query to search-and-pick-the-top-result, and
supports a quantity beyond 1 via the storefront's own quantity stepper.

Not a port — worked out directly against the live storefront, whose product
pages carry a plain "Add to Cart" button and, after it's clicked, a
"− N +" quantity stepper.
"""

import re
from urllib.parse import quote

from strands import tool

from tools._session import STOREFRONT_URL, get_page, js_click

_NAME_PRICE_RE = re.compile(r"([^\n]+)\n\nNet quantity[^\n]*\n\n₹\s*\n?\s*([\d,.]+)")


def _read_product_details(page) -> dict:
    body = page.evaluate("() => document.body.innerText")
    match = _NAME_PRICE_RE.search(body)
    if not match:
        return {"name": None, "price": None}
    return {"name": match.group(1).strip(), "price": f"₹{match.group(2)}"}


@tool
def add_to_cart(product_url: str = "", query: str = "", quantity: int = 1) -> dict:
    """
    Add a product to the cart. Provide either product_url (from a prior
    search_products call — preferred, since it's unambiguous) or a plain
    query to search and add the top match.

    Args:
        product_url: A storefront product path, e.g.
            "/pn/fortune-chakki-fresh-atta/pvid/...". Takes priority over
            query if both are given.
        query: What to search for and add, e.g. "amul milk 500ml". Only
            used if product_url is empty.
        quantity: How many units to add (default 1).

    Returns:
        A dict with status ("ok", "not_found", or "error"), and on success
        the item's "name", "price" (per unit), and "quantity" now in cart.
    """
    if not product_url and not query:
        return {"status": "error", "error": "Provide either product_url or query."}

    page = get_page()

    try:
        if product_url:
            full_url = product_url if product_url.startswith("http") else f"{STOREFRONT_URL}{product_url}"
        else:
            page.goto(f"{STOREFRONT_URL}/search?query={quote(query)}", wait_until="domcontentloaded", timeout=40000)
            page.wait_for_selector('[data-testid="product-card"]', timeout=10000)
            href = page.evaluate('() => document.querySelector(\'[data-testid="product-card"]\')?.getAttribute("href")')
            if not href:
                return {"status": "not_found", "error": f'No products found for "{query}"'}
            full_url = f"{STOREFRONT_URL}{href}"

        page.goto(full_url, wait_until="domcontentloaded", timeout=40000)
        page.wait_for_timeout(1200)

        details = _read_product_details(page)

        already_in_cart = page.get_by_role("button", name="Increase quantity by one").is_visible()
        if already_in_cart:
            # Already in the cart at some quantity — treat `quantity` as how
            # many more units to add, rather than guessing the stepper's
            # current value.
            extra_units = quantity
        else:
            clicked = js_click(page, r"^add to cart$")
            if not clicked:
                return {"status": "error", "error": "Could not find an Add to Cart button on this product."}
            page.wait_for_timeout(1000)
            extra_units = quantity - 1  # the Add to Cart click already added one

        for _ in range(max(0, extra_units)):
            page.get_by_role("button", name="Increase quantity by one").click()
            page.wait_for_timeout(400)

        return {
            "status": "ok",
            "name": details["name"],
            "price": details["price"],
            "added": quantity,
            "note": "Already in cart — added more units." if already_in_cart else None,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
