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
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.models.gemini import GeminiModel

from agent.prompts import SYSTEM_PROMPT
from knowledge.settings import get_settings
from tools.add_to_cart import add_to_cart
from tools.check_budget import check_budget
from tools.check_wallet_balance import check_wallet_balance
from tools.checkout import checkout
from tools.get_restock_suggestions import get_restock_suggestions
from tools.manage_address import manage_address
from tools.notify import notify_user
from tools.query_purchase_history import query_purchase_history
from tools.record_purchase import record_purchase
from tools.remove_from_cart import remove_from_cart
from tools.search_products import search_products
from tools.view_cart import view_cart

# server.py keeps one Agent alive for the whole console session, and every
# call resends the full message history to the model — with no cap, a long
# chat's token cost per turn grows without bound (worse here than most
# agents, since search_products results carry names/prices/urls/images that
# stick around in history). A sliding window keeps only the most recent
# CONVERSATION_WINDOW_SIZE messages, truncating older tool results (first/
# last 200 chars, images swapped for placeholders) instead of dropping them
# outright — no extra model calls, unlike a summarizing manager.
DEFAULT_CONVERSATION_WINDOW_SIZE = 30


def _build_model():
    """Pick the model provider from settings (the Settings page's toggle,
    seeded from MODEL_PROVIDER — default "gemini"). "bedrock-mantle" uses AWS
    credentials via boto3's normal resolution chain (env vars, a named
    profile, or an IAM role) — nothing AWS-specific is read directly here."""
    provider = get_settings()["model_provider"]

    if provider == "bedrock-mantle":
        # Bedrock's OpenAI-compatible Mantle endpoint, via Strands'
        # OpenAIModel — reaches Bedrock models not on the native Converse
        # API (open-weight lines like openai.gpt-oss-*). No API key to
        # manage: bedrock_mantle_config mints a fresh, short-lived bearer
        # token per request straight off the standard boto3 credential
        # chain, so nothing sits around to expire the way a manually pasted
        # token would. Needs real IAM credentials (AWS_ACCESS_KEY_ID/
        # AWS_SECRET_ACCESS_KEY, a profile, or a role) to sign those tokens.
        # Model id comes from settings (the console composer's selector,
        # seeded from MANTLE_MODEL_ID, default openai.gpt-oss-120b).
        from strands.models.openai import OpenAIModel

        model_id = get_settings().get("mantle_model") or "openai.gpt-oss-120b"
        return OpenAIModel(
            bedrock_mantle_config={"region": os.environ.get("AWS_REGION", "us-east-1")},
            model_id=model_id,
        )

    if provider != "gemini":
        raise RuntimeError(f'Unknown MODEL_PROVIDER {provider!r} — use "gemini" or "bedrock-mantle".')

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set — copy .env.example to .env and fill it in."
        )
    # Model id comes from settings (the console composer's selector, seeded
    # from GEMINI_MODEL, default gemini-3.6-flash). gemini-2.0-flash was
    # deprecated mid-build — the API's own 404 pointed at 3.6 as the
    # replacement — but the free tier caps requests per-model per-day, so
    # being able to switch without a restart matters.
    model_id = get_settings().get("gemini_model") or "gemini-3.6-flash"
    return GeminiModel(
        client_args={"api_key": api_key},
        model_id=model_id,
    )


def build_agent() -> Agent:
    """Construct the Agentry Strands Agent: model provider + tools."""
    window_size = int(os.environ.get("CONVERSATION_WINDOW_SIZE", DEFAULT_CONVERSATION_WINDOW_SIZE))

    return Agent(
        model=_build_model(),
        system_prompt=SYSTEM_PROMPT,
        conversation_manager=SlidingWindowConversationManager(window_size=window_size),
        tools=[
            get_restock_suggestions,
            query_purchase_history,
            search_products,
            add_to_cart,
            remove_from_cart,
            view_cart,
            manage_address,
            check_budget,
            check_wallet_balance,
            checkout,
            record_purchase,
            notify_user,
        ],
    )
