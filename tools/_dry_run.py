"""
tools/_dry_run.py

Mock storefront for AGENTRY_DRY_RUN=1 — lets the full agent loop
(search_products -> add_to_cart -> view_cart -> checkout -> record_purchase)
run end to end against the synthetic catalog in knowledge/catalog.py, with
no Playwright browser and no real Zepto/Blinkit login. Built for the Graph
Hacks demo so the agent is runnable without a live storefront session;
every item/price here is the same synthetic catalog the FalkorDB seed
script uses, never real order data.

Not a tool itself — each storefront tool (search_products.py,
add_to_cart.py, view_cart.py, remove_from_cart.py, check_wallet_balance.py,
checkout.py) checks is_dry_run() first and calls the matching function here
instead of touching Playwright at all.

Cart state is process-level (module globals), same lifetime as the real
Playwright session's cart — survives across tool calls within one agent
run, resets on process restart.
"""

import os
import time
from typing import Optional

from knowledge.catalog import PRODUCTS, by_sku


def is_dry_run() -> bool:
    return os.environ.get("AGENTRY_DRY_RUN") == "1"


_carts: dict[str, dict[str, dict]] = {}


def _cart(platform: str) -> dict:
    return _carts.setdefault(platform, {})


def search(query: str, limit: int) -> dict:
    needle = query.strip().lower()
    matches = [p for p in PRODUCTS if needle in p["name"].lower() or needle in p["sku"]]
    if not matches:
        return {"status": "not_found", "results": [], "error": f'No products found for "{query}"'}
    results = [
        {"name": p["name"], "price": f"₹{p['price']}", "url": f"/mock/{p['sku']}", "image": ""}
        for p in matches[:limit]
    ]
    return {"status": "ok", "results": results}


def _resolve(product_url: str, query: str) -> Optional[dict]:
    if product_url:
        return by_sku(product_url.removeprefix("/mock/"))
    needle = query.strip().lower()
    return next((p for p in PRODUCTS if needle in p["name"].lower() or needle in p["sku"]), None)


def add_to_cart(product_url: str, query: str, quantity: int, platform: str) -> dict:
    product = _resolve(product_url, query)
    if not product:
        return {"status": "not_found", "error": f'No products found for "{product_url or query}"'}
    cart = _cart(platform)
    entry = cart.setdefault(product["sku"], {"name": product["name"], "price": product["price"], "quantity": 0})
    was_already_in_cart = entry["quantity"] > 0
    entry["quantity"] += quantity
    return {
        "status": "ok",
        "name": product["name"],
        "price": f"₹{product['price']}",
        "added": quantity,
        "note": "Already in cart — added more units." if was_already_in_cart else None,
    }


def remove_from_cart(product_url: str, quantity: int, platform: str) -> dict:
    cart = _cart(platform)
    sku = product_url.removeprefix("/mock/")
    if sku not in cart:
        return {"status": "ok", "removed": 0, "cleared": True, "note": "Item was not in the cart."}
    entry = cart[sku]
    to_remove = quantity if quantity > 0 else entry["quantity"]
    entry["quantity"] = max(0, entry["quantity"] - to_remove)
    cleared = entry["quantity"] == 0
    name = entry["name"]
    if cleared:
        del cart[sku]
    return {"status": "ok", "name": name, "removed": to_remove, "cleared": cleared}


def view_cart(platform: str) -> dict:
    cart = _cart(platform)
    if not cart:
        return {"status": "ok", "items": [], "total": "₹0", "note": "Cart is empty."}
    items = [{"name": e["name"], "quantity": e["quantity"], "price": f"₹{e['price']}"} for e in cart.values()]
    total = sum(e["price"] * e["quantity"] for e in cart.values())
    return {"status": "ok", "items": items, "total": f"₹{total}"}


def check_wallet_balance() -> dict:
    return {"status": "ok", "wallet": "Agentry Dry-Run Wallet", "balance": 2000.0}


def checkout(platform: str) -> dict:
    cart = _cart(platform)
    if not cart:
        return {"status": "error", "error": "Cart is empty — nothing to check out."}
    total = sum(e["price"] * e["quantity"] for e in cart.values())
    items = [e["name"] for e in cart.values()]
    order_id = f"DRYRUN-{int(time.time())}"
    cart.clear()
    return {
        "status": "paid",
        "amount_paid": float(total),
        "order_id": order_id,
        "items": items,
        "note": "Simulated order (AGENTRY_DRY_RUN=1) — no real payment was made.",
    }
