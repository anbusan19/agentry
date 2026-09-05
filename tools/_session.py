"""
tools/_session.py

Shared Playwright session for storefront tools. Not a tool itself (no
@tool here) — this is the plumbing every tools/*.py storefront tool imports:
one persistent, already-logged-in browser profile and one live page, reused
across tool calls within an agent run so cart state survives from
search_products through checkout, exactly like a real shopping session.

Uses a persistent browser profile (Playwright's launch_persistent_context)
rather than exporting/importing a storage-state file: logging in once via
scripts/capture_session.py writes cookies straight to this profile directory,
and every tool call afterwards reuses them automatically. No explicit
save/load step needed.
"""

from pathlib import Path
from typing import Optional

from playwright.sync_api import Page, sync_playwright

STOREFRONT_URL = "https://www.zepto.com"
SESSION_DIR = Path(__file__).parent / ".sessions" / "zepto-profile"

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
_context = None
_page: Optional[Page] = None


def get_page(headless: bool = True) -> Page:
    """Return the shared, already-navigated-if-possible page for this
    process. Launches the persistent profile on first use."""
    global _playwright, _context, _page

    if _context is None:
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        _playwright = sync_playwright().start()
        _context = _playwright.chromium.launch_persistent_context(
            user_data_dir=str(SESSION_DIR),
            headless=headless,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            **CONTEXT_ARGS,
        )
        _context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )

    if _page is None or _page.is_closed():
        _page = _context.pages[0] if _context.pages else _context.new_page()

    return _page


def is_logged_in(page: Page) -> bool:
    """Best-effort check for the storefront's logged-out state."""
    try:
        return not page.locator("text=Please Login").is_visible()
    except Exception:
        return True


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
