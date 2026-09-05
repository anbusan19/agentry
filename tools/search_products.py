"""
tools/search_products.py

Storefront product search, split out of the original combined
browser_automation tool so the agent (and, through it, the user) can look
things up without committing to a purchase — "what's the cheapest atta
right now" doesn't need to add anything to a cart.

The scraping approach here was worked out against the live storefront
directly (product cards carry a stable data-testid="product-card" and their
name/price fall out of a couple of regexes over the card's visible text) —
the original prototype's version scraped older selectors that no longer
match the current site.
"""

from urllib.parse import quote

from strands import tool

from tools._session import STOREFRONT_URL, get_page

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
        if (name && href && !results.find(r => r.url === href)) {
            results.push({ name, price, url: href });
        }
        if (results.length >= max) break;
    }
    return results;
}"""


@tool
def search_products(query: str, limit: int = 5) -> dict:
    """
    Search the storefront for products matching a query, without adding
    anything to the cart. Use this to check what's available, compare
    prices, or find a product URL before calling add_to_cart.

    Args:
        query: What to search for, e.g. "amul milk 500ml".
        limit: Max number of results to return (default 5).

    Returns:
        A dict with status ("ok", "not_found", or "error") and, on success,
        a "results" list of {name, price, url} dicts, best match first.
    """
    page = get_page()
    try:
        page.goto(
            f"{STOREFRONT_URL}/search?query={quote(query)}",
            wait_until="domcontentloaded",
            timeout=40000,
        )
        page.wait_for_selector('[data-testid="product-card"]', timeout=10000)
        page.wait_for_timeout(500)

        results = page.evaluate(_RESULTS_JS, limit)
        if not results:
            return {"status": "not_found", "results": [], "error": f'No products found for "{query}"'}

        return {"status": "ok", "results": results}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
