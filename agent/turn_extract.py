"""
agent/turn_extract.py

Pulls structured data (search results, cart contents, checkout outcome) out
of a slice of raw Strands agent messages — the {toolUse}/{toolResult}
content-block pairing every Strands model provider produces.

Moved out of server.py (which originally had these inline for the REST
/api/chat and /api/voice paths) so voice/bidi_voice.py's real-time Nova
Sonic path can reuse the exact same extraction logic against
BidiAgent.messages — the same accumulate-a-message-history shape as the
regular text Agent — without server.py and voice/bidi_voice.py importing
from each other (voice/bidi_voice.py is itself imported by server.py, so
the reverse import would be circular).
"""

import json
from typing import Any, Optional


def extract_search_batches(messages: list[dict[str, Any]]) -> list[dict]:
    """Pull out every search_products call's results from this slice of
    messages, so the console can render them as tiles instead of the model
    having to retype a product list as prose. Strands records each tool
    call as a {toolUse} block (name + input) and its outcome as a matching
    {toolResult} block (linked by toolUseId) in the following message."""
    tool_calls: dict[str, dict] = {}
    batches = []

    for msg in messages:
        for block in msg.get("content", []):
            if "toolUse" in block:
                tu = block["toolUse"]
                tool_calls[tu["toolUseId"]] = tu
            elif "toolResult" in block:
                tr = block["toolResult"]
                call = tool_calls.get(tr.get("toolUseId"))
                if not call or call.get("name") != "search_products" or tr.get("status") != "success":
                    continue
                for c in tr.get("content", []):
                    text = c.get("text")
                    if not text:
                        continue
                    try:
                        data = json.loads(text)
                    except (json.JSONDecodeError, TypeError):
                        continue
                    if data.get("status") == "ok" and data.get("results"):
                        batches.append(
                            {"query": call.get("input", {}).get("query", ""), "results": data["results"]}
                        )
    return batches


def last_tool_result(messages: list[dict[str, Any]], tool_name: str) -> Optional[dict]:
    """The most recent parsed toolResult for `tool_name` in this slice of
    messages, or None. Same {toolUse}/{toolResult} pairing as
    extract_search_batches, but we only care about the last call's payload
    (a turn that re-checks the cart should show the latest state)."""
    calls: dict[str, dict] = {}
    latest: Optional[dict] = None

    for msg in messages:
        for block in msg.get("content", []):
            if "toolUse" in block:
                tu = block["toolUse"]
                calls[tu["toolUseId"]] = tu
            elif "toolResult" in block:
                tr = block["toolResult"]
                call = calls.get(tr.get("toolUseId"))
                if not call or call.get("name") != tool_name:
                    continue
                for c in tr.get("content", []):
                    text = c.get("text")
                    if not text:
                        continue
                    try:
                        latest = json.loads(text)
                    except (json.JSONDecodeError, TypeError):
                        continue
    return latest


def extract_cart(messages: list[dict[str, Any]]) -> Optional[dict]:
    data = last_tool_result(messages, "view_cart")
    if data and data.get("status") == "ok" and data.get("items"):
        return {"items": data["items"], "total": data.get("total")}
    return None


def extract_checkout(messages: list[dict[str, Any]]) -> Optional[dict]:
    data = last_tool_result(messages, "checkout")
    if not data or not data.get("status"):
        return None
    keep = ("status", "amount_paid", "order_id", "note", "error")
    return {k: data[k] for k in keep if data.get(k) is not None}
