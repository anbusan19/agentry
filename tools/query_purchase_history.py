"""
tools/query_purchase_history.py

Answers questions about past orders by searching the purchase-history
knowledge graph directly, rather than the model guessing from whatever
happens to be in its context. get_restock_suggestions only surfaces items
with a clear repeat pattern; this covers everything else, "how many ice
creams have I ordered," "have I ever bought X," "when did I last get Y."
"""

from strands import tool

from knowledge.graph import search_items


@tool
def query_purchase_history(keyword: str) -> dict:
    """
    Search the household's actual order history for items matching a
    keyword and report how many separate orders included each one, plus
    when it was last bought. Use this for any question about past orders
    that isn't just "what's due soon" — a count ("how many ice creams have
    I ordered"), a yes/no ("have I ever bought oat milk"), or a date
    ("when did I last order coffee"). Always call this rather than
    answering from memory or guessing.

    Args:
        keyword: A word or phrase to match against item names,
            case-insensitive, substring match (e.g. "ice cream", "milk").

    Returns:
        A dict with "matches" (list of {item, times_ordered,
        last_purchased}, most recent first) and "total_orders" (the sum of
        times_ordered across all matches, i.e. how many separate orders
        contained something matching this keyword — not a count of
        individual units within an order).
    """
    matches = search_items(keyword)
    if not matches:
        return {
            "matches": [],
            "total_orders": 0,
            "note": f'Nothing matching "{keyword}" found in the order history.',
        }

    return {"matches": matches, "total_orders": sum(m["times_ordered"] for m in matches)}
