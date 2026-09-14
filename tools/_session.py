"""
tools/_session.py

Shared Playwright session for storefront tools. Not a tool itself (no
@tool here) — this is the plumbing every tools/*.py storefront tool imports:
one persistent, already-logged-in browser profile and one live page per
platform, reused across tool calls within an agent run so cart state
survives from search_products through checkout, exactly like a real
shopping session.

Uses a persistent browser profile (Playwright's launch_persistent_context)
rather than exporting/importing a storage-state file: logging in once via
scripts/capture_session.py writes cookies straight to this profile directory,
and every tool call afterwards reuses them automatically. No explicit
save/load step needed.

Multi-platform note: every storefront tool (search_products.py,
add_to_cart.py, view_cart.py, remove_from_cart.py, checkout.py,
check_wallet_balance.py, manage_address.py) takes a `platform` arg and has
a code path for both platforms below. Zepto's path is the original, worked
out and exercised against the live site with stable data-testid selectors.
Blinkit's was worked out and confirmed live separately (own selectors —
div[role="button"][id] product cards, a glyph-based quantity stepper, a
directly-navigable /cart page — see scrape_blinkit_results and
stepper_click below). manage_address on Blinkit is still unconfirmed.
Blinkit Money is confirmed app-exclusive — not on /account, not on the web
payment-method screen (screenshot-confirmed: Wallets, cards, Netbanking,
UPI, Cash, Pay Later only) — so check_wallet_balance.py reports it
"not_found" outright for Blinkit rather than hunting for it, and
checkout.py's payment_method="upi" is the real working payment path there
instead of a wallet. Incrementing the quantity of an item already in the
cart is flaky. Run scripts/capture_session.py for a platform, then try
search_products /
view_cart there before ever calling checkout(confirm=True) on it.
"""

import concurrent.futures
import re
from pathlib import Path
from typing import Any, Callable, Optional

from playwright.sync_api import Page, sync_playwright

DEFAULT_PLATFORM = "zepto"

PLATFORMS: dict[str, dict] = {
    "zepto": {
        "label": "Zepto",
        "url": "https://www.zepto.com",
        # Shopping tools (search/cart/checkout) are implemented for this one
        # and have been run against a live logged-in session.
        "supported": True,
        "verified": True,
    },
    "blinkit": {
        "label": "Blinkit",
        "url": "https://blinkit.com",
        # Verified live (against a real logged-in session) while porting:
        # search, add-to-cart, and the cart page all work. Product cards are
        # div[role="button"][id=<numeric product id>] with no href — see
        # scrape_blinkit_results below — and /prn/<anything>/prid/<id> routes
        # correctly regardless of the slug text, confirmed by navigating
        # there with a deliberately wrong slug. check_wallet_balance and
        # manage_address are still unconfirmed (the wallet page loaded but
        # never rendered a balance in testing — inconclusive, not "broken").
        # One known remaining gap: incrementing/decrementing the quantity
        # of an item ALREADY in the cart is flaky (stepper_click sometimes
        # can't find the "− N +" control even though it's on screen) —
        # fresh adds, search, and view_cart are solid, but don't trust
        # "add more of what's already there" unattended yet.
        "supported": True,
        "verified": True,
    },
}

# Kept as module-level constants so the existing (Zepto-only) tool files can
# keep importing them unchanged.
STOREFRONT_URL = PLATFORMS[DEFAULT_PLATFORM]["url"]
SESSION_DIR = Path(__file__).parent / ".sessions" / f"{DEFAULT_PLATFORM}-profile"

USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

CONTEXT_ARGS = dict(
    user_agent=USER_AGENT,
    viewport={"width": 390, "height": 844},
    locale="en-IN",
    geolocation={"latitude": 12.9903, "longitude": 80.2456},
    permissions=["geolocation"],
)

_playwright = None
_contexts: dict[str, object] = {}
_pages: dict[str, Page] = {}

# Every bit of actual Playwright work in this process — get_page() and
# everything each tool does with the page it returns — is funneled through
# this single dedicated worker thread. This isn't an optimization, it's
# required correctness: Playwright's *sync* API is bound to the one OS
# thread that created it (sync_playwright().start() roots a greenlet-based
# dispatcher in that thread), and calling any page/context method from a
# different thread fails outright with "greenlet.error: cannot switch to a
# different thread" — confirmed live. Strands runs every @tool call via
# asyncio.to_thread, which hands each call to whatever thread Python's
# default executor pool has free — a different thread per call, easily,
# especially when the agent issues two tool calls back to back. An earlier
# version of this file only put a lock around get_page()'s lazy-init, which
# stopped two threads from *creating* the driver at once but did nothing
# for the (much more common) case of a second thread later *using* a page
# a first thread had already created — that's what was actually breaking
# live runs. Routing everything through one thread fixes both: only that
# thread ever touches _playwright/_contexts/_pages, so there's no creation
# race either, and no lock is needed.
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="playwright-owner")


def run_on_playwright_thread(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Run fn(*args, **kwargs) on the single thread that owns every
    Playwright connection/context/page in this process, and block for its
    result. Every storefront tool's @tool-decorated function is a thin
    wrapper that does nothing but call this around its real implementation
    — see any tools/*.py for the pattern. Never call get_page() or touch a
    Page directly from a function that wasn't itself dispatched this way."""
    return _executor.submit(fn, *args, **kwargs).result()


def session_dir(platform: str) -> Path:
    return Path(__file__).parent / ".sessions" / f"{platform}-profile"


def platform_status() -> list[dict]:
    """For the settings UI: every known platform, whether a login session
    has been captured for it, and whether shopping tools exist for it yet."""
    status = []
    for pid, info in PLATFORMS.items():
        sdir = session_dir(pid)
        connected = sdir.exists() and any(sdir.iterdir())
        status.append(
            {
                "id": pid,
                "label": info["label"],
                "url": info["url"],
                "supported": info["supported"],
                "verified": info.get("verified", False),
                "connected": connected,
            }
        )
    return status


def get_page(platform: str = DEFAULT_PLATFORM, headless: bool = True) -> Page:
    """Return the shared, already-navigated-if-possible page for this
    platform in this process. Launches the persistent profile on first use.
    One context per platform, so switching platforms mid-process doesn't
    tear down another platform's session.

    Must only be called from the dedicated Playwright thread — i.e. from
    inside a function passed to run_on_playwright_thread(). No locking here:
    that thread is the only caller by construction, so there's nothing to
    race with."""
    global _playwright

    if platform not in PLATFORMS:
        raise ValueError(f"Unknown platform {platform!r} — known: {list(PLATFORMS)}")

    if platform not in _contexts:
        sdir = session_dir(platform)
        sdir.mkdir(parents=True, exist_ok=True)
        if _playwright is None:
            _playwright = sync_playwright().start()
        context = _playwright.chromium.launch_persistent_context(
            user_data_dir=str(sdir),
            headless=headless,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            **CONTEXT_ARGS,
        )
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )
        _contexts[platform] = context

    context = _contexts[platform]
    page = _pages.get(platform)
    if page is None or page.is_closed():
        page = context.pages[0] if context.pages else context.new_page()
        _pages[platform] = page

    return page


def is_logged_in(page: Page) -> bool:
    """Best-effort check for the storefront's logged-out state."""
    try:
        return not page.locator("text=Please Login").is_visible()
    except Exception:
        return True


def stepper_click(page: Page, increase: bool) -> bool:
    """Click a quantity-stepper '+'/'−' control (the "− N +" widget that
    appears next to an item once it's in the cart). Tries, in order: Zepto's
    "Increase/Decrease quantity by one" aria-label; a bare +/- text glyph
    button; an icon-font button (a <button> wrapping a child whose class
    contains "plus"/"minus", e.g. Blinkit's `<span class="icon-minus">`,
    which carries no text at all). The last two are scoped to the current
    viewport.

    That viewport scoping matters: confirmed live on Blinkit, a plain
    "closest +/- anywhere in the DOM" search picks up unrelated glyphs
    lower on the page (a recommendations carousel's own "+" chip, far
    below the fold) instead of the real sticky action-bar stepper, and
    clicks that instead — silently not doing what was asked. Restricting
    to elements actually on screen fixes that.

    The icon-font fallback exists because Blinkit's stepper stopped being
    plain +/- text at some point after this was first verified live — it
    now renders as an empty-text button wrapping an icon-font span, so the
    text-glyph match alone silently found nothing and remove_from_cart
    reported items as "not in the cart" when they genuinely were. Exactly
    the kind of live DOM drift the project's own notes warn about."""
    verb = "increase" if increase else "decrease"
    try:
        btn = page.get_by_role("button", name=re.compile(rf"{verb} quantity( by one)?", re.I))
        if btn.first.is_visible():
            btn.first.click()
            return True
    except Exception:
        pass

    glyphs = ["+", "＋"] if increase else ["−", "-", "–"]
    icon_word = "plus" if increase else "minus"
    return page.evaluate(
        """(args) => {
            const [glyphs, iconWord] = args;
            const inViewport = (e) => {
                const rect = e.getBoundingClientRect();
                return rect.bottom >= 0 && rect.top <= window.innerHeight;
            };

            const glyphEls = Array.from(document.querySelectorAll('button, div[role="button"], span'))
                .filter(e => e.offsetParent !== null && glyphs.includes((e.textContent || '').trim()) && inViewport(e));

            // Real <button>s first: a generic div[role="button"] can be an
            // outer wrapper around the *whole* stepper (both +/- icons),
            // sitting lower on the page than the actual clickable button
            // inside it — confirmed live, that wrapper matched instead of
            // the real button and the click did nothing. Only fall back to
            // div wrappers if no actual <button> icon match exists.
            const iconButtons = Array.from(document.querySelectorAll('button'))
                .filter(e => e.offsetParent !== null && inViewport(e) && e.querySelector(`[class*="${iconWord}" i]`));
            const iconDivs = iconButtons.length
                ? []
                : Array.from(document.querySelectorAll('div[role="button"]'))
                    .filter(e => e.offsetParent !== null && inViewport(e) && e.querySelector(`[class*="${iconWord}" i]`));

            const candidates = [...glyphEls, ...iconButtons, ...iconDivs];
            // Prefer the one closest to the bottom of the viewport — that's
            // where a sticky add-to-cart/stepper action bar lives.
            candidates.sort((a, b) => b.getBoundingClientRect().bottom - a.getBoundingClientRect().bottom);
            if (candidates[0]) { candidates[0].click(); return true; }
            return false;
        }""",
        [glyphs, icon_word],
    )


_BLINKIT_RESULTS_JS = r"""(max) => {
    const cards = Array.from(document.querySelectorAll('div[role="button"][id]'))
        .filter(c => /^\d+$/.test(c.id));
    const results = [];
    for (const card of cards) {
        const lines = (card.innerText || '').split('\n').map(l => l.trim()).filter(Boolean);
        const price = lines.find(l => /^₹\d/.test(l));
        if (!price) continue;
        const name = lines.find(l =>
            l !== price &&
            l !== 'ADD' &&
            !/^\d+\.?\d*\s*(ml|g|kg|l|pack|pc|pcs)\b/i.test(l) &&
            !/mins?$/i.test(l) &&
            l.length > 3
        );
        if (!name) continue;
        const img = card.querySelector('img');
        // Blinkit routes on /prn/<slug>/prid/<id> and ignores the slug text
        // entirely (confirmed by navigating with a deliberately wrong one),
        // so the id is all that matters for add_to_cart to find this again.
        results.push({ name, price, url: `/prn/product/prid/${card.id}`, image: img ? (img.getAttribute('src') || '') : '' });
        if (results.length >= max) break;
    }
    return results;
}"""


def scrape_blinkit_results(page: Page, limit: int) -> list[dict]:
    """Blinkit-specific product scrape, confirmed live while porting:
    product cards are `<div role="button" id="<numeric product id>">` with
    no `<a href>` at all (unlike Zepto's anchor-based cards). The product id
    doubles as the routable id in /prn/<anything>/prid/<id> — Blinkit
    ignores the slug text, confirmed by loading that URL with a
    deliberately wrong slug and getting the right product."""
    try:
        page.wait_for_function(
            """() => Array.from(document.querySelectorAll('div[role="button"][id]'))
                .some(c => /^\\d+$/.test(c.id) && /₹\\d/.test(c.innerText || ''))""",
            timeout=10000,
        )
    except Exception:
        pass
    page.wait_for_timeout(500)
    return page.evaluate(_BLINKIT_RESULTS_JS, limit)


def js_click(page: Page, pattern: str) -> bool:
    """Click the first visible button/link/div whose text matches `pattern`
    (case-insensitive). Shared by every checkout-adjacent tool."""
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
