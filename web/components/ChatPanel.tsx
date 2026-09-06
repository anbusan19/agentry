"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import SettingsModal from "@/components/SettingsModal";
import ProductTiles, { type ProductBatch } from "@/components/ProductTiles";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Message {
  role: "user" | "agent" | "error";
  content: string;
  at: number;
  products?: ProductBatch[];
}

// Pinned locale + hour12: toLocaleTimeString's *default* locale/format can
// differ between the server's Node runtime and the browser (24-hour vs.
// 12-hour, say), which is a hydration mismatch waiting to happen for any
// timestamp rendered during the initial SSR pass. Pinning both makes the
// output deterministic across environments.
function timeLabel(at: number) {
  return new Date(at).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: true });
}

/**
 * A chat window talking to server.py's /api/chat, which wraps one live
 * Strands Agent instance kept alive across turns — so a real conversation
 * here can search, add to cart, and checkout exactly like a CLI run, with
 * cart state carried turn to turn.
 */
export default function ChatPanel() {
  // `at: 0` here, not Date.now() — a timestamp baked into the initial
  // render would embed whatever instant the server happened to render at
  // into the SSR-ed HTML, which the client's own hydration pass has no way
  // to reproduce exactly. Filled in for real once mounted, below.
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "agent",
      content:
        "I'm Agentry. Give me a goal, something like \"restock the pantry\" or \"what's in my cart,\" and I'll take it from there.",
      at: 0,
    },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [addingUrl, setAddingUrl] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMessages((m) => (m.length === 1 && m[0].at === 0 ? [{ ...m[0], at: Date.now() }] : m));
  }, []);

  function scrollToEnd() {
    requestAnimationFrame(() => {
      listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
    });
  }

  /**
   * Sends `text` to the agent. `displayText`, if given, is what shows up
   * in the user's own chat bubble instead — used by the product tiles'
   * Add button, which sends a message precise enough for the model to call
   * add_to_cart with the exact product_url, but shows the user a plain
   * "Add X to my cart" rather than that raw detail.
   */
  async function send(text: string, displayText?: string) {
    if (!text || sending) return;

    setMessages((m) => [...m, { role: "user", content: displayText ?? text, at: Date.now() }]);
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
      setMessages((m) => [
        ...m,
        { role: "agent", content: data.reply, at: Date.now(), products: data.products },
      ]);
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
      setAddingUrl(null);
      scrollToEnd();
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text) return;
    setInput("");
    send(text);
  }

  function handleAddTile(item: { name: string; price: string; url: string }) {
    setAddingUrl(item.url);
    send(
      `Add "${item.name}" to my cart. product_url: ${item.url}`,
      `Add ${item.name} to my cart`
    );
  }

  return (
    <div className="chat">
      <div className="chat__head">
        <div className="chat__head-id">
          <span className="chat__mark" aria-hidden="true" />
          <span className="chat__title">Agentry</span>
        </div>
        <div className="chat__head-actions">
          <span className={`chat__status ${sending ? "chat__status--busy" : ""}`}>
            {sending ? "working" : "idle"}
          </span>
          <button
            className="chat__settings-btn"
            onClick={() => setSettingsOpen(true)}
            aria-label="Open settings"
            title="Settings"
          >
            <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden="true">
              <circle cx="7.5" cy="7.5" r="2.2" stroke="currentColor" strokeWidth="1.2" />
              <path
                d="M7.5 1.5v1.4M7.5 12.1v1.4M13.5 7.5h-1.4M2.9 7.5H1.5M11.5 3.5l-1 1M4.5 10.5l-1 1M11.5 11.5l-1-1M4.5 4.5l-1-1"
                stroke="currentColor"
                strokeWidth="1.2"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </div>
      </div>

      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />

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
            {m.products && m.products.length > 0 && (
              <ProductTiles batches={m.products} onAdd={handleAddTile} addingUrl={addingUrl} />
            )}
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

      <form className="chat__form" onSubmit={handleSubmit}>
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
