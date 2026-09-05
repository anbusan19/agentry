"""
agent/agent.py

Strands Agent definition and model configuration for Agentry.

This is the from-scratch Strands port for this hackathon — unlike most of
tools/, there is no equivalent to adapt here, since the prototype this
submission builds on hand-rolled its own orchestration loop rather than
using an agent framework. See README's Disclosure section.
"""

import os

from strands import Agent
from strands.models.gemini import GeminiModel

from agent.prompts import SYSTEM_PROMPT
from tools.add_to_cart import add_to_cart
from tools.check_budget import check_budget
from tools.check_wallet_balance import check_wallet_balance
from tools.checkout import checkout
from tools.get_restock_suggestions import get_restock_suggestions
from tools.notify import notify_user
from tools.record_purchase import record_purchase
from tools.remove_from_cart import remove_from_cart
from tools.search_products import search_products
from tools.view_cart import view_cart


def build_agent() -> Agent:
    """Construct the Agentry Strands Agent: Gemini model + tools."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set — copy .env.example to .env and fill it in."
        )

    model = GeminiModel(
        client_args={"api_key": api_key},
        model_id="gemini-2.0-flash",
    )

    return Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[
            get_restock_suggestions,
            search_products,
            add_to_cart,
            remove_from_cart,
            view_cart,
            check_budget,
            check_wallet_balance,
            checkout,
            record_purchase,
            notify_user,
        ],
    )
