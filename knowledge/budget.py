"""
knowledge/budget.py

A small local spend tracker — not a port, and deliberately not the old
prototype's on-chain spend-cap contract. Just a JSON log of what's been
spent (data/spend_log.json, gitignored) and a rolling-window sum against a
configurable limit, so checkout can be gated by a real spend cap without
any blockchain/wallet infra.

checkout.py calls record_spend itself after a successful payment, so the
ledger reflects reality regardless of whether the agent remembers to log
anything — tools/check_budget.py just reads it back.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

SPEND_FILE = Path(__file__).parent.parent / "data" / "spend_log.json"


def _load() -> list[dict]:
    if not SPEND_FILE.exists():
        return []
    with open(SPEND_FILE) as f:
        return json.load(f)


def _save(entries: list[dict]) -> None:
    SPEND_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SPEND_FILE, "w") as f:
        json.dump(entries, f, indent=2)


def record_spend(amount: float, when: Optional[datetime] = None) -> None:
    when = when or datetime.now(timezone.utc)
    entries = _load()
    entries.append({"amount": amount, "at": when.isoformat()})
    _save(entries)


def spent_within(days: float, now: Optional[datetime] = None) -> float:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    return sum(
        e["amount"] for e in _load() if datetime.fromisoformat(e["at"]) >= cutoff
    )


def check_budget(amount: float, limit: float, days: float = 7.0) -> dict:
    """Would spending `amount` now push the trailing `days`-day total over
    `limit`? Returns the numbers behind the answer, not just a bool."""
    spent = spent_within(days)
    remaining = limit - spent
    return {
        "approved": amount <= remaining,
        "amount": amount,
        "spent_so_far": round(spent, 2),
        "remaining": round(remaining, 2),
        "limit": limit,
        "window_days": days,
    }
