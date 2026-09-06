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

from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent.agent import build_agent
from knowledge.graph import load_graph, restock_suggestions

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


@app.get("/api/health")
async def health():
    return {"status": "ok"}
