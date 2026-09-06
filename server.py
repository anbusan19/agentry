"""
server.py

A thin FastAPI bridge between the Strands Agent (Python) and the Next.js
frontend (web/) — not part of the hackathon's core CLI path (that's still
`python main.py --goal "..."`), but needed for the chat console at
web/app/console to talk to a live agent instead of shelling out per
message.

One Agent instance is built lazily on first request and kept alive for the
life of the process: Strands' own Agent already accumulates conversation
history across calls, and tools/_session.py's persistent browser page
survives exactly the same way — so a real chat conversation keeps its cart
state turn to turn, the same as a CLI run would within one process.

Run: uvicorn server:app --reload --port 8000
"""

import base64
import json
import os
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent.agent import build_agent
from knowledge.budget import spent_within
from knowledge.graph import load_graph, restock_suggestions
from knowledge.settings import get_settings, update_settings
from tools._session import platform_status

load_dotenv()

app = FastAPI(title="Agentry")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_agent = None

# Gemini models the current key can call generateContent on. Cached for the
# process — models.list() is cheap and on a different quota than
# generateContent, but there's no reason to re-fetch it every settings poll.
_gemini_models_cache: Optional[list[str]] = None

# Used when GEMINI_API_KEY is unset or models.list() fails (offline, quota,
# SDK shape change) — a small hand-picked set so the composer selector is
# never empty. The live list replaces this whenever the call succeeds.
FALLBACK_GEMINI_MODELS = [
    "gemini-3.6-flash",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]

# models.list() also returns image / tts / transcribe / robotics / computer-use
# variants that share the generateContent action but aren't text chat models —
# drop anything whose id carries one of these markers.
_NON_CHAT_MARKERS = (
    "image",
    "tts",
    "transcribe",
    "robotics",
    "computer-use",
    "customtools",
    "embedding",
    "aqa",
)


def _gemini_models() -> list[str]:
    """Every Gemini model the configured key can use for chat, newest first.
    Falls back to FALLBACK_GEMINI_MODELS on any failure so the UI selector
    always has something to show."""
    global _gemini_models_cache
    if _gemini_models_cache is not None:
        return _gemini_models_cache

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        _gemini_models_cache = FALLBACK_GEMINI_MODELS
        return _gemini_models_cache

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        names: list[str] = []
        for m in client.models.list():
            actions = (
                getattr(m, "supported_actions", None)
                or getattr(m, "supported_generation_methods", None)
                or []
            )
            if "generateContent" not in actions:
                continue
            name = (getattr(m, "name", "") or "").removeprefix("models/")
            if not name.startswith("gemini-") or "tuning" in name:
                continue
            if any(marker in name for marker in _NON_CHAT_MARKERS):
                continue
            names.append(name)
        _gemini_models_cache = sorted(set(names), reverse=True) or FALLBACK_GEMINI_MODELS
    except Exception:
        _gemini_models_cache = FALLBACK_GEMINI_MODELS

    return _gemini_models_cache


def _get_agent():
    global _agent
    if _agent is None:
        _agent = build_agent()
    return _agent


class ChatMessage(BaseModel):
    message: str


class ProductBatch(BaseModel):
    query: str
    results: list[dict]


class Cart(BaseModel):
    items: list[dict]
    total: Optional[str] = None


class CheckoutInfo(BaseModel):
    status: str
    amount_paid: Optional[float] = None
    order_id: Optional[str] = None
    note: Optional[str] = None
    error: Optional[str] = None


class ChatReply(BaseModel):
    reply: str
    products: list[ProductBatch] = []
    # Cart contents / checkout outcome for this turn, when the agent called
    # view_cart or checkout — the console renders them as an order-summary
    # card (in chat, and on the voice stage) instead of leaving the numbers
    # buried in prose.
    cart: Optional[Cart] = None
    checkout: Optional[CheckoutInfo] = None


def _extract_search_batches(messages: list[dict[str, Any]]) -> list[dict]:
    """Pull out every search_products call's results from this turn's new
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


def _last_tool_result(messages: list[dict[str, Any]], tool_name: str) -> Optional[dict]:
    """The most recent parsed toolResult for `tool_name` in this turn's new
    messages, or None. Same {toolUse}/{toolResult} pairing as
    _extract_search_batches, but we only care about the last call's payload
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


def _extract_cart(messages: list[dict[str, Any]]) -> Optional[dict]:
    data = _last_tool_result(messages, "view_cart")
    if data and data.get("status") == "ok" and data.get("items"):
        return {"items": data["items"], "total": data.get("total")}
    return None


def _extract_checkout(messages: list[dict[str, Any]]) -> Optional[dict]:
    data = _last_tool_result(messages, "checkout")
    if not data or not data.get("status"):
        return None
    keep = ("status", "amount_paid", "order_id", "note", "error")
    return {k: data[k] for k in keep if data.get(k) is not None}


@app.post("/api/chat", response_model=ChatReply)
async def chat(body: ChatMessage) -> ChatReply:
    agent = _get_agent()
    before = len(agent.messages)
    result = await run_in_threadpool(agent, body.message)
    new_messages = agent.messages[before:]
    return ChatReply(
        reply=str(result),
        products=_extract_search_batches(new_messages),
        cart=_extract_cart(new_messages),
        checkout=_extract_checkout(new_messages),
    )


class VoiceReply(BaseModel):
    transcript: str
    reply: str
    products: list[ProductBatch] = []
    cart: Optional[Cart] = None
    checkout: Optional[CheckoutInfo] = None
    # base64 speech audio + its mime type; null if TTS was unavailable (the
    # text reply still stands, the console just won't speak it).
    audio_b64: Optional[str] = None
    audio_mime: Optional[str] = None


@app.post("/api/voice", response_model=VoiceReply)
async def voice(clip: UploadFile = File(...)) -> VoiceReply:
    """One recorded mic clip -> local Whisper -> the same shared agent the
    text console uses (so cart state carries) -> local TTS. Non-streaming by
    design for now; the structured cart/checkout/products come back too so
    the console's voice stage can render them."""
    from voice.stt import transcribe
    from voice.style import frame_transcript
    from voice.tts import synthesize

    raw = await clip.read()
    transcript = (await run_in_threadpool(transcribe, raw, clip.content_type)).strip()
    if not transcript:
        return VoiceReply(transcript="", reply="Sorry, I didn't catch that. Say that again?")

    agent = _get_agent()
    before = len(agent.messages)
    result = await run_in_threadpool(agent, frame_transcript(transcript))
    new_messages = agent.messages[before:]
    reply_text = str(result)

    audio_b64 = audio_mime = None
    try:
        audio_bytes, audio_mime = await run_in_threadpool(synthesize, reply_text)
        audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
    except Exception as exc:  # TTS is best-effort — never fail the turn over it
        print(f"[voice] TTS unavailable: {exc}")

    return VoiceReply(
        transcript=transcript,
        reply=reply_text,
        products=_extract_search_batches(new_messages),
        cart=_extract_cart(new_messages),
        checkout=_extract_checkout(new_messages),
        audio_b64=audio_b64,
        audio_mime=audio_mime,
    )


@app.get("/api/voice/health")
async def voice_health():
    """Whether the local voice loop can run, for the console to show a
    'voice not ready' hint instead of a silent failure."""
    from voice.stt import is_ready as stt_ready
    from voice.tts import active_engine

    tts = active_engine()
    return {
        "stt_ready": stt_ready(),
        "stt_model": os.environ.get("VOICE_STT_MODEL", "base"),
        "tts_engine": tts,
        "ready": stt_ready() and tts != "none",
    }


@app.get("/api/graph")
async def graph():
    """The purchase-history knowledge graph, shaped for a force-directed
    viz: nodes carry restock status, edges carry co-purchase weight."""
    g = load_graph()
    due_by_item = {d["item"]: d for d in restock_suggestions()["due"]}

    nodes = [
        {
            "id": item,
            "purchase_count": len(attrs.get("purchases", [])),
            "last_purchased": max(attrs["purchases"]) if attrs.get("purchases") else None,
            "overdue": due_by_item.get(item, {}).get("overdue", False),
            "due_soon": item in due_by_item,
        }
        for item, attrs in g.nodes(data=True)
    ]
    links = [
        {"source": a, "target": b, "weight": attrs.get("co_purchase", 1)}
        for a, b, attrs in g.edges(data=True)
    ]
    return {"nodes": nodes, "links": links}


class SettingsPatch(BaseModel):
    weekly_budget_inr: Optional[float] = None
    model_provider: Optional[str] = None
    gemini_model: Optional[str] = None


def _settings_payload() -> dict:
    settings = get_settings()
    g = load_graph()
    return {
        "weekly_budget_inr": settings["weekly_budget_inr"],
        "spent_this_week": round(spent_within(7), 2),
        "model_provider": settings["model_provider"],
        "gemini_model": settings.get("gemini_model", "gemini-3.6-flash"),
        "gemini_models": _gemini_models(),
        "gemini_configured": bool(os.environ.get("GEMINI_API_KEY")),
        "bedrock_configured": bool(os.environ.get("AWS_ACCESS_KEY_ID")),
        "telegram_configured": bool(
            os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID")
        ),
        "platforms": platform_status(),
        "graph_stats": {"items": g.number_of_nodes(), "co_purchase_links": g.number_of_edges()},
    }


@app.get("/api/settings")
async def settings():
    return _settings_payload()


@app.post("/api/settings")
async def update_settings_endpoint(patch: SettingsPatch):
    global _agent
    changes = {k: v for k, v in patch.model_dump().items() if v is not None}
    current = get_settings()
    provider_changed = (
        "model_provider" in changes and changes["model_provider"] != current["model_provider"]
    )
    model_changed = (
        "gemini_model" in changes and changes["gemini_model"] != current.get("gemini_model")
    )
    if provider_changed or model_changed:
        # The cached Agent was built with the old model — drop it so the
        # next chat request rebuilds one with whatever's now selected,
        # instead of the change silently doing nothing until a restart.
        _agent = None
    update_settings(changes)
    return _settings_payload()


@app.get("/api/health")
async def health():
    return {"status": "ok"}
