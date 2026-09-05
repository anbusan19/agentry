"""
main.py

Entry point for Agentry.

Usage:
    python main.py --goal "restock the pantry"
"""

import argparse

from dotenv import load_dotenv

from agent.agent import build_agent
from agent.prompts import PLANNING_PROMPT_TEMPLATE


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Agentry — autonomous grocery-ordering agent")
    parser.add_argument(
        "--goal",
        required=True,
        help='The shopping goal, e.g. "restock the pantry" or "order milk and eggs".',
    )
    args = parser.parse_args()

    agent = build_agent()
    prompt = PLANNING_PROMPT_TEMPLATE.format(goal=args.goal)

    agent(prompt)


if __name__ == "__main__":
    main()
