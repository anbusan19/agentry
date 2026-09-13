"""
tools/record_purchase.py

Logs a completed order into the purchase-history knowledge graph
(knowledge/graph.py), so future runs can reason about restock timing and
what tends to get bought together. Call this once checkout succeeds.
"""

from strands import tool

from knowledge.graph import record_purchase as _record_purchase


@tool
def record_purchase(items: list[str], platform: str = "zepto") -> dict:
    """
    Record a completed order's items into the purchase-history knowledge
    graph, so future runs can suggest restocks based on this household's
    actual buying pattern. Call this once, right after a successful
    checkout, with the item names that were actually bought.

    Args:
        items: The item names bought in this order, e.g.
            ["amul milk 500ml", "bread"].
        platform: Which storefront the order was placed on — "zepto",
            "blinkit", or "instamart". Defaults to "zepto"; only pass
            something else if checkout actually ran on that platform. Tags
            each item's purchase history with where it was bought, for
            restock timing per-platform and, eventually, price comparison
            across stores.

    Returns:
        A dict with status "ok" and the number of items recorded.
    """
    if not items:
        return {"status": "ok", "recorded": 0}

    _record_purchase(items, platform=platform)
    return {"status": "ok", "recorded": len(items)}
