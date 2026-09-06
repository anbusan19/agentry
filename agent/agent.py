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
from strands.models.bedrock import BedrockModel
from strands.models.gemini import GeminiModel

from agent.prompts import SYSTEM_PROMPT
from tools.add_to_cart import add_to_cart
from tools.check_budget import check_budget
from tools.check_wallet_balance import check_wallet_balance
from tools.checkout import checkout
from tools.get_restock_suggestions import get_restock_suggestions
from tools.notify import notify_user
from tools.query_purchase_history import query_purchase_history
from tools.record_purchase import record_purchase
from tools.remove_from_cart import remove_from_cart
from tools.search_products import search_products
from tools.view_cart import view_cart

DEFAULT_BEDROCK_MODEL_ID = "anthropic.claude-3-5-sonnet-20241022-v2:0"


def _build_model():
    """Pick the model provider from MODEL_PROVIDER (default "gemini").
    "bedrock" uses AWS credentials via boto3's normal resolution chain
    (env vars, a named profile, or an IAM role) — nothing AWS-specific is
    read directly here, boto3 handles that on its own once BedrockModel
    calls it."""
    provider = os.environ.get("MODEL_PROVIDER", "gemini").lower()

    if provider == "bedrock":
        return BedrockModel(
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
            model_id=os.environ.get("BEDROCK_MODEL_ID", DEFAULT_BEDROCK_MODEL_ID),
        )

    if provider != "gemini":
        raise RuntimeError(f'Unknown MODEL_PROVIDER {provider!r} — use "gemini" or "bedrock".')

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set — copy .env.example to .env and fill it in."
        )
    return GeminiModel(
        client_args={"api_key": api_key},
        # gemini-2.0-flash was deprecated (confirmed live, mid-build) — the
        # API's own 404 pointed at this as the replacement.
        model_id="gemini-3.6-flash",
    )


def build_agent() -> Agent:
    """Construct the Agentry Strands Agent: model provider + tools."""
    return Agent(
        model=_build_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[
            get_restock_suggestions,
            query_purchase_history,
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
