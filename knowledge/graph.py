"""
knowledge/graph.py

A small purchase-history knowledge graph: not a tool itself, this is the
shared logic behind tools/record_purchase.py,
tools/get_restock_suggestions.py, and tools/query_purchase_history.py.

Nodes are items (normalized by name). Each item node carries a list of past
purchase timestamps, used to estimate a restock interval. Edges between two
items carry a co_purchase count, incremented whenever they show up in the
same order — this is what lets get_restock_suggestions round out a restock
list ("you usually buy X with Y").

Storage is a single JSON file (data/purchases_graph.json, gitignored — this
is real personal shopping history, not something to ship in the repo) built
on NetworkX's node-link format, loaded fresh and saved back on every write.
No database needed for something this small.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Optional

import networkx as nx

GRAPH_FILE = Path(__file__).parent.parent / "data" / "purchases_graph.json"


def _normalize(item: str) -> str:
    return " ".join(item.strip().lower().split())


def load_graph() -> nx.Graph:
    if not GRAPH_FILE.exists():
        return nx.Graph()
    with open(GRAPH_FILE) as f:
        data = json.load(f)
    return nx.node_link_graph(data, edges="edges")


def save_graph(graph: nx.Graph) -> None:
    GRAPH_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(GRAPH_FILE, "w") as f:
        json.dump(nx.node_link_data(graph, edges="edges"), f, indent=2)


def record_purchase(items: list[str], when: Optional[datetime] = None) -> nx.Graph:
    """Log one order's items into the graph: a purchase timestamp on each
    item node, and a co_purchase edge (or incremented weight) between every
    pair of items bought together in this order."""
    when = when or datetime.now(timezone.utc)
    timestamp = when.isoformat()

    graph = load_graph()
    normalized = [_normalize(i) for i in items if i.strip()]

    for item in normalized:
        if item not in graph:
            graph.add_node(item, purchases=[])
        graph.nodes[item]["purchases"].append(timestamp)

    for i, item_a in enumerate(normalized):
        for item_b in normalized[i + 1 :]:
            if item_a == item_b:
                continue
            if graph.has_edge(item_a, item_b):
                graph[item_a][item_b]["co_purchase"] += 1
            else:
                graph.add_edge(item_a, item_b, co_purchase=1)

    save_graph(graph)
    return graph


def _avg_interval_days(purchases: list[str]) -> Optional[float]:
    if len(purchases) < 2:
        return None
    dates = sorted(datetime.fromisoformat(p) for p in purchases)
    gaps = [(b - a).total_seconds() / 86400 for a, b in zip(dates, dates[1:])]
    return mean(gaps)


def restock_suggestions(within_days: float = 3.0, now: Optional[datetime] = None) -> dict:
    """Return items whose typical restock interval says they're due (or
    overdue) within `within_days`, each with its top co-purchased items."""
    now = now or datetime.now(timezone.utc)
    graph = load_graph()

    due = []
    for item, attrs in graph.nodes(data=True):
        purchases = attrs.get("purchases", [])
        interval = _avg_interval_days(purchases)
        if interval is None:
            continue

        last = max(datetime.fromisoformat(p) for p in purchases)
        days_since = (now - last).total_seconds() / 86400
        days_until_due = interval - days_since

        if days_until_due <= within_days:
            neighbors = sorted(
                graph[item].items(),
                key=lambda kv: kv[1].get("co_purchase", 0),
                reverse=True,
            )
            due.append(
                {
                    "item": item,
                    "usual_interval_days": round(interval, 1),
                    "days_since_last": round(days_since, 1),
                    "overdue": days_until_due < 0,
                    "often_bought_with": [n for n, _ in neighbors[:3]],
                }
            )

    due.sort(key=lambda d: d["days_since_last"] - d["usual_interval_days"], reverse=True)
    return {"due": due}


def search_items(keyword: str) -> list[dict]:
    """Find every item whose name contains `keyword` (case-insensitive),
    with how many separate orders it showed up in and when it was last
    bought. This is a plain substring match over the graph's nodes, not
    restricted to items with a repeat pattern the way restock_suggestions
    is — it answers "how many times have I ordered X" for anything in the
    history, even a one-off purchase."""
    graph = load_graph()
    needle = _normalize(keyword)
    if not needle:
        return []

    matches = []
    for item, attrs in graph.nodes(data=True):
        if needle not in item:
            continue
        purchases = attrs.get("purchases", [])
        matches.append(
            {
                "item": item,
                "times_ordered": len(purchases),
                "last_purchased": max(purchases) if purchases else None,
            }
        )

    matches.sort(key=lambda m: m["last_purchased"] or "", reverse=True)
    return matches
