"""
tools/manage_address.py

View, switch, or set the storefront delivery address.

Quick-commerce prices, stock, and delivery ETAs are all address-specific,
so the agent needs a way to say "deliver to my office instead" or "set the
area to Indiranagar" without the user opening the app. This tool covers the
three cheap, safe cases:

  - list   : read the saved addresses and which one is active
  - select : switch the active address to a saved one matching a keyword
  - search : set the delivery location from a locality / landmark search

Adding a brand-new saved address means dragging a map pin and filling a
flat/house form on most of these sites — that's fragile to do blind and
easy to get wrong, so it's deliberately out of scope here; the tool says so
and the agent can fall back to notify_user.

Not a port — worked out against the live Zepto mobile site (the iPhone UA
in tools/_session.py). The address sheet's DOM has no stable test ids, so
the selectors below are text/heuristic based and may need a refresh if the
site changes; every path fails soft with a clear status rather than
throwing. That same heuristic style (no data-testid dependency, plain
text/keyword matching over the address sheet) is what makes this tool the
one storefront tool that didn't need a separate Blinkit code path for the
Strands port — it was written platform-agnostic from the start. It's still
unverified against a live Blinkit address sheet, though; see
tools/_session.py's module docstring.

The actual work happens in _manage_address_impl, run on the single
dedicated Playwright thread via run_on_playwright_thread — see
tools/_session.py's module docstring for why that's required (not
optional) whenever a tool touches a Page.
"""

from strands import tool

from tools._session import PLATFORMS, get_page, js_click, run_on_playwright_thread


def _current_address(page) -> str:
    """The delivery address shown in the top bar right now, trimmed."""
    try:
        return page.evaluate(
            """() => {
                const sel = [
                    '[data-testid*="address" i]',
                    '[data-testid*="location" i]',
                    '[class*="address" i]',
                    'header [class*="location" i]',
                ];
                for (const s of sel) {
                    const el = document.querySelector(s);
                    const t = el && el.textContent ? el.textContent.trim() : '';
                    if (t && t.length > 3) return t.replace(/\\s+/g, ' ').slice(0, 140);
                }
                return '';
            }"""
        )
    except Exception:
        return ""


def _open_address_sheet(page) -> bool:
    """Click whatever opens the address / location picker and wait for it."""
    opened = js_click(
        page,
        r"select location|add address|deliver(y)? to|delivery address|change address|"
        r"set (your )?location|your location|home\b.*\d|select a location",
    )
    if not opened:
        # Fall back to clicking the top-bar address element directly.
        opened = page.evaluate(
            """() => {
                const sel = [
                    '[data-testid*="address" i]',
                    '[data-testid*="location" i]',
                    'header [class*="location" i]',
                    '[class*="addressBar" i]',
                ];
                for (const s of sel) {
                    const el = document.querySelector(s);
                    if (el && el.offsetParent !== null) { el.click(); return true; }
                }
                return false;
            }"""
        )

    if not opened:
        return False

    try:
        page.wait_for_selector(
            "text=/saved address|add address|search.*(location|area)|"
            "confirm location|your saved addresses|add new address/i",
            timeout=8000,
        )
        return True
    except Exception:
        # The sheet may be open even without one of those exact strings.
        return True


def _scrape_addresses(page) -> list[dict]:
    """Every saved-address row in the open sheet: a short label plus the
    detail line, and a best-effort `active` flag from any selected styling."""
    return page.evaluate(
        """() => {
            const rows = Array.from(document.querySelectorAll(
                '[class*="address" i], [data-testid*="address" i], li, [role="button"]'
            ));
            const seen = new Set();
            const out = [];
            for (const r of rows) {
                const text = (r.textContent || '').replace(/\\s+/g, ' ').trim();
                if (!text || text.length < 6 || text.length > 220) continue;
                if (!/home|work|office|flat|floor|road|street|nagar|layout|apt|house|block|sector|\\d/i.test(text)) continue;
                if (/add address|add new address|search/i.test(text)) continue;
                if (seen.has(text)) continue;
                seen.add(text);
                const cls = (r.className || '') + ' ' + (r.getAttribute('aria-checked') || '');
                const active = /selected|active|current|checked|true/i.test(cls);
                const labelMatch = text.match(/^(home|work|office|other)\\b/i);
                out.push({
                    label: labelMatch ? labelMatch[1] : text.slice(0, 24),
                    detail: text.slice(0, 160),
                    active,
                });
            }
            return out.slice(0, 12);
        }"""
    )


@tool
def manage_address(action: str = "list", query: str = "", platform: str = "zepto") -> dict:
    """
    View, switch, or set the storefront delivery address. Prices, stock,
    and delivery times are all tied to the address, so use this before
    searching or checking out if the user wants delivery somewhere other
    than the currently selected place.

    Args:
        action: One of:
            "list"   - return the saved addresses and which is active now.
            "select" - switch the active delivery address to a saved one
                       whose text matches `query` (e.g. "home", "office",
                       a street name). Call "list" first to see options.
            "search" - set the delivery location by looking up `query`
                       (a locality, area, or landmark) and picking the top
                       suggestion. Use this when the place isn't already a
                       saved address.
        query: The keyword to match ("select") or the place to look up
            ("search"). Ignored for "list".
        platform: Which storefront — "zepto" (default) or "blinkit".
            Blinkit is unverified against a live address sheet — see
            tools/_session.py PLATFORMS.

    Returns:
        A dict with status ("ok", "not_found", "error"). For "list" and
        "select": "addresses" (list of {label, detail, active}) and
        "active" (the address string now shown in the top bar). For
        "search": the "active" address after the change.

        Adding a completely new saved address (map pin + house/flat form)
        is not supported here — status "error" with a note, so you can tell
        the user via notify_user.
    """
    return run_on_playwright_thread(_manage_address_impl, action, query, platform)


def _manage_address_impl(action: str, query: str, platform: str) -> dict:
    action = (action or "list").strip().lower()
    if action not in {"list", "select", "search"}:
        return {"status": "error", "error": f'Unknown action {action!r} — use "list", "select", or "search".'}
    if action in {"select", "search"} and not query.strip():
        return {"status": "error", "error": f'action "{action}" needs a non-empty query.'}
    if platform not in PLATFORMS:
        return {"status": "error", "error": f"Unknown platform {platform!r} — use one of {list(PLATFORMS)}."}

    page = get_page(platform)
    try:
        page.goto(PLATFORMS[platform]["url"], wait_until="domcontentloaded", timeout=40000)
        page.wait_for_timeout(1200)
        before = _current_address(page)

        if not _open_address_sheet(page):
            return {
                "status": "error",
                "error": "Could not open the address picker on the storefront.",
                "active": before,
            }
        page.wait_for_timeout(800)

        if action == "list":
            addresses = _scrape_addresses(page)
            return {"status": "ok", "active": before, "addresses": addresses}

        if action == "select":
            addresses = _scrape_addresses(page)
            clicked = page.evaluate(
                """(q) => {
                    const re = new RegExp(q.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&'), 'i');
                    const rows = Array.from(document.querySelectorAll(
                        '[class*="address" i], [data-testid*="address" i], li, [role="button"]'
                    ));
                    const el = rows.find(r =>
                        r.offsetParent !== null &&
                        re.test((r.textContent || '').trim()) &&
                        !/add address|add new address|search/i.test(r.textContent || '')
                    );
                    if (el) { el.click(); return true; }
                    return false;
                }""",
                query,
            )
            if not clicked:
                return {
                    "status": "not_found",
                    "error": f"No saved address matched {query!r}.",
                    "addresses": addresses,
                    "active": before,
                }
            page.wait_for_timeout(2500)
            after = _current_address(page)
            return {
                "status": "ok",
                "active": after or before,
                "changed": bool(after and after != before),
                "addresses": _scrape_addresses(page) if _open_address_sheet(page) else addresses,
            }

        # action == "search"
        filled = page.evaluate(
            """(q) => {
                const inp = document.querySelector(
                    'input[placeholder*="search" i], input[placeholder*="location" i], input[type="search"], input[type="text"]'
                );
                if (!inp) return false;
                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                setter.call(inp, q);
                inp.dispatchEvent(new Event('input', { bubbles: true }));
                inp.dispatchEvent(new Event('change', { bubbles: true }));
                inp.focus();
                return true;
            }""",
            query,
        )
        if not filled:
            return {"status": "error", "error": "Could not find the location search box.", "active": before}

        page.wait_for_timeout(2500)
        # Click the first real suggestion row under the search box.
        picked = page.evaluate(
            """() => {
                const items = Array.from(document.querySelectorAll(
                    'li, [role="option"], [class*="suggestion" i], [class*="result" i], [class*="predict" i]'
                ));
                const el = items.find(i => i.offsetParent !== null && (i.textContent || '').trim().length > 4);
                if (el) { el.click(); return true; }
                return false;
            }"""
        )
        if not picked:
            return {
                "status": "not_found",
                "error": f"No location suggestions came up for {query!r}.",
                "active": before,
            }

        page.wait_for_timeout(2000)
        # Zepto often needs a confirm step after picking a suggestion.
        js_click(page, r"confirm location|confirm & continue|add address details|use this location|save address")
        page.wait_for_timeout(2500)

        after = _current_address(page)
        if not after or after == before:
            return {
                "status": "error",
                "error": (
                    "Picked a suggestion but the delivery address didn't visibly change — "
                    "Zepto may need a house/flat number to finish. Ask the user to set it in the app."
                ),
                "active": before,
            }
        return {"status": "ok", "active": after, "changed": True}

    except Exception as exc:
        return {"status": "error", "error": str(exc)}
