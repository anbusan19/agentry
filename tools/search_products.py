"""
tools/search_products.py

Storefront product search, split out of the original combined
browser_automation tool so the agent (and, through it, the user) can look
things up without committing to a purchase — "what's the cheapest atta
right now" doesn't need to add anything to a cart.

The Zepto scraping approach here was worked out against the live storefront
directly (product cards carry a stable data-testid="product-card" and their
name/price fall out of a couple of regexes over the card's visible text) —
the original prototype's version scraped older selectors that no longer
match the current site.

Blinkit support (added for the Strands port, not present in the original
prototype) was confirmed live against a real logged-in session: /s/?q=...
is the right search path, and product cards are
div[role="button"][id=<numeric id>] with no href at all — a different
shape from Zepto's anchor cards — so it uses its own scraper
(tools/_session.py's scrape_blinkit_results).
"""

from urllib.parse import quote

from strands import tool

from tools._session import PLATFORMS, get_page, scrape_blinkit_results

_RESULTS_JS = r"""(max) => {
    const results = [];
    const cards = Array.from(document.querySelectorAll('[data-testid="product-card"]'));
    for (const card of cards) {
        const href = card.getAttribute('href') || '';
        const lines = (card.innerText || '').split('\n').map(l => l.trim()).filter(Boolean);
        const price = lines.find(l => /^₹\d/.test(l)) || '—';
        const name = lines.find(l =>
            !/^₹/.test(l) &&
            l !== 'OFF' &&
            l !== 'ADD' &&
            !/^\d+(\.\d+)?$/.test(l) &&                                    // rating, e.g. "4.8"
            !/^\(\d+(\.\d+)?[km]?\)$/i.test(l) &&                          // review count, e.g. "(39.7k)"
            !/^\d+\.?\d*\s*(pack|pc|pcs|ml|g|kg|l|ltr|litre|liters?)\b/i.test(l)  // weight, e.g. "1 pack (1 L)"
        );
        const img = card.querySelector('img');
        const image = img ? (img.getAttribute('src') || '') : '';

        if (name && href && !results.find(r => r.url === href)) {
            results.push({ name, price, url: href, image });
        }
        if (results.length >= max) break;
    }
    return results;
}"""

# Per-platform search path, both confirmed live.
SEARCH_PATH = {
    "zepto": "/search?query={q}",
    "blinkit": "/s/?q={q}",
}


@tool
def search_products(query: str, limit: int = 5, platform: str = "zepto") -> dict:
    """
    Search the storefront for products matching a query, without adding
    anything to the cart. Use this to check what's available, compare
    prices, or find a product URL before calling add_to_cart.

    Args:
        query: What to search for, e.g. "amul milk 500ml".
        limit: Max number of results to return (default 5).
        platform: Which storefront to search — "zepto" (default) or
            "blinkit". Both verified against a live logged-in session.

    Returns:
        A dict with status ("ok", "not_found", or "error") and, on success,
        a "results" list of {name, price, url, image} dicts, best match
        first. "image" is a product photo URL, or an empty string if the
        card had none.
    """
    if platform not in PLATFORMS:
        return {"status": "error", "error": f"Unknown platform {platform!r} — use one of {list(PLATFORMS)}."}

    storefront_url = PLATFORMS[platform]["url"]
    page = get_page(platform)
    try:
        path = SEARCH_PATH.get(platform, "/search?query={q}").format(q=quote(query))
        page.goto(f"{storefront_url}{path}", wait_until="domcontentloaded", timeout=40000)

        if platform == "zepto":
            page.wait_for_selector('[data-testid="product-card"]', timeout=10000)
            page.wait_for_timeout(500)
            results = page.evaluate(_RESULTS_JS, limit)
        else:
            results = scrape_blinkit_results(page, limit)

        if not results:
            return {"status": "not_found", "results": [], "error": f'No products found for "{query}"'}

        return {"status": "ok", "results": results}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
