"""
tools/recall_decisions.py

New for Graph Hacks (WeMakeDevs x FalkorDB) — episodic memory read.
record_purchase (knowledge/graph.py) writes a Session-[:DECIDED]->Product
edge for every completed order, and seed/decision data can record
substitution accept/reject or out-of-stock events the same way. This tool
reads that history back so a later session doesn't repeat a decision this
household already made.
"""

from strands import tool

from knowledge.graph import recall_decisions as _recall_decisions


@tool
def recall_decisions(sku_or_name: str) -> dict:
    """
    Look up every past session decision on record for an item — purchases,
    accepted/rejected substitutions, out-of-stock events — most recent
    first. Call this before choosing a substitution, so you don't suggest
    something this household already rejected, or miss one they already
    accepted before.

    Args:
        sku_or_name: The item name, same normalization as everywhere else.

    Returns:
        A dict with "decisions" (list of {session_id, ts, goal, action,
        reason}) and "count". An empty list means no prior decision is on
        record for this item — not an error.
    """
    decisions = _recall_decisions(sku_or_name)
    return {"decisions": decisions, "count": len(decisions)}
