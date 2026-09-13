"""
knowledge/settings.py

Small local settings store (data/settings.json, gitignored) backing the
web console's Settings page: the weekly budget cap (tools/check_budget.py
reads it from here instead of a fixed env var) and the model provider
(agent/agent.py reads it here instead of MODEL_PROVIDER directly), so
changing either in the UI takes effect immediately without a restart.

WEEKLY_BUDGET_INR / MODEL_PROVIDER (if set) seed the defaults the first
time this file is read; after that, whatever's saved here wins.
"""

import json
import os
from pathlib import Path

SETTINGS_FILE = Path(__file__).parent.parent / "data" / "settings.json"


def _defaults() -> dict:
    return {
        "weekly_budget_inr": float(os.environ.get("WEEKLY_BUDGET_INR", 1500.0)),
        "model_provider": os.environ.get("MODEL_PROVIDER", "gemini").lower(),
        # Which Gemini model the agent talks to. Selectable from the console
        # composer (server.py lists what the key can reach) so a per-model
        # rate limit can be side-stepped by switching, no restart needed.
        "gemini_model": os.environ.get("GEMINI_MODEL", "gemini-3.6-flash"),
        # Which Bedrock Mantle model the agent talks to (MODEL_PROVIDER=
        # bedrock-mantle). Also selectable from the console composer.
        "mantle_model": os.environ.get("MANTLE_MODEL_ID", "openai.gpt-oss-120b"),
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
