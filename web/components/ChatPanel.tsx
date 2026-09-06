"use client";

import { useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Message {
  role: "user" | "agent" | "error";
  content: string;
  at: number;
}

function timeLabel(at: number) {
  return new Date(at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

/**
 * A chat window talking to server.py's /api/chat, which wraps one live
 * Strands Agent instance kept alive across turns — so a real conversation
 * here can search, add to cart, and checkout exactly like a CLI run, with
 * cart state carried turn to turn.
 */
export default function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "agent",
      content:
        "I'm Agentry. Give me a goal, something like \"restock the pantry\" or \"what's in my cart,\" and I'll take it from there.",
      at: Date.now(),
    },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  function scrollToEnd() {
    requestAnimationFrame(() => {
      listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
    });
  }

  async function send() {
    const text = input.trim();
    if (!text || sending) return;

    setMessages((m) => [...m, { role: "user", content: text, at: Date.now() }]);
    setInput("");
    setSending(true);
    scrollToEnd();

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const data = await res.json();
      setMessages((m) => [...m, { role: "agent", content: data.reply, at: Date.now() }]);
    } catch (err) {
      setMessages((m) => [
        ...m,
        {
          role: "error",
          content:
            (err instanceof Error ? err.message : "Something went wrong") +
            ". Is `uvicorn server:app --port 8000` running?",
          at: Date.now(),
        },
      ]);
    } finally {
      setSending(false);
      scrollToEnd();
    }
  }

  return (
    <div className="chat">
      <div className="chat__head">
        <div className="chat__head-id">
          <span className="chat__mark" aria-hidden="true" />
          <span className="chat__title">Agentry</span>
        </div>
        <span className={`chat__status ${sending ? "chat__status--busy" : ""}`}>
          {sending ? "working" : "idle"}
        </span>
      </div>

      <div className="chat__list" ref={listRef}>
        {messages.map((m, i) => (
          <div key={i} className={`chat__row chat__row--${m.role}`}>
            <span className="chat__who">{m.role === "user" ? "You" : m.role === "error" ? "Console" : "Agentry"}</span>
            <div className={`chat__bubble chat__bubble--${m.role}`}>
              {m.role === "agent" ? (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
              ) : (
                <p>{m.content}</p>
              )}
            </div>
            <span className="chat__time">{timeLabel(m.at)}</span>
          </div>
        ))}

        {sending && (
          <div className="chat__row chat__row--agent">
            <span className="chat__who">Agentry</span>
            <div className="chat__bubble chat__bubble--thinking">
              <span className="chat__orb" aria-hidden="true" />
              <span className="chat__thinking-label">thinking</span>
            </div>
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
