"""
tools/check_budget.py

Checks a prospective spend against a configurable weekly budget cap, using
the local spend log (knowledge/budget.py). checkout.py logs every actual
payment there itself, so this reflects real spending regardless of whether
the agent remembers to record anything.
"""

import os

from strands import tool

from knowledge.budget import check_budget as _check_budget

DEFAULT_LIMIT_INR = 1500.0


@tool
def check_budget(amount: float) -> dict:
    """
    Check whether spending `amount` now would exceed the household's
    weekly grocery budget, based on what's actually been spent (via past
    checkout calls) in the trailing 7 days. Call this before checkout,
    especially for a cart total the user didn't explicitly pre-approve.

    The limit is read from the WEEKLY_BUDGET_INR environment variable
    (defaults to 1500 if unset).

    Args:
        amount: The amount that would be spent, e.g. a cart's total.

    Returns:
        A dict with "approved" (bool), "amount", "spent_so_far",
        "remaining", and "limit" — enough to explain the decision to the
        user if it's not approved.
    """
    limit = float(os.environ.get("WEEKLY_BUDGET_INR", DEFAULT_LIMIT_INR))
    return _check_budget(amount, limit)
