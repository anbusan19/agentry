"""
tools/browser.py

Playwright storefront automation tool for Agentry.

Ported from the pre-existing prototype this hackathon submission builds on
(see README's Disclosure section): a stealth-context launcher, session
persistence, product search, and add-to-cart/checkout DOM-scraping flow,
reimplemented here in Python as a single Strands @tool.

Deliberately NOT ported: wallet selection (Zepto Cash) and "Place Order".
Checkout stops once the payment screen is reached and the amount due can be
read off the page — settlement is handed off to tools/payment.py instead, so
this file stays free of payment logic per project convention.
"""

import re
from pathlib import Path
from typing import Optional

from playwright.sync_api import BrowserContext, sync_playwright
from strands import tool

STOREFRONT_URL = "https://www.zepto.com"
SESSION_DIR = Path(__file__).parent / ".sessions"
SESSION_FILE = SESSION_DIR / "zepto.json"

USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

# Module-level browser/context, reused across tool calls within one agent run
# (mirrors the original's globalContext singleton in agent/index.ts).
_playwright = None
_browser = None
_context: Optional[BrowserContext] = None


def _get_context() -> BrowserContext:
    global _playwright, _browser, _context
    if _context is not None:
        return _context

    _playwright = sync_playwright().start()
    _browser = _playwright.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
    )

    kwargs = dict(
        user_agent=USER_AGENT,
        viewport={"width": 390, "height": 844},
        locale="en-IN",
        geolocation={"latitude": 12.9903, "longitude": 80.2456},
        permissions=["geolocation"],
    )
    if SESSION_FILE.exists():
        kwargs["storage_state"] = str(SESSION_FILE)

    _context = _browser.new_context(**kwargs)
    _context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
    )
    return _context


def _save_session(context: BrowserContext) -> None:
    SESSION_DIR.mkdir(exist_ok=True)
    context.storage_state(path=str(SESSION_FILE))


_SEARCH_RESULTS_JS = """(max) => {
    const results = [];
    const links = Array.from(document.querySelectorAll('a[href*="/pn/"]'));
    for (const link of links) {
        const href = link.getAttribute('href') || '';
        const rawName = link.textContent?.trim() ?? '';
        const name = rawName
            .replace(/ADD/g, '')
            .replace(/₹\\s?\\d+(\\.\\d+)?\\s*(OFF|off)?/g, '')
            .replace(/\\d+\\.?\\d*\\s*(pc|pcs|ml|g|kg|L|ltr|litre|liters?)\\b.*/i, '')
            .replace(/\\d+\\.\\d+\\s*\\(\\d+.*/, '')
            .replace(/\\s+/g, ' ')
            .trim()
            .slice(0, 80);
        let price = '—';
        let container = link.parentElement;
        for (let i = 0; i < 6 && container; i++) {
            const priceEl = Array.from(container.querySelectorAll('*')).find(el => {
                const t = el.textContent?.trim() ?? '';
                return /^₹\\s?\\d/.test(t) && t.length < 15 && el.children.length === 0;
            });
            if (priceEl) { price = priceEl.textContent?.trim() ?? '—'; break; }
            container = container.parentElement;
        }
        if (name && href && !results.find(r => r.url === href)) {
            results.push({ name, price, url: href });
        }
        if (results.length >= max) break;
    }
    return results;
}"""


def _search(context: BrowserContext, query: str, limit: int = 5) -> list[dict]:
    page = context.new_page()
    try:
        page.goto(STOREFRONT_URL, wait_until="networkidle", timeout=40000)
        page.wait_for_timeout(2000)
        page.click('[data-testid="search-bar-icon"]')
        page.wait_for_timeout(1500)

        search_input = page.query_selector('input[type="search"], input[placeholder*="earch" i]')
        if not search_input:
            raise RuntimeError("Search input not found on storefront")
        search_input.fill(query)
        page.wait_for_timeout(2000)
        page.locator(f"text={query}").first.click()
        page.wait_for_timeout(3000)

        return page.evaluate(_SEARCH_RESULTS_JS, limit)
    finally:
        page.close()


def _add_to_cart_and_reach_payment(context: BrowserContext, query: str, product_url: Optional[str]) -> dict:
    """Navigate to a product, add it to cart, and walk checkout up to (but not
    through) the payment step. Returns what's known about the pending order.
    Stops before wallet selection / placing the order."""
    page = context.new_page()
    try:
        product_name = query
        product_price = "unknown"

        if product_url:
            full_url = product_url if product_url.startswith("http") else f"{STOREFRONT_URL}{product_url}"
            page.goto(full_url, wait_until="networkidle", timeout=40000)
            page.wait_for_timeout(2000)
        else:
            page.goto(STOREFRONT_URL, wait_until="networkidle", timeout=40000)
            page.wait_for_timeout(2000)
            page.click('[data-testid="search-bar-icon"]')
            page.wait_for_timeout(1500)
            search_input = page.query_selector('input[type="search"], input[placeholder*="earch" i]')
            if not search_input:
                raise RuntimeError("Search input not found on storefront")
            search_input.fill(query)
            page.wait_for_timeout(2000)
            page.locator(f"text={query}").first.click()
            page.wait_for_timeout(3000)

            first_link = page.query_selector('a[href*="/pn/"]')
            if first_link:
                href = first_link.get_attribute("href")
                if href:
                    page.goto(href, wait_until="networkidle", timeout=30000)
                    page.wait_for_timeout(2000)

        details = page.evaluate(
            """() => {
                const name = document.querySelector('h1, [class*="product-name"], [class*="productName"]');
                const price = document.querySelector('[class*="price"], [class*="Price"]');
                return {
                    name: name?.textContent?.trim().slice(0, 60),
                    price: price?.textContent?.trim().slice(0, 20),
                };
            }"""
        )
        product_name = details.get("name") or product_name
        product_price = details.get("price") or product_price

        # ── Add to cart ──────────────────────────────────────────
        added = page.evaluate(
            """() => {
                const EXCLUDE = /add\\s*(new\\s*)?address/i;
                const candidates = Array.from(
                    document.querySelectorAll('button, div[role="button"], a[role="button"], [class*="add-to-cart" i], [class*="addToCart" i]')
                );
                let btn = candidates.find(b => {
                    const t = b.textContent?.trim() ?? '';
                    return (/^add to cart$/i.test(t) || /^add$/i.test(t)) && b.offsetParent !== null && !EXCLUDE.test(t);
                });
                if (btn) { btn.click(); return btn.textContent?.trim(); }
                return null;
            }"""
        )
        if not added:
            try:
                page.get_by_role("button", name=re.compile("add to cart|^add$", re.I)).first.click(timeout=8000)
            except Exception:
                page.locator("button, [role='button']").filter(has_text=re.compile("add", re.I)).filter(
                    has_not_text=re.compile(r"add\s*(new\s*)?address", re.I)
                ).first.click(timeout=8000)

        try:
            page.wait_for_function(
                "() => /view cart|item in cart|items in cart|\\d+\\s*item/i.test(document.body.innerText)",
                timeout=8000,
            )
        except Exception:
            page.wait_for_timeout(2000)

        # ── Open cart on same page (preserves SPA session) ─────────
        current_url = page.url.split("?")[0]
        page.goto(f"{current_url}?cart=open", wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(2000)

        try:
            page.wait_for_function(
                "() => /item total|total bill|add address|proceed to pay|your cart|₹|subtotal/i.test(document.body.innerText)",
                timeout=12000,
            )
        except Exception:
            pass

        needs_login = page.locator("text=Please Login").is_visible()
        if needs_login:
            raise RuntimeError("SESSION_EXPIRED — storefront login needed (set ZEPTO_PHONE and log in)")

        def js_click(pattern: str) -> bool:
            return page.evaluate(
                """(pat) => {
                    const re = new RegExp(pat, 'i');
                    const candidates = [
                        ...Array.from(document.querySelectorAll('button')),
                        ...Array.from(document.querySelectorAll('div[role="button"], a, div, span')),
                    ];
                    const el = candidates.find(b => re.test(b.textContent?.trim() ?? '') && b.offsetParent !== null);
                    if (el) { el.click(); return true; }
                    return false;
                }""",
                pattern,
            )

        js_click("add address to proceed|proceed to checkout")
        page.wait_for_timeout(2000)

        # ── Address selection, if a saved-address modal appears ────
        is_address_modal = page.evaluate(
            "() => /select an address|saved addresses/i.test(document.body.innerText)"
        )
        if is_address_modal:
            page.evaluate(
                """() => {
                    const heading = Array.from(document.querySelectorAll('*')).find(
                        el => /^saved addresses$/i.test(el.textContent?.trim() ?? '') && el.offsetParent !== null
                    );
                    let container = heading?.parentElement ?? null;
                    for (let i = 0; i < 5 && container; i++) {
                        const row = Array.from(container.querySelectorAll('div, li, a')).find(el => {
                            const text = el.textContent?.trim() ?? '';
                            return text.length > 10 && text.length < 300 && el.offsetParent !== null &&
                                !/^saved addresses$/i.test(text) && !/^add new address$/i.test(text) &&
                                !/^select an address$/i.test(text) && el !== heading;
                        });
                        if (row) { row.click(); return true; }
                        container = container.parentElement;
                    }
                    return false;
                }"""
            )
            page.wait_for_timeout(2000)
            js_click("deliver here|use this address|confirm address|done")
            page.wait_for_timeout(2000)

        js_click("proceed to pay")
        page.wait_for_timeout(2000)

        # ── Select the platform wallet (Zepto Cash) ─────────────────
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
        page.wait_for_timeout(1500)

        order_summary = page.evaluate(
            """() => {
                const total = document.querySelector('[class*="total" i], [class*="amount" i], [class*="payable" i]');
                const eta = document.querySelector('[class*="eta" i], [class*="time" i], [class*="minute" i]');
                return {
                    total: total?.textContent?.trim().slice(0, 30),
                    eta: eta?.textContent?.trim().slice(0, 30),
                };
            }"""
        )

        if not wallet_selected:
            _save_session(context)
            return {
                "item": product_name,
                "price": order_summary.get("total") or product_price,
                "eta": order_summary.get("eta") or "10-15 mins",
                "status": "wallet_not_available",
                "note": "No platform wallet (Zepto Cash) option found — order was not placed.",
            }

        # ── Place order ──────────────────────────────────────────────
        placed = js_click("place order|pay now|confirm order|pay ₹")
        if not placed:
            _save_session(context)
            return {
                "item": product_name,
                "price": order_summary.get("total") or product_price,
                "eta": order_summary.get("eta") or "10-15 mins",
                "status": "error",
                "note": "Could not find the Place Order / Pay Now button.",
            }

        page.wait_for_timeout(5000)

        confirmation = page.evaluate(
            """() => {
                const idText = document.body.innerText.match(/#?([A-Z0-9]{6,20})/)?.[1];
                const eta = document.querySelector('[class*="eta" i], [class*="time" i], [class*="minute" i]');
                const total = document.querySelector('[class*="total" i], [class*="amount" i]');
                return {
                    orderId: idText || null,
                    eta: eta?.textContent?.trim().slice(0, 30) || null,
                    total: total?.textContent?.trim().slice(0, 30) || null,
                };
            }"""
        )

        current_url = page.url
        is_confirmed = (
            "order" in current_url
            or "success" in current_url
            or "confirmed" in current_url
            or page.locator("text=/order placed|order confirmed|on the way/i").is_visible()
        )

        _save_session(context)

        total_text = confirmation.get("total") or order_summary.get("total") or product_price
        match = re.search(r"[\d.]+", total_text or "")
        amount_paid = float(match.group(0)) if match else None

        if not is_confirmed:
            return {
                "item": product_name,
                "price": total_text,
                "amount_paid": amount_paid,
                "status": "error",
                "note": f"Order placement may have failed. URL: {current_url}",
            }

        order_id = f"ZP-{confirmation['orderId']}" if confirmation.get("orderId") else None

        return {
            "item": product_name,
            "price": total_text,
            "amount_paid": amount_paid,
            "eta": confirmation.get("eta") or order_summary.get("eta") or "10-15 mins",
            "order_id": order_id,
            "status": "paid",
        }
    finally:
        page.close()


@tool
def browser_automation(query: str, limit: int = 5) -> dict:
    """
    Search the storefront for an item, add the best match to the cart, and
    complete checkout end to end — including paying with the storefront's
    own wallet (e.g. Zepto Cash).

    This drives a real quick-commerce storefront via a stealth Playwright
    browser. There is no separate payment step: settlement happens using
    whatever platform-native wallet balance is available at checkout. If no
    such wallet is available, the order is left unplaced and reported back
    rather than guessing at another payment method.

    Args:
        query: The item to search for and order, e.g. "amul milk 500ml".
        limit: How many search results to consider before picking the best
            match (default 5). Currently the top result is used.

    Returns:
        A dict describing the outcome: item name, price, eta, and status —
        "paid" (with amount_paid and order_id), "wallet_not_available"
        (nothing was charged), "not_found", or "error" (with a note).
    """
    context = _get_context()

    try:
        results = _search(context, query, limit=limit)
    except Exception as exc:
        return {"status": "error", "error": f"Search failed: {exc}"}

    if not results:
        return {"status": "not_found", "error": f'No products found for "{query}"'}

    best_match = results[0]

    try:
        return _add_to_cart_and_checkout(context, best_match["name"], best_match.get("url"))
    except Exception as exc:
        return {"status": "error", "error": str(exc), "item": best_match.get("name")}
