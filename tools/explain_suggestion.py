"""
tools/explain_suggestion.py

New for Graph Hacks (WeMakeDevs x FalkorDB) — every restock/co-purchase
suggestion the agent surfaces should be traceable back to the actual Cypher
paths that justify it, not an opaque "trust me." Wraps
knowledge/graph.py's explain_path (restock-timing stats, co-purchase
neighbors, substitute edges, and episodic DECIDED history, all read live
from FalkorDB) into a human-readable explanation plus the exact Cypher
used, so the agent can show its reasoning before adding or presenting an
item.
"""

from strands import tool

from knowledge.graph import explain_path


@tool
def explain_suggestion(sku_or_name: str) -> dict:
    """
    Explain why an item is being suggested (for a restock, a round-out, or
    a substitution), by tracing the actual graph paths behind it: this
    household's purchase stats for the item, what it's usually bought
    alongside, any known substitutes, and any past session decisions on
    record for it. Call this before presenting or adding a suggested item
    so you can give the user a real reason, not a guess.

    Args:
        sku_or_name: The item name (same normalization as everywhere else
            — case/whitespace don't matter), e.g. "amul milk 500ml".

    Returns:
        A dict with "found" (False if nothing is known about this item
        yet), "explanation" (a short human-readable reason), "hops" (the
        structured list of nodes/relationships/properties that explanation
        was built from), and "cypher" (the named Cypher queries actually
        run against FalkorDB to produce it).
    """
    return explain_path(sku_or_name)
