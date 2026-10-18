"""
knowledge/catalog.py

A small synthetic grocery catalog — ~40 everyday Indian-household items
across a handful of categories, each with a plausible real-world restock
interval. Built fresh for Graph Hacks (WeMakeDevs x FalkorDB), not part of
the original Agentry port.

Two things depend on this list:
  - scripts/seed_graph.py uses it (plus the interval hints) to generate
    synthetic purchase history for the FalkorDB demo graph.
  - tools/_dry_run.py uses it as a mock storefront catalog so
    search_products/add_to_cart/view_cart/checkout can run end-to-end
    without Playwright or a real storefront login when AGENTRY_DRY_RUN=1.

No real order, wallet, or session data lives here or is ever loaded into
it — this is the synthetic/public data the hackathon rules require.
"""

# sku doubles as the normalized item name (matches knowledge/graph.py's
# _normalize convention, so dry-run purchases line up with the same graph
# nodes a seeded demo already created).
PRODUCTS = [
    {"sku": "amul milk 500ml", "name": "Amul Milk 500ml", "category": "dairy", "price": 28, "interval_days": 2},
    {"sku": "toned milk 1l", "name": "Toned Milk 1L", "category": "dairy", "price": 54, "interval_days": 2},
    {"sku": "full cream milk 1l", "name": "Full Cream Milk 1L", "category": "dairy", "price": 66, "interval_days": 3},
    {"sku": "curd 400g", "name": "Curd 400g", "category": "dairy", "price": 40, "interval_days": 4},
    {"sku": "paneer 200g", "name": "Paneer 200g", "category": "dairy", "price": 80, "interval_days": 7},
    {"sku": "butter 100g", "name": "Butter 100g", "category": "dairy", "price": 52, "interval_days": 14},
    {"sku": "eggs 6 pack", "name": "Eggs (6 pack)", "category": "dairy", "price": 42, "interval_days": 5},
    {"sku": "eggs 12 pack", "name": "Eggs (12 pack)", "category": "dairy", "price": 78, "interval_days": 9},
    {"sku": "bread", "name": "Bread", "category": "bakery", "price": 45, "interval_days": 4},
    {"sku": "brown bread", "name": "Brown Bread", "category": "bakery", "price": 50, "interval_days": 4},
    {"sku": "white bread", "name": "White Bread", "category": "bakery", "price": 45, "interval_days": 4},
    {"sku": "bun pack", "name": "Bun Pack", "category": "bakery", "price": 35, "interval_days": 10},
    {"sku": "rusk", "name": "Rusk", "category": "bakery", "price": 60, "interval_days": 12},
    {"sku": "basmati rice 1kg", "name": "Basmati Rice 1kg", "category": "grains", "price": 120, "interval_days": 20},
    {"sku": "sona masoori rice 5kg", "name": "Sona Masoori Rice 5kg", "category": "grains", "price": 320, "interval_days": 30},
    {"sku": "atta 5kg", "name": "Fortune Chakki Fresh Atta 5kg", "category": "grains", "price": 240, "interval_days": 25},
    {"sku": "oats 1kg", "name": "Oats 1kg", "category": "grains", "price": 150, "interval_days": 18},
    {"sku": "poha 500g", "name": "Poha 500g", "category": "grains", "price": 45, "interval_days": 15},
    {"sku": "vermicelli 200g", "name": "Vermicelli 200g", "category": "grains", "price": 35, "interval_days": 20},
    {"sku": "toor dal 1kg", "name": "Toor Dal 1kg", "category": "pulses", "price": 160, "interval_days": 20},
    {"sku": "moong dal 1kg", "name": "Moong Dal 1kg", "category": "pulses", "price": 140, "interval_days": 20},
    {"sku": "chana dal 1kg", "name": "Chana Dal 1kg", "category": "pulses", "price": 130, "interval_days": 22},
    {"sku": "rajma 500g", "name": "Rajma 500g", "category": "pulses", "price": 85, "interval_days": 25},
    {"sku": "bananas 6 pack", "name": "Bananas (6 pack)", "category": "produce", "price": 40, "interval_days": 4},
    {"sku": "onion 1kg", "name": "Onion 1kg", "category": "produce", "price": 35, "interval_days": 7},
    {"sku": "tomato 1kg", "name": "Tomato 1kg", "category": "produce", "price": 40, "interval_days": 5},
    {"sku": "potato 1kg", "name": "Potato 1kg", "category": "produce", "price": 30, "interval_days": 8},
    {"sku": "spinach bunch", "name": "Spinach Bunch", "category": "produce", "price": 20, "interval_days": 6},
    {"sku": "apples 4 pack", "name": "Apples (4 pack)", "category": "produce", "price": 120, "interval_days": 9},
    {"sku": "ginger garlic paste 200g", "name": "Ginger Garlic Paste 200g", "category": "produce", "price": 55, "interval_days": 14},
    {"sku": "sugar 1kg", "name": "Sugar 1kg", "category": "staples", "price": 48, "interval_days": 25},
    {"sku": "salt 1kg", "name": "Salt 1kg", "category": "staples", "price": 22, "interval_days": 35},
    {"sku": "sunflower oil 1l", "name": "Sunflower Oil 1L", "category": "staples", "price": 140, "interval_days": 20},
    {"sku": "tea powder 250g", "name": "Tea Powder 250g", "category": "staples", "price": 110, "interval_days": 18},
    {"sku": "coffee powder 200g", "name": "Coffee Powder 200g", "category": "staples", "price": 180, "interval_days": 22},
    {"sku": "biscuits pack", "name": "Biscuits Pack", "category": "snacks", "price": 30, "interval_days": 6},
    {"sku": "namkeen 200g", "name": "Namkeen 200g", "category": "snacks", "price": 55, "interval_days": 10},
    {"sku": "chips pack", "name": "Chips Pack", "category": "snacks", "price": 20, "interval_days": 8},
    {"sku": "dish wash liquid 500ml", "name": "Dish Wash Liquid 500ml", "category": "household", "price": 95, "interval_days": 20},
    {"sku": "detergent powder 1kg", "name": "Detergent Powder 1kg", "category": "household", "price": 130, "interval_days": 25},
    {"sku": "toilet paper pack", "name": "Toilet Paper Pack", "category": "household", "price": 110, "interval_days": 15},
]

# (sku_a, sku_b, reason) — SUBSTITUTE_FOR is bidirectional in practice, so
# seed_graph.py writes the edge both ways once per pair.
SUBSTITUTE_PAIRS = [
    ("toned milk 1l", "full cream milk 1l", "both plain milk, different fat content"),
    ("amul milk 500ml", "toned milk 1l", "same category, different pack size/brand"),
    ("brown bread", "white bread", "same bakery staple, different grain"),
    ("basmati rice 1kg", "sona masoori rice 5kg", "both rice staples"),
    ("toor dal 1kg", "moong dal 1kg", "common dal swap"),
    ("oats 1kg", "poha 500g", "common quick-breakfast swap"),
    ("tea powder 250g", "coffee powder 200g", "common morning-beverage swap"),
]


def by_sku(sku: str) -> dict | None:
    return next((p for p in PRODUCTS if p["sku"] == sku), None)
