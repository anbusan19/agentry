"use client";

import { useRef, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Message {
  role: "user" | "agent" | "error";
  content: string;
}

/**
 * A plain chat window talking to server.py's /api/chat, which wraps one
 * live Strands Agent instance kept alive across turns — so a real
 * conversation here can search, add to cart, and checkout exactly like a
 * CLI run, with cart state carried turn to turn.
 */
export default function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "agent",
      content:
        "I'm Agentry. Give me a goal — \"restock the pantry\", \"what's in my cart\", \"how much Zepto Cash do I have\" — and I'll take it from there.",
    },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  async function send() {
    const text = input.trim();
    if (!text || sending) return;

    setMessages((m) => [...m, { role: "user", content: text }]);
    setInput("");
    setSending(true);

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const data = await res.json();
      setMessages((m) => [...m, { role: "agent", content: data.reply }]);
    } catch (err) {
      setMessages((m) => [
        ...m,
        {
          role: "error",
          content:
            (err instanceof Error ? err.message : "Something went wrong") +
            " — is `uvicorn server:app --port 8000` running?",
        },
      ]);
    } finally {
      setSending(false);
      requestAnimationFrame(() => {
        listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
      });
    }
  }

  return (
    <div className="chat">
      <div className="chat__head">
        <span className="chat__title">Agentry</span>
        <span className={`chat__status ${sending ? "chat__status--busy" : ""}`}>
          {sending ? "thinking…" : "idle"}
        </span>
      </div>

      <div className="chat__list" ref={listRef}>
        {messages.map((m, i) => (
          <div key={i} className={`chat__bubble chat__bubble--${m.role}`}>
            {m.content}
          </div>
        ))}
        {sending && (
          <div className="chat__bubble chat__bubble--agent chat__bubble--pending">
            <span className="chat__dot" />
            <span className="chat__dot" />
            <span className="chat__dot" />
          </div>
        )}
      </div>

      <form
        className="chat__form"
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
      >
        <input
          className="chat__input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="restock the pantry"
          disabled={sending}
        />
        <button className="chat__send" type="submit" disabled={sending || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}
