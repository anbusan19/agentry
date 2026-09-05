"""
tools/get_restock_suggestions.py

Reads the purchase-history knowledge graph (knowledge/graph.py) to suggest
what's likely due for a restock, based on this household's own past buying
intervals — not a fixed schedule. Each suggestion also carries the items
most often bought alongside it, so a restock list can be rounded out
sensibly (milk usually means bread too).
"""

from strands import tool

from knowledge.graph import restock_suggestions


@tool
def get_restock_suggestions(within_days: float = 3.0) -> dict:
    """
    Suggest items likely due for a restock soon, based on this household's
    own purchase history — how often each item has actually been bought in
    the past, not a generic assumption. Use this before planning a
    "restock the pantry"-style goal to ground the shopping list in real
    buying patterns, on top of whatever the user explicitly asked for.

    Needs at least two recorded purchases of an item to estimate its
    interval — a brand-new household knowledge graph will return nothing,
    which is expected, not an error.

    Args:
        within_days: How close to (or past) an item's usual restock point
            counts as "due soon" (default 3 days).

    Returns:
        A dict with a "due" list, each entry giving the item, its usual
        restock interval in days, days since it was last bought, whether
        it's already overdue, and up to 3 items it's often bought with.
    """
    return restock_suggestions(within_days=within_days)
