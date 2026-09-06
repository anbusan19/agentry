"""
scripts/backfill_purchase_history.py

One-off backfill: walks every order under /account/orders, skips cancelled
ones, and records each delivered order's items into the purchase-history
knowledge graph (knowledge/graph.py) with its real order date — so
get_restock_suggestions reflects actual buying history from day one,
instead of starting empty.

Not a Strands @tool: this is a one-time seeding operation, not something
the agent needs to call itself. Re-running it re-appends every order again
(record_purchase doesn't dedup), so this is meant to be run once against a
freshly cleared data/purchases_graph.json.

Usage:
    python scripts/backfill_purchase_history.py
"""

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from knowledge.graph import record_purchase  # noqa: E402
from tools._session import STOREFRONT_URL, get_page, js_click  # noqa: E402

_QTY_LINE_RE = re.compile(r"^\d+\s*units?$", re.IGNORECASE)
_DATE_RE = re.compile(r"(\d{1,2}\s+\w{3}\s+\d{4},\s*\d{1,2}:\d{2}\s*[AP]M)", re.IGNORECASE)


def _collect_order_links(page) -> list[str]:
    page.goto(f"{STOREFRONT_URL}/account/orders", wait_until="domcontentloaded", timeout=40000)
    page.wait_for_timeout(1500)

    for _ in range(20):
        clicked = js_click(page, r"^load more$")
        if not clicked:
            break
        page.wait_for_timeout(1200)

    hrefs = page.evaluate(
        '() => Array.from(document.querySelectorAll(\'a[href*="/order/"]\')).map(a => a.getAttribute("href"))'
    )
    return list(dict.fromkeys(hrefs))  # de-duplicate, preserve order


def _parse_order(page, href: str) -> tuple[list[str], datetime | None, bool]:
    """Returns (items, placed_at, is_delivered)."""
    full_url = href if href.startswith("http") else f"{STOREFRONT_URL}{href}"
    page.goto(full_url, wait_until="domcontentloaded", timeout=40000)
    page.wait_for_timeout(1500)

    body = page.evaluate("() => document.body.innerText")
    lines = [l.strip() for l in body.split("\n") if l.strip()]

    is_delivered = "delivered" in body.lower() and "cancelled" not in body.lower()

    items = []
    for i, line in enumerate(lines):
        if _QTY_LINE_RE.match(line) and i >= 2:
            name = lines[i - 2]
            if name and name not in items:
                items.append(name)

    placed_at = None
    date_match = _DATE_RE.search(body)
    if date_match:
        try:
            # The storefront doesn't expose a timezone on this string — treat
            # it as UTC (a few hours off from the actual IST timestamp
            # doesn't matter at the day-level granularity restock intervals
            # are computed at), so it's comparable to the aware "now" used
            # elsewhere in knowledge/graph.py.
            placed_at = datetime.strptime(date_match.group(1), "%d %b %Y, %I:%M %p").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            placed_at = None

    return items, placed_at, is_delivered


def main() -> None:
    page = get_page()

    print("Loading full order history...")
    hrefs = _collect_order_links(page)
    print(f"Found {len(hrefs)} orders.\n")

    recorded, skipped = 0, 0
    for href in hrefs:
        items, placed_at, is_delivered = _parse_order(page, href)

        if not is_delivered:
            print(f"  skip (not delivered): {href}")
            skipped += 1
            continue
        if not items:
            print(f"  skip (no items parsed): {href}")
            skipped += 1
            continue

        record_purchase(items, when=placed_at)
        when_str = placed_at.strftime("%d %b %Y") if placed_at else "unknown date"
        print(f"  recorded {len(items)} items from {when_str}: {', '.join(items[:3])}{'...' if len(items) > 3 else ''}")
        recorded += 1

    print(f"\nDone: {recorded} orders recorded, {skipped} skipped.")


if __name__ == "__main__":
    main()
