"""
scripts/seed_graph.py

Generates ~60 days of synthetic purchase history into FalkorDB for two demo
users ("demo" and "demo2"), from the catalog in knowledge/catalog.py — new
work for Graph Hacks (WeMakeDevs x FalkorDB), Oct 15-18 2026. Every item,
quantity, and timestamp here is synthetic/deterministic (fixed random
seed); nothing from a real Zepto/Blinkit session or wallet is ever loaded
into this graph, per the hackathon's data rules.

Idempotent: clears each user's graph before reloading, so running this
twice (or after changing the catalog) never leaves stale/duplicate nodes.

Usage:
    python scripts/seed_graph.py
"""

import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from knowledge.catalog import PRODUCTS, SUBSTITUTE_PAIRS  # noqa: E402
from knowledge.graph import clear_graph, graph_for, record_decision, record_purchase  # noqa: E402

DAYS_OF_HISTORY = 60

# A deterministic "household" per demo user: which items they buy, roughly
# how regularly, and loose co-purchase groupings so CO_PURCHASED_WITH ends
# up with a realistic shape rather than every item linking to every other.
HOUSEHOLDS = {
    "demo": {
        "seed": 42,
        "staples": [
            "amul milk 500ml", "bread", "eggs 6 pack", "bananas 6 pack", "onion 1kg",
            "tomato 1kg", "basmati rice 1kg", "toor dal 1kg", "atta 5kg", "sunflower oil 1l",
            "sugar 1kg", "salt 1kg", "tea powder 250g", "curd 400g", "biscuits pack",
        ],
        "occasional": [
            "paneer 200g", "butter 100g", "apples 4 pack", "potato 1kg", "spinach bunch",
            "oats 1kg", "chana dal 1kg", "chips pack", "namkeen 200g", "dish wash liquid 500ml",
            "toilet paper pack", "detergent powder 1kg",
        ],
        "co_groups": [
            ["amul milk 500ml", "bread", "eggs 6 pack"],
            ["onion 1kg", "tomato 1kg", "potato 1kg"],
            ["basmati rice 1kg", "toor dal 1kg", "sunflower oil 1l"],
            ["tea powder 250g", "sugar 1kg", "biscuits pack"],
        ],
    },
    "demo2": {
        "seed": 7,
        "staples": [
            "toned milk 1l", "brown bread", "eggs 12 pack", "apples 4 pack", "spinach bunch",
            "sona masoori rice 5kg", "moong dal 1kg", "atta 5kg", "sunflower oil 1l",
            "coffee powder 200g", "oats 1kg", "curd 400g", "namkeen 200g",
        ],
        "occasional": [
            "full cream milk 1l", "butter 100g", "bananas 6 pack", "ginger garlic paste 200g",
            "poha 500g", "rajma 500g", "vermicelli 200g", "chips pack", "biscuits pack",
            "detergent powder 1kg", "toilet paper pack", "dish wash liquid 500ml",
        ],
        "co_groups": [
            ["toned milk 1l", "brown bread", "eggs 12 pack"],
            ["spinach bunch", "ginger garlic paste 200g"],
            ["sona masoori rice 5kg", "moong dal 1kg", "sunflower oil 1l"],
            ["coffee powder 200g", "biscuits pack"],
        ],
    },
}

# interval_days per sku, looked up from the catalog, drives how often a
# synthetic household "reorders" that item within the 60-day window.
_INTERVALS = {p["sku"]: p["interval_days"] for p in PRODUCTS}

PLATFORMS = ["zepto", "blinkit"]


def _seed_household(user_id: str, config: dict, now: datetime) -> dict:
    rng = random.Random(config["seed"])
    clear_graph(user_id)

    start = now - timedelta(days=DAYS_OF_HISTORY)
    orders_written = 0

    all_items = config["staples"] + config["occasional"]
    # Walk forward in time, placing an order every few days, drawing from
    # staples (reliably) plus occasional items and whole co-purchase groups.
    t = start
    while t < now:
        gap = rng.uniform(1.5, 4.0)
        t += timedelta(days=gap)
        if t >= now:
            break

        basket: set[str] = set()
        # 1-2 staples due around now, biased by their catalog interval.
        for sku in rng.sample(config["staples"], k=min(3, len(config["staples"]))):
            if rng.random() < 0.6:
                basket.add(sku)
        # occasionally pull in a whole co-purchase group intact
        if rng.random() < 0.5:
            group = rng.choice(config["co_groups"])
            basket.update(group)
        # a sprinkle of occasional items
        for sku in rng.sample(config["occasional"], k=min(2, len(config["occasional"]))):
            if rng.random() < 0.3:
                basket.add(sku)

        if not basket:
            basket.add(rng.choice(all_items))

        platform = rng.choice(PLATFORMS)
        record_purchase(list(basket), when=t, platform=platform, user_id=user_id)
        orders_written += 1

    return {"orders": orders_written}


def _seed_substitutes_and_decisions(user_id: str, now: datetime) -> dict:
    g = graph_for(user_id)
    for a, b, reason in SUBSTITUTE_PAIRS:
        g.query(
            """
            MERGE (pa:Product {sku: $a}) ON CREATE SET pa.name = $a, pa.category = 'uncategorized',
                  pa.purchase_count = 0, pa.interval_sum_days = 0.0
            MERGE (pb:Product {sku: $b}) ON CREATE SET pb.name = $b, pb.category = 'uncategorized',
                  pb.purchase_count = 0, pb.interval_sum_days = 0.0
            MERGE (pa)-[e:SUBSTITUTE_FOR {reason: $reason}]-(pb)
            """,
            {"a": a, "b": b, "reason": reason},
        )

    # A few synthetic episodic decisions from "earlier sessions" — the kind
    # of thing recall_decisions() should be able to surface to a later run.
    decisions = [
        ("toned milk 1l", "accepted_substitute", "full cream milk 1l was out of stock", now - timedelta(days=12)),
        ("white bread", "rejected_substitute", "household prefers brown bread", now - timedelta(days=20)),
        ("basmati rice 1kg", "out_of_stock", "unavailable on Zepto, ordered on Blinkit instead", now - timedelta(days=5)),
    ]
    for sku, action, reason, ts in decisions:
        record_decision(sku, action=action, reason=reason, goal="restock the pantry", when=ts, user_id=user_id)

    return {"substitute_pairs": len(SUBSTITUTE_PAIRS), "decisions": len(decisions)}


def _counts(user_id: str) -> dict:
    g = graph_for(user_id)
    node_count = g.query("MATCH (n) RETURN count(n)").result_set[0][0]
    edge_count = g.query("MATCH ()-[r]->() RETURN count(r)").result_set[0][0]
    return {"nodes": node_count, "edges": edge_count}


def main() -> None:
    now = datetime.now(timezone.utc)
    for user_id, config in HOUSEHOLDS.items():
        print(f"Seeding graph for user {user_id!r}...")
        order_stats = _seed_household(user_id, config, now)
        extra_stats = _seed_substitutes_and_decisions(user_id, now)
        counts = _counts(user_id)
        print(
            f"  orders={order_stats['orders']} substitute_pairs={extra_stats['substitute_pairs']} "
            f"decisions={extra_stats['decisions']} -> nodes={counts['nodes']} edges={counts['edges']}"
        )
    print("Done.")


if __name__ == "__main__":
    main()
