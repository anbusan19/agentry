"""
tools/rank_anchor_items.py

New for Graph Hacks (WeMakeDevs x FalkorDB) — the one FalkorDB
graph-algorithm call this product depends on (per the hackathon's Track 01
"Agents That Act on Connected Data" angle). Runs PageRank over the
Product/CO_PURCHASED_WITH subgraph in knowledge/graph.py's rank_anchor_items,
to surface which items are the real structural "anchors" of this
household's shopping pattern, not just the most-frequently-bought item in
isolation.
"""

from strands import tool

from knowledge.graph import rank_anchor_items as _rank_anchor_items


@tool
def rank_anchor_items(limit: int = 10) -> dict:
    """
    Rank this household's items by how central they are in the
    co-purchase graph (FalkorDB's algo.pageRank over Product nodes and
    CO_PURCHASED_WITH edges), not just by raw purchase count. The top
    results are the "anchor" items everything else tends to cluster
    around — useful context for deciding what a restock list should be
    built outward from.

    Args:
        limit: Max number of ranked items to return (default 10).

    Returns:
        A dict with "anchors" (list of {sku, score}, highest first) and
        "cypher" (the exact query run). "anchors" can come back empty for
        a brand-new or very small household graph, which is expected.
    """
    return _rank_anchor_items(limit=limit)
