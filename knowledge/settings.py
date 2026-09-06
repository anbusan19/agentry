"""
knowledge/settings.py

Small local settings store (data/settings.json, gitignored) backing the
web console's Settings page — currently just the weekly budget cap, which
tools/check_budget.py reads from here instead of a fixed env var, so
changing it in the UI takes effect immediately without a restart.

WEEKLY_BUDGET_INR (if set) seeds the default the first time this file is
read; after that, whatever's saved here wins.
"""

import json
import os
from pathlib import Path

SETTINGS_FILE = Path(__file__).parent.parent / "data" / "settings.json"


def _defaults() -> dict:
    return {
        "weekly_budget_inr": float(os.environ.get("WEEKLY_BUDGET_INR", 1500.0)),
    }


def get_settings() -> dict:
    if not SETTINGS_FILE.exists():
        return _defaults()
    with open(SETTINGS_FILE) as f:
        saved = json.load(f)
    return {**_defaults(), **saved}


def update_settings(patch: dict) -> dict:
    current = get_settings()
    current.update(patch)
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(current, f, indent=2)
    return current
