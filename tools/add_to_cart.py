"""
tools/add_to_cart.py

Adds one product to the cart, split out of the original combined
browser_automation tool. Takes a product_url (as returned by
search_products) or a plain query to search-and-pick-the-top-result, and
supports a quantity beyond 1 via the storefront's own quantity stepper.

Zepto's path is not a port — worked out directly against the live
storefront, whose product pages carry a plain "Add to Cart" button and,
after it's clicked, a "− N +" quantity stepper.

Blinkit support (added for the Strands port) was confirmed live: the
product page really does carry a plain "Add to Cart" button (so the
existing js_click pattern needs no change) and a "− N +" stepper once it's
in the cart, but with no aria-label at all — unlike Zepto's — so it uses
tools/_session.py's glyph-based stepper_click instead of a role/name
lookup. "Already in cart" detection also had to change to match: Zepto's
aria-labelled role lookup doesn't exist on Blinkit, so this checks for a
visible bare "+"/"−" glyph button instead.
"""

import re
from urllib.parse import quote

from strands import tool

from tools._session import PLATFORMS, get_page, js_click, scrape_blinkit_results, stepper_click

_NAME_PRICE_RE = re.compile(r"([^\n]+)\n\nNet quantity[^\n]*\n\n₹\s*\n?\s*([\d,.]+)")
_GENERIC_PRICE_RE = re.compile(r"(₹|Rs\.?)\s?([\d,]+(?:\.\d+)?)")

SEARCH_PATH = {
    "zepto": "/search?query={q}",
    "blinkit": "/s/?q={q}",
}


def _read_product_details_zepto(page) -> dict:
    body = page.evaluate("() => document.body.innerText")
    match = _NAME_PRICE_RE.search(body)
    if not match:
        return {"name": None, "price": None}
    return {"name": match.group(1).strip(), "price": f"₹{match.group(2)}"}


_TITLE_NAME_RE = re.compile(r"^Buy (.+?) Online", re.IGNORECASE)


_FOOTER_PRICE_RE = re.compile(r"₹\s?([\d,]+(?:\.\d+)?)\s*\n\s*Inclusive of all taxes", re.IGNORECASE)


def _read_product_details_generic(page) -> dict:
    """Name/price read for a Blinkit product page. Confirmed live: Blinkit
    has no <h1> on the product page at all (checked directly), but
    document.title reliably follows "Buy <name> Online at Best Price |
    Blinkit" — that's the primary source, with a loose text-node fallback
    for anything that doesn't match.

    Price is NOT just "the first ₹ on the page" — that was tried first and
    is wrong: if anything's already in the cart, the page's own sticky
    header cart badge ("1 item / ₹40 / View Cart") renders above the
    product's own price and matches first, so a second add_to_cart call
    would silently report the wrong item's price (confirmed live — a ₹230
    product came back reporting ₹40, the first item's cart-badge total).
    The product's real price sits right above "Inclusive of all taxes" in
    the sticky footer, which is a much more specific anchor."""
    title = page.title() or ""
    match = _TITLE_NAME_RE.match(title)
    name = match.group(1).strip() if match else None
    if not name:
        name = page.evaluate(
            """() => {
                const h1 = document.querySelector('h1');
                if (h1 && h1.textContent.trim()) return h1.textContent.trim();
                return document.title || null;
            }"""
        )
    body = page.evaluate("() => document.body.innerText")
    footer_match = _FOOTER_PRICE_RE.search(body)
    if footer_match:
        price = f"₹{footer_match.group(1)}"
    else:
        price_match = _GENERIC_PRICE_RE.search(body)
        price = f"₹{price_match.group(2)}" if price_match else None
    return {"name": name, "price": price}


@tool
def add_to_cart(product_url: str = "", query: str = "", quantity: int = 1, platform: str = "zepto") -> dict:
    """
    Add a product to the cart. Provide either product_url (from a prior
    search_products call — preferred, since it's unambiguous) or a plain
    query to search and add the top match.

    Args:
        product_url: A storefront product path, e.g.
            "/pn/fortune-chakki-fresh-atta/pvid/...". Takes priority over
            query if both are given. Must be from the same platform.
        query: What to search for and add, e.g. "amul milk 500ml". Only
            used if product_url is empty.
        quantity: How many units to add (default 1).
        platform: Which storefront — "zepto" (default) or "blinkit". Both
            verified against a live logged-in session.

    Returns:
        A dict with status ("ok", "not_found", or "error"), and on success
        the item's "name", "price" (per unit), and "quantity" now in cart.
    """
    if not product_url and not query:
        return {"status": "error", "error": "Provide either product_url or query."}
    if platform not in PLATFORMS:
        return {"status": "error", "error": f"Unknown platform {platform!r} — use one of {list(PLATFORMS)}."}

    storefront_url = PLATFORMS[platform]["url"]
    page = get_page(platform)

    try:
        if product_url:
            full_url = product_url if product_url.startswith("http") else f"{storefront_url}{product_url}"
        else:
            search_path = SEARCH_PATH.get(platform, "/search?query={q}").format(q=quote(query))
            page.goto(f"{storefront_url}{search_path}", wait_until="domcontentloaded", timeout=40000)

            if platform == "zepto":
                page.wait_for_selector('[data-testid="product-card"]', timeout=10000)
                href = page.evaluate('() => document.querySelector(\'[data-testid="product-card"]\')?.getAttribute("href")')
            else:
                results = scrape_blinkit_results(page, 1)
                href = results[0]["url"] if results else None

            if not href:
                return {"status": "not_found", "error": f'No products found for "{query}"'}
            full_url = href if href.startswith("http") else f"{storefront_url}{href}"

        page.goto(full_url, wait_until="domcontentloaded", timeout=40000)
        page.wait_for_timeout(1200)

        if platform == "zepto":
            details = _read_product_details_zepto(page)
            already_in_cart = page.get_by_role("button", name="Increase quantity by one").is_visible()
        else:
            details = _read_product_details_generic(page)
            # Blinkit's stepper carries no aria-label (checked live), and a
            # naive "any visible '+' glyph" check is a false-positive trap:
            # a product page can have a stray unrelated "+" elsewhere (a
            # brand-row expand icon, confirmed live on a real product page
            # that had never been added to cart) while the real add
            # control is a plain "Add to cart" button. The one control that
            # actually reflects this item's cart state is the sticky
            # bottom action bar, which is either "Add to cart" (not in
            # cart) or a "− N +" stepper (already in cart) — and it's
            # reliably the bottom-most matching element on the page, so
            # pick by vertical position rather than trusting the first
            # match anywhere in the DOM.
            already_in_cart = page.evaluate(
                """() => {
                    const glyphs = ['+', '＋', '−', '-', '–'];
                    const addRe = /^(add to cart|add|add item|add to basket)$/i;
                    const els = Array.from(document.querySelectorAll('button, div[role="button"], a, span'));
                    let best = null;
                    for (const e of els) {
                        if (e.offsetParent === null) continue;
                        const t = (e.textContent || '').trim();
                        const isStepper = glyphs.includes(t);
                        const isAdd = addRe.test(t);
                        if (!isStepper && !isAdd) continue;
                        const rect = e.getBoundingClientRect();
                        // Restrict to the current viewport — a carousel
                        // further down the page (confirmed live: a "+" in a
                        // recommendations strip miles below the fold) has a
                        // much larger .bottom than the real sticky action
                        // bar and would otherwise win a plain max().
                        if (rect.bottom < 0 || rect.top > window.innerHeight) continue;
                        if (!best || rect.bottom > best.bottom) best = { isStepper, bottom: rect.bottom };
                    }
                    return best ? best.isStepper : false;
                }"""
            )

        if already_in_cart:
            # Already in the cart at some quantity — treat `quantity` as how
            # many more units to add, rather than guessing the stepper's
            # current value.
            extra_units = quantity
        else:
            clicked = js_click(page, r"^add to cart$|^add$|add to basket|add item")
            if not clicked:
                return {"status": "error", "error": "Could not find an Add to Cart button on this product."}
            page.wait_for_timeout(1000)
            extra_units = quantity - 1  # the Add to Cart click already added one

        for _ in range(max(0, extra_units)):
            if platform == "zepto":
                page.get_by_role("button", name="Increase quantity by one").click()
            else:
                if not stepper_click(page, increase=True):
                    break
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
