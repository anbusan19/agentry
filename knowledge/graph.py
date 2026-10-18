"""
knowledge/graph.py

Agentry's purchase-history memory, now backed by FalkorDB instead of a
local NetworkX JSON file — rewritten for Graph Hacks (WeMakeDevs x
FalkorDB), Track 02 (Agent Memory and Coordination). This is new work done
during Oct 15-18, 2026; see the README's "Graph Hacks submission" section
for the disclosure this hackathon's rules require. NetworkX has been
removed entirely from this project — if FalkorDB is unreachable, these
functions raise, they do not fall back to a local file.

One graph per user: db.select_graph(f"agentry:{user_id}") — AGENTRY_USER_ID
(default "demo") picks which one a given process talks to, so "demo" and
"demo2" (seeded by scripts/seed_graph.py) are fully isolated memories.

Data model (see README for the full table):
  (:User {id})
  (:Product {sku, name, category, purchase_count, interval_sum_days,
              avg_interval_days, last_purchased_ts})
  (:Order {id, ts})
  (:Category {name})
  (:Session {id, ts, goal})

  (:User)-[:PURCHASED {ts, qty, order_id}]->(:Product)
  (:User)-[:PLACED]->(:Order)
  (:Order)-[:CONTAINS {qty}]->(:Product)
  (:Product)-[:CO_PURCHASED_WITH {count, last_ts}]->(:Product)  -- stored
      once per unordered pair, sku-sorted, so "-[:CO_PURCHASED_WITH]-"
      (no arrow) is how every read query walks it in either direction.
  (:Product)-[:IN_CATEGORY]->(:Category)
  (:Product)-[:SUBSTITUTE_FOR {reason}]->(:Product)
  (:Session)-[:DECIDED {action, reason}]->(:Product)  -- episodic memory:
      "purchased" (written automatically by record_purchase), or
      "accepted_substitute" / "rejected_substitute" / "out_of_stock"
      (written by seed_graph.py's synthetic history for the demo).

Every write/read below is a parameterized Cypher query (g.query(q, params))
against the official `falkordb` Python client — no string-built queries,
no local JSON, no NetworkX anywhere in this file.
"""

import os
from datetime import datetime, timezone
from typing import Optional

from falkordb import FalkorDB

_client: Optional[FalkorDB] = None
_indexed_graphs: set[str] = set()


def _normalize(item: str) -> str:
    return " ".join(item.strip().lower().split())


def _db() -> FalkorDB:
    global _client
    if _client is None:
        _client = FalkorDB(
            host=os.environ.get("FALKORDB_HOST", "localhost"),
            port=int(os.environ.get("FALKORDB_PORT", 6379)),
            password=os.environ.get("FALKORDB_PASSWORD") or None,
        )
    return _client


def _resolve_user(user_id: Optional[str]) -> str:
    return user_id or os.environ.get("AGENTRY_USER_ID", "demo")


def graph_for(user_id: Optional[str] = None):
    """The FalkorDB graph for one user's memory — select_graph is a cheap
    handle, not a connection, so there's no pooling/caching needed beyond
    the client itself."""
    user_id = _resolve_user(user_id)
    g = _db().select_graph(f"agentry:{user_id}")
    if user_id not in _indexed_graphs:
        for query in (
            "CREATE INDEX FOR (p:Product) ON (p.sku)",
            "CREATE INDEX FOR (o:Order) ON (o.id)",
        ):
            try:
                g.query(query)
            except Exception:
                pass  # already exists
        _indexed_graphs.add(user_id)
    return g


def clear_graph(user_id: Optional[str] = None) -> None:
    """Wipe one user's graph entirely — used by scripts/seed_graph.py to
    make reseeding idempotent."""
    g = graph_for(user_id)
    try:
        g.query("MATCH (n) DETACH DELETE n")
    except Exception:
        pass
    _indexed_graphs.discard(_resolve_user(user_id))


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _upsert_product(g, sku: str, name: Optional[str] = None, category: Optional[str] = None) -> None:
    g.query(
        """
        MERGE (p:Product {sku: $sku})
        ON CREATE SET p.name = $name, p.category = $category,
                      p.purchase_count = 0, p.interval_sum_days = 0.0,
                      p.avg_interval_days = null, p.last_purchased_ts = null
        """,
        {"sku": sku, "name": name or sku, "category": category or "uncategorized"},
    )
    if category:
        g.query(
            """
            MATCH (p:Product {sku: $sku})
            MERGE (c:Category {name: $category})
            MERGE (p)-[:IN_CATEGORY]->(c)
            """,
            {"sku": sku, "category": category},
        )


def _bump_purchase_stats(g, sku: str, ts_iso: str, when: datetime) -> None:
    """Read this product's current stats, compute the new rolling average
    restock interval in Python (FalkorDB's Cypher dialect doesn't reliably
    support Neo4j-style duration arithmetic), then write it back."""
    result = g.query(
        "MATCH (p:Product {sku: $sku}) RETURN p.purchase_count, p.interval_sum_days, p.last_purchased_ts",
        {"sku": sku},
    )
    purchase_count, interval_sum_days, last_ts = result.result_set[0]
    interval_sum_days = interval_sum_days or 0.0
    purchase_count = purchase_count or 0

    if last_ts:
        last_dt = datetime.fromisoformat(last_ts)
        gap_days = (when - last_dt).total_seconds() / 86400
        interval_sum_days += max(gap_days, 0.0)

    purchase_count += 1
    avg_interval = interval_sum_days / (purchase_count - 1) if purchase_count > 1 else None

    g.query(
        """
        MATCH (p:Product {sku: $sku})
        SET p.purchase_count = $pc, p.interval_sum_days = $isd,
            p.last_purchased_ts = $ts, p.avg_interval_days = $avg
        """,
        {"sku": sku, "pc": purchase_count, "isd": interval_sum_days, "ts": ts_iso, "avg": avg_interval},
    )


def record_purchase(
    items: list[str],
    when: Optional[datetime] = None,
    platform: str = "zepto",
    user_id: Optional[str] = None,
) -> dict:
    """Log one order's items: a PURCHASED edge + updated restock-interval
    stats on each Product, a CO_PURCHASED_WITH edge (or bumped count)
    between every pair bought together, and a Session/DECIDED edge per item
    so this order shows up in episodic memory too."""
    when = when or datetime.now(timezone.utc)
    ts = when.isoformat()
    user_id = _resolve_user(user_id)
    g = graph_for(user_id)

    normalized = [_normalize(i) for i in items if i.strip()]
    if not normalized:
        return {"recorded": 0}

    order_id = f"ord-{int(when.timestamp() * 1000)}"
    session_id = f"sess-{order_id}"

    g.query(
        """
        MERGE (u:User {id: $user_id})
        CREATE (o:Order {id: $order_id, ts: $ts})
        CREATE (s:Session {id: $session_id, ts: $ts, goal: 'purchase'})
        CREATE (u)-[:PLACED]->(o)
        """,
        {"user_id": user_id, "order_id": order_id, "ts": ts, "session_id": session_id, "platform": platform},
    )

    for item in normalized:
        _upsert_product(g, item)
        g.query(
            """
            MATCH (u:User {id: $user_id}), (o:Order {id: $order_id}), (s:Session {id: $session_id}),
                  (p:Product {sku: $sku})
            CREATE (u)-[:PURCHASED {ts: $ts, qty: 1, order_id: $order_id, platform: $platform}]->(p)
            CREATE (o)-[:CONTAINS {qty: 1}]->(p)
            CREATE (s)-[:DECIDED {action: 'purchased', reason: 'order'}]->(p)
            """,
            {"user_id": user_id, "order_id": order_id, "session_id": session_id, "sku": item, "ts": ts, "platform": platform},
        )
        _bump_purchase_stats(g, item, ts, when)

    for i, a in enumerate(normalized):
        for b in normalized[i + 1 :]:
            if a == b:
                continue
            lo, hi = sorted([a, b])
            g.query(
                """
                MATCH (pa:Product {sku: $lo}), (pb:Product {sku: $hi})
                MERGE (pa)-[r:CO_PURCHASED_WITH]->(pb)
                ON CREATE SET r.count = 1, r.last_ts = $ts
                ON MATCH SET r.count = r.count + 1, r.last_ts = $ts
                """,
                {"lo": lo, "hi": hi, "ts": ts},
            )

    return {"recorded": len(normalized), "order_id": order_id}


def record_decision(
    sku: str,
    action: str,
    reason: str = "",
    goal: str = "",
    when: Optional[datetime] = None,
    user_id: Optional[str] = None,
) -> dict:
    """Write one episodic-memory decision (a substitution accepted/rejected,
    an out-of-stock event, etc.) as a Session-[:DECIDED]->Product edge, so a
    later session can recall it via recall_decisions(). Used by
    scripts/seed_graph.py to seed synthetic decision history, and available
    for the agent to call directly when it makes a real substitution call."""
    when = when or datetime.now(timezone.utc)
    ts = when.isoformat()
    g = graph_for(user_id)
    sku = _normalize(sku)
    _upsert_product(g, sku)
    session_id = f"sess-decision-{int(when.timestamp() * 1000)}"
    g.query(
        """
        CREATE (s:Session {id: $session_id, ts: $ts, goal: $goal})
        WITH s
        MATCH (p:Product {sku: $sku})
        CREATE (s)-[:DECIDED {action: $action, reason: $reason}]->(p)
        """,
        {"session_id": session_id, "ts": ts, "goal": goal, "sku": sku, "action": action, "reason": reason},
    )
    return {"status": "ok", "session_id": session_id}


# ---------------------------------------------------------------------------
# Reads — restock timing, co-purchase, substitutes, episodic recall
# ---------------------------------------------------------------------------


def restock_suggestions(within_days: float = 3.0, now: Optional[datetime] = None, user_id: Optional[str] = None) -> dict:
    """Cypher equivalent of due_for_restock: products whose avg restock
    interval says they're due (or overdue) within `within_days`, each with
    its top co-purchased items."""
    now = now or datetime.now(timezone.utc)
    g = graph_for(user_id)

    rows = g.query(
        """
        MATCH (p:Product)
        WHERE p.avg_interval_days IS NOT NULL AND p.last_purchased_ts IS NOT NULL
        RETURN p.sku, p.avg_interval_days, p.last_purchased_ts
        """
    ).result_set

    due = []
    for sku, interval, last_ts in rows:
        last = datetime.fromisoformat(last_ts)
        days_since = (now - last).total_seconds() / 86400
        days_until_due = interval - days_since
        if days_until_due > within_days:
            continue

        neighbors = g.query(
            """
            MATCH (p:Product {sku: $sku})-[r:CO_PURCHASED_WITH]-(n:Product)
            RETURN n.sku, r.count ORDER BY r.count DESC LIMIT 3
            """,
            {"sku": sku},
        ).result_set

        due.append(
            {
                "item": sku,
                "usual_interval_days": round(interval, 1),
                "days_since_last": round(days_since, 1),
                "overdue": days_until_due < 0,
                "often_bought_with": [n[0] for n in neighbors],
            }
        )

    due.sort(key=lambda d: d["days_since_last"] - d["usual_interval_days"], reverse=True)
    return {"due": due}


def search_items(keyword: str, user_id: Optional[str] = None) -> list[dict]:
    """Cypher substring search over every Product's sku/name, case
    insensitive — answers "how many times have I ordered X" for anything
    in history, not just items with a repeat pattern."""
    needle = _normalize(keyword)
    if not needle:
        return []
    g = graph_for(user_id)
    rows = g.query(
        """
        MATCH (p:Product)
        WHERE toLower(p.sku) CONTAINS $needle OR toLower(p.name) CONTAINS $needle
        RETURN p.sku, p.purchase_count, p.last_purchased_ts
        """,
        {"needle": needle},
    ).result_set

    matches = [
        {"item": sku, "times_ordered": count or 0, "last_purchased": last_ts}
        for sku, count, last_ts in rows
    ]
    matches.sort(key=lambda m: m["last_purchased"] or "", reverse=True)
    return matches


def co_purchase_suggestions(seed_skus: list[str], limit: int = 5, user_id: Optional[str] = None) -> list[dict]:
    """Round out a cart: items frequently co-purchased with any seed item
    (1-hop CO_PURCHASED_WITH), plus items sharing a Category with a seed
    item (2-hop via :IN_CATEGORY) as a weaker secondary signal — excludes
    anything already in the seed set."""
    seeds = [_normalize(s) for s in seed_skus]
    g = graph_for(user_id)

    # LIMIT is interpolated as a plain int literal, not a $param — FalkorDB's
    # Cypher dialect doesn't reliably accept a parameterized LIMIT. `limit`
    # is always a caller-supplied int (never raw user text), so this is safe.
    co_rows = g.query(
        f"""
        UNWIND $seeds AS seed
        MATCH (s:Product {{sku: seed}})-[r:CO_PURCHASED_WITH]-(p:Product)
        WHERE NOT p.sku IN $seeds
        RETURN p.sku, p.name, sum(r.count) AS score
        ORDER BY score DESC LIMIT {int(limit)}
        """,
        {"seeds": seeds},
    ).result_set

    scores: dict[str, dict] = {
        sku: {"sku": sku, "name": name, "score": float(score), "via": "co_purchased"} for sku, name, score in co_rows
    }

    if len(scores) < limit:
        cat_rows = g.query(
            f"""
            UNWIND $seeds AS seed
            MATCH (s:Product {{sku: seed}})-[:IN_CATEGORY]->(c:Category)<-[:IN_CATEGORY]-(p:Product)
            WHERE NOT p.sku IN $seeds AND NOT p.sku IN $existing
            RETURN p.sku, p.name, count(*) AS score
            ORDER BY score DESC LIMIT {int(limit) - len(scores)}
            """,
            {"seeds": seeds, "existing": list(scores)},
        ).result_set
        for sku, name, score in cat_rows:
            scores[sku] = {"sku": sku, "name": name, "score": float(score) * 0.5, "via": "same_category"}

    return sorted(scores.values(), key=lambda s: s["score"], reverse=True)[:limit]


def substitute_candidates(sku: str, user_id: Optional[str] = None) -> list[dict]:
    """Substitute candidates for a product: explicit SUBSTITUTE_FOR edges,
    ranked up by any prior session that accepted that same substitute for
    this item (episodic memory), and down by any that rejected it."""
    sku = _normalize(sku)
    g = graph_for(user_id)

    base = g.query(
        """
        MATCH (p:Product {sku: $sku})-[e:SUBSTITUTE_FOR]-(sub:Product)
        RETURN sub.sku, sub.name, e.reason
        """,
        {"sku": sku},
    ).result_set

    history = recall_decisions(sku, user_id=user_id)
    accepted = {d["sku"] for d in history if d["action"] == "accepted_substitute"}
    rejected = {d["sku"] for d in history if d["action"] == "rejected_substitute"}

    candidates = []
    for sub_sku, sub_name, reason in base:
        candidates.append(
            {
                "sku": sub_sku,
                "name": sub_name,
                "reason": reason,
                "previously_accepted": sub_sku in accepted,
                "previously_rejected": sub_sku in rejected,
            }
        )
    candidates.sort(key=lambda c: (c["previously_rejected"], not c["previously_accepted"]))
    return candidates


def recall_decisions(sku: str, user_id: Optional[str] = None) -> list[dict]:
    """Episodic memory: every past Session-[:DECIDED]->Product decision
    recorded against this product (a purchase, an accepted/rejected
    substitution, an out-of-stock event), most recent first."""
    sku = _normalize(sku)
    g = graph_for(user_id)
    rows = g.query(
        """
        MATCH (s:Session)-[d:DECIDED]->(p:Product {sku: $sku})
        RETURN s.id, s.ts, s.goal, d.action, d.reason
        ORDER BY s.ts DESC
        """,
        {"sku": sku},
    ).result_set
    return [
        {"session_id": sid, "ts": ts, "goal": goal, "action": action, "reason": reason}
        for sid, ts, goal, action, reason in rows
    ]


def explain_path(sku_or_name: str, user_id: Optional[str] = None) -> dict:
    """The structured reasoning behind a restock suggestion for one
    product: its own restock-timing stats, its co-purchase neighbors, any
    substitute edges, and its episodic decision history — plus the exact
    Cypher used for each, so tools/explain_suggestion.py can show a
    traceable reason instead of an opaque "trust me"."""
    sku = _normalize(sku_or_name)
    g = graph_for(user_id)

    queries = {
        "restock_stats": "MATCH (p:Product {sku: $sku}) RETURN p.sku, p.name, p.avg_interval_days, p.last_purchased_ts, p.purchase_count",
        "co_purchased": "MATCH (p:Product {sku: $sku})-[r:CO_PURCHASED_WITH]-(n:Product) RETURN n.sku, r.count ORDER BY r.count DESC LIMIT 5",
        "substitutes": "MATCH (p:Product {sku: $sku})-[e:SUBSTITUTE_FOR]-(n:Product) RETURN n.sku, e.reason",
        "decisions": "MATCH (s:Session)-[d:DECIDED]->(p:Product {sku: $sku}) RETURN s.ts, d.action, d.reason ORDER BY s.ts DESC LIMIT 5",
    }

    stats_rows = g.query(queries["restock_stats"], {"sku": sku}).result_set
    if not stats_rows:
        return {
            "sku": sku,
            "found": False,
            "hops": [],
            "explanation": f'No purchase history found for "{sku_or_name}" yet.',
            "cypher": queries,
        }

    _, name, avg_interval, last_ts, purchase_count = stats_rows[0]
    co_rows = g.query(queries["co_purchased"], {"sku": sku}).result_set
    sub_rows = g.query(queries["substitutes"], {"sku": sku}).result_set
    decision_rows = g.query(queries["decisions"], {"sku": sku}).result_set

    hops = [
        {
            "node": {"label": "Product", "sku": sku, "name": name},
            "relationship": None,
            "properties": {
                "purchase_count": purchase_count,
                "avg_interval_days": avg_interval,
                "last_purchased_ts": last_ts,
            },
        }
    ]
    for n_sku, count in co_rows:
        hops.append({"node": {"label": "Product", "sku": n_sku}, "relationship": "CO_PURCHASED_WITH", "properties": {"count": count}})
    for n_sku, reason in sub_rows:
        hops.append({"node": {"label": "Product", "sku": n_sku}, "relationship": "SUBSTITUTE_FOR", "properties": {"reason": reason}})
    for ts, action, reason in decision_rows:
        hops.append({"node": {"label": "Session", "ts": ts}, "relationship": "DECIDED", "properties": {"action": action, "reason": reason}})

    lines = [f'"{name}" has been bought {purchase_count} time(s).']
    if avg_interval and last_ts:
        now = datetime.now(timezone.utc)
        days_since = (now - datetime.fromisoformat(last_ts)).total_seconds() / 86400
        lines.append(
            f"Usual restock interval is about {round(avg_interval, 1)} days; "
            f"it's been {round(days_since, 1)} days since the last purchase."
        )
    if co_rows:
        lines.append("Often bought alongside: " + ", ".join(f"{s} ({c}x)" for s, c in co_rows[:3]) + ".")
    if sub_rows:
        lines.append("Known substitutes: " + ", ".join(s for s, _ in sub_rows) + ".")
    if decision_rows:
        lines.append(f"{len(decision_rows)} prior decision(s) on record for this item.")

    return {
        "sku": sku,
        "found": True,
        "hops": hops,
        "explanation": " ".join(lines),
        "cypher": queries,
    }


def rank_anchor_items(limit: int = 10, user_id: Optional[str] = None) -> dict:
    """The one FalkorDB graph-algorithm call this product depends on:
    PageRank over the Product/CO_PURCHASED_WITH subgraph, to surface which
    items are the real "anchors" of this household's shopping pattern —
    the ones most central to its co-purchase network, not just the
    most-frequently-bought in isolation."""
    g = graph_for(user_id)
    cypher = (
        "CALL algo.pageRank('Product', 'CO_PURCHASED_WITH') YIELD node, score "
        f"RETURN node.sku, score ORDER BY score DESC LIMIT {int(limit)}"
    )
    try:
        rows = g.query(cypher).result_set
    except Exception as exc:
        return {"anchors": [], "cypher": cypher, "error": str(exc)}
    return {"anchors": [{"sku": sku, "score": round(score, 4)} for sku, score in rows], "cypher": cypher}


def graph_snapshot(within_days: float = 3.0, user_id: Optional[str] = None, max_edges: int = 200) -> dict:
    """Nodes/edges/clusters shaped for the console's force-directed view
    (server.py's GET /graph), read straight from FalkorDB — the visual is
    driven by the same graph the agent reasons over, not a separate cache."""
    g = graph_for(user_id)
    due_by_sku = {d["item"]: d for d in restock_suggestions(within_days=within_days, user_id=user_id)["due"]}

    node_rows = g.query(
        "MATCH (p:Product) RETURN p.sku, p.purchase_count, p.last_purchased_ts, p.category"
    ).result_set

    platform_rows = g.query(
        "MATCH (:User)-[r:PURCHASED]->(p:Product) RETURN p.sku, r.platform, count(*) AS n"
    ).result_set
    platforms_by_sku: dict[str, list[tuple[str, int]]] = {}
    for sku, platform, n in platform_rows:
        platforms_by_sku.setdefault(sku, []).append((platform or "zepto", n))

    def _ranked_platforms(sku: str) -> list[str]:
        counts = sorted(platforms_by_sku.get(sku, []), key=lambda pair: pair[1], reverse=True)
        return [p for p, _ in counts]

    nodes = [
        {
            "id": sku,
            "purchase_count": count or 0,
            "last_purchased": last_ts,
            "overdue": due_by_sku.get(sku, {}).get("overdue", False),
            "due_soon": sku in due_by_sku,
            "platforms": _ranked_platforms(sku),
            "category": category,
        }
        for sku, count, last_ts, category in node_rows
    ]

    edge_rows = g.query(
        f"MATCH (a:Product)-[r:CO_PURCHASED_WITH]-(b:Product) WHERE a.sku < b.sku RETURN a.sku, b.sku, r.count LIMIT {int(max_edges)}"
    ).result_set
    links = [{"source": a, "target": b, "weight": weight or 1} for a, b, weight in edge_rows]

    adjacency: dict[str, set[str]] = {}
    for a, b, _ in edge_rows:
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)

    seen: set[str] = set()
    clusters = []
    for sku in adjacency:
        if sku in seen:
            continue
        stack, component = [sku], set()
        while stack:
            cur = stack.pop()
            if cur in component:
                continue
            component.add(cur)
            stack.extend(adjacency.get(cur, ()) - component)
        seen |= component
        if len(component) >= 2:
            clusters.append({"id": len(clusters), "items": sorted(component), "platforms": []})

    return {"nodes": nodes, "links": links, "clusters": clusters}
