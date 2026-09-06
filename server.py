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

import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI
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


def _get_agent():
    global _agent
    if _agent is None:
        _agent = build_agent()
    return _agent


class ChatMessage(BaseModel):
    message: str


class ChatReply(BaseModel):
    reply: str


@app.post("/api/chat", response_model=ChatReply)
async def chat(body: ChatMessage) -> ChatReply:
    agent = _get_agent()
    result = await run_in_threadpool(agent, body.message)
    return ChatReply(reply=str(result))


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


def _settings_payload() -> dict:
    settings = get_settings()
    g = load_graph()
    return {
        "weekly_budget_inr": settings["weekly_budget_inr"],
        "spent_this_week": round(spent_within(7), 2),
        "gemini_configured": bool(os.environ.get("GEMINI_API_KEY")),
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
    update_settings({k: v for k, v in patch.model_dump().items() if v is not None})
    return _settings_payload()


@app.get("/api/health")
async def health():
    return {"status": "ok"}
