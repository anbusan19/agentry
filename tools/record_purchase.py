"""
tools/record_purchase.py

Logs a completed order into the purchase-history knowledge graph
(knowledge/graph.py), so future runs can reason about restock timing and
what tends to get bought together. Call this once checkout succeeds.
"""

from strands import tool

from knowledge.graph import record_purchase as _record_purchase


@tool
def record_purchase(items: list[str]) -> dict:
    """
    Record a completed order's items into the purchase-history knowledge
    graph, so future runs can suggest restocks based on this household's
    actual buying pattern. Call this once, right after a successful
    checkout, with the item names that were actually bought.

    Args:
        items: The item names bought in this order, e.g.
            ["amul milk 500ml", "bread"].

    Returns:
        A dict with status "ok" and the number of items recorded.
    """
    if not items:
        return {"status": "ok", "recorded": 0}

    _record_purchase(items)
    return {"status": "ok", "recorded": len(items)}
