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

Multi-platform note: PLATFORMS below is the registry for Blinkit/Instamart
expansion — session capture (login) already works for any of them, since
that flow is just "open the URL, let the user log in, keep the profile."
What's still Zepto-only is every tool's actual scraping logic
(search_products.py, add_to_cart.py, etc.), which hardcodes Zepto's DOM.
Porting those to another platform means giving each one its own selectors,
not just pointing this file at a different URL.
"""

from pathlib import Path
from typing import Optional

from playwright.sync_api import Page, sync_playwright

DEFAULT_PLATFORM = "zepto"

PLATFORMS: dict[str, dict] = {
    "zepto": {
        "label": "Zepto",
        "url": "https://www.zepto.com",
        # Shopping tools (search/cart/checkout) are implemented for this one.
        "supported": True,
    },
    "blinkit": {
        "label": "Blinkit",
        "url": "https://blinkit.com",
        "supported": False,
    },
    "instamart": {
        "label": "Swiggy Instamart",
        "url": "https://www.swiggy.com/instamart",
        "supported": False,
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
                "connected": connected,
            }
        )
    return status


def get_page(platform: str = DEFAULT_PLATFORM, headless: bool = True) -> Page:
    """Return the shared, already-navigated-if-possible page for this
    platform in this process. Launches the persistent profile on first use.
    One context per platform, so switching platforms mid-process doesn't
    tear down another platform's session."""
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
