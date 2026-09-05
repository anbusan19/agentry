"""
agent/agent.py

Strands Agent definition and model configuration for Agentry.

This is the from-scratch Strands port for this hackathon — unlike
tools/browser.py and tools/notify.py, there is no equivalent to adapt here,
since the prototype this submission builds on hand-rolled its own
orchestration loop rather than using an agent framework. See README's
Disclosure section.
"""

import os

from strands import Agent
from strands.models.gemini import GeminiModel

from agent.prompts import SYSTEM_PROMPT
from tools.browser import browser_automation
from tools.notify import notify_user


def build_agent() -> Agent:
    """Construct the Agentry Strands Agent: Gemini model + tools."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set — copy .env.example to .env and fill it in."
        )

    model = GeminiModel(
        api_key=api_key,
        model_id="gemini-2.0-flash",
    )

    return Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[browser_automation, notify_user],
    )
