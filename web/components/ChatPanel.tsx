"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import SettingsModal from "@/components/SettingsModal";
import ProductTiles, { type ProductBatch } from "@/components/ProductTiles";
import PaymentCard, { type Cart, type CheckoutInfo } from "@/components/PaymentCard";
import VoiceMode, { type VoiceExchange } from "@/components/VoiceMode";
import VoiceStage from "@/components/VoiceStage";
import LightRays from "@/components/LightRays";
import { DotmCircular20 } from "@/components/ui/dotm-circular-20";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Message {
  role: "user" | "agent" | "error";
  content: string;
  at: number;
  products?: ProductBatch[];
  cart?: Cart | null;
  checkout?: CheckoutInfo | null;
}

interface ChatConfig {
  model_provider: "gemini" | "bedrock-mantle" | "groq";
  gemini_model: string;
  gemini_models: string[];
  mantle_model: string;
  mantle_models: string[];
  groq_model: string;
  groq_models: string[];
}

// Pinned locale + hour12: toLocaleTimeString's *default* locale/format can
// differ between the server's Node runtime and the browser (24-hour vs.
// 12-hour, say), which is a hydration mismatch waiting to happen for any
// timestamp rendered during the initial SSR pass. Pinning both makes the
// output deterministic across environments.
function timeLabel(at: number) {
  return new Date(at).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: true });
}

// Optional, build-time. Shown after the time-of-day greeting when set.
const USER_NAME = process.env.NEXT_PUBLIC_USER_NAME?.trim();

/** A casual, time-of-day welcome for the empty chat — Claude-style. */
function greetingFor(hour: number, name?: string): string {
  if (hour < 5) return name ? `Midnight cravings, ${name}?` : "Midnight cravings?";
  if (hour < 12) return name ? `Good morning, ${name}` : "Good morning";
  if (hour < 17) return name ? `Good afternoon, ${name}` : "Good afternoon";
  if (hour < 22) return name ? `Good evening, ${name}` : "Good evening";
  return name ? `Late night, ${name}?` : "Late night restock?";
}

/**
 * A chat window talking to server.py's /api/chat, which wraps one live
 * Strands Agent instance kept alive across turns — so a real conversation
 * here can search, add to cart, and checkout exactly like a CLI run, with
 * cart state carried turn to turn.
 */
export default function ChatPanel({
  onVoiceChange,
}: {
  /** Told whenever voice mode opens/closes, so the console can swap the
   * right-hand pane (knowledge graph <-> voice stage). */
  onVoiceChange?: (on: boolean) => void;
}) {
  // Starts empty — before the first turn the panel shows a centred
  // "How can I help?" prompt instead of a greeting bubble; it disappears
  // the moment there's a real message.
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [voiceOpen, setVoiceOpen] = useState(false);
  const [addingUrl, setAddingUrl] = useState<string | null>(null);
  const [config, setConfig] = useState<ChatConfig | null>(null);
  const [modelSaving, setModelSaving] = useState(false);
  // "Keep shopping" on the order card hides it from the voice stage without
  // wiping it from the transcript; any new agent reply clears the flag.
  const [stagePaymentHidden, setStagePaymentHidden] = useState(false);
  const [stageHost, setStageHost] = useState<Element | null>(null);
  // Computed after mount so the server render and hydration agree.
  const [greeting, setGreeting] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setGreeting(greetingFor(new Date().getHours(), USER_NAME));
  }, []);

  useEffect(() => {
    setStageHost(document.querySelector(".console__pane--graph"));
  }, []);

  useEffect(() => {
    onVoiceChange?.(voiceOpen);
  }, [voiceOpen, onVoiceChange]);

  // The provider (gemini / bedrock) is set in Settings; the composer only
  // reads it, plus the per-provider model list, so a per-model rate limit
  // can be dodged by switching model right from the input row. Refetched
  // whenever Settings closes, since the provider may have changed there.
  const loadConfig = useCallback(() => {
    fetch(`${API_BASE}/api/settings`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!data) return;
        setConfig({
          model_provider: data.model_provider,
          gemini_model: data.gemini_model,
          gemini_models: data.gemini_models ?? [],
          mantle_model: data.mantle_model,
          mantle_models: data.mantle_models ?? [],
          groq_model: data.groq_model,
          groq_models: data.groq_models ?? [],
        });
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  async function changeModel(field: "gemini_model" | "mantle_model" | "groq_model", next: string) {
    setConfig((c) => (c ? { ...c, [field]: next } : c));
    setModelSaving(true);
    try {
      await fetch(`${API_BASE}/api/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ [field]: next }),
      });
    } catch {
      // best-effort; the next chat call will surface a real error if it stuck
    } finally {
      setModelSaving(false);
    }
  }

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
      setStagePaymentHidden(false);
      setMessages((m) => [
        ...m,
        {
          role: "agent",
          content: data.reply,
          at: Date.now(),
          products: data.products,
          cart: data.cart ?? null,
          checkout: data.checkout ?? null,
        },
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

  // A completed voice turn: /api/voice already ran the agent, so just fold
  // the transcript + reply into the same message list the text chat uses —
  // the voice stage reads the latest agent turn from here.
  function handleVoiceExchange(x: VoiceExchange) {
    setStagePaymentHidden(false);
    setMessages((m) => [
      ...m,
      ...(x.transcript
        ? [{ role: "user" as const, content: x.transcript, at: Date.now() }]
        : []),
      {
        role: "agent" as const,
        content: x.reply,
        at: Date.now(),
        products: x.products,
        cart: x.cart ?? null,
        checkout: x.checkout ?? null,
      },
    ]);
    scrollToEnd();
  }

  function handleConfirmPay() {
    send("Yes, go ahead and place the order now.", "Place the order");
  }

  function handleCancelPay() {
    setStagePaymentHidden(true);
    send("Not yet — hold off on checkout for now.", "Keep shopping");
  }

  // The most recent agent turn's visuals feed the voice stage.
  const lastAgent = [...messages].reverse().find((m) => m.role === "agent");
  const lastAgentIndex = messages.reduce((acc, m, i) => (m.role === "agent" ? i : acc), -1);
  const stageProducts = lastAgent?.products ?? [];
  const stageCart = stagePaymentHidden ? null : lastAgent?.cart ?? null;
  const stageCheckout = lastAgent?.checkout ?? null;

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

      <SettingsModal
        open={settingsOpen}
        onClose={() => {
          setSettingsOpen(false);
          loadConfig();
        }}
      />
      {voiceOpen && (
        <VoiceMode onClose={() => setVoiceOpen(false)} onExchange={handleVoiceExchange} />
      )}
      {voiceOpen &&
        stageHost &&
        createPortal(
          <VoiceStage
            products={stageProducts}
            cart={stageCart}
            checkout={stageCheckout}
            onAdd={handleAddTile}
            addingUrl={addingUrl}
            onConfirmPay={handleConfirmPay}
            onCancelPay={handleCancelPay}
            paying={sending}
          />,
          stageHost
        )}

      <div className="chat__stage">
        {/* Ambient light rays, retinted to the project's petal tone — a quiet
            backdrop confined to the message area, behind the transcript. */}
        <LightRays
          className="chat__rays"
          raysOrigin="top-center"
          raysColor="#f6dde2"
          raysSpeed={0.7}
          lightSpread={0.85}
          rayLength={1.5}
          fadeDistance={1.2}
          saturation={0.9}
          followMouse
          mouseInfluence={0.08}
          noiseAmount={0.05}
          distortion={0.03}
        />

        <div className="chat__list" ref={listRef}>
          {messages.length === 0 && !sending && greeting && (
            <div className="chat__welcome">
              <p className="chat__welcome-title">{greeting}</p>
            </div>
          )}
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
            {(m.cart || m.checkout) && (
              <PaymentCard
                cart={m.cart}
                checkout={m.checkout}
                onConfirm={
                  i === lastAgentIndex && m.cart && !m.checkout && !sending
                    ? handleConfirmPay
                    : undefined
                }
                onCancel={
                  i === lastAgentIndex && m.cart && !m.checkout && !sending
                    ? handleCancelPay
                    : undefined
                }
                busy={sending}
                variant="chat"
              />
            )}
            <span className="chat__time">{timeLabel(m.at)}</span>
          </div>
        ))}

          {sending && (
            <div className="chat__thinking" aria-live="polite" aria-label="Agentry is thinking">
              <DotmCircular20 size={26} dotSize={3} />
            </div>
          )}
        </div>
      </div>

      {!sending && (
        <form className="chat__composer" onSubmit={handleSubmit}>
          <input
            className="chat__composer-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="restock the pantry"
          />
          <div className="chat__composer-bar">
            {config?.model_provider === "gemini" ? (
              <label className="chat__model" title="Gemini model — switch if one is rate-limited">
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
                  <path
                    d="M6 1.2l1.4 3 3.4.4-2.5 2.3.7 3.3L6 9.8 3 11.5l.7-3.3L1.2 5.6l3.4-.4L6 1.2z"
                    stroke="currentColor"
                    strokeWidth="1"
                    strokeLinejoin="round"
                  />
                </svg>
                <select
                  value={config.gemini_model}
                  onChange={(e) => changeModel("gemini_model", e.target.value)}
                  disabled={modelSaving}
                  aria-label="Gemini model"
                >
                  {(config.gemini_models.includes(config.gemini_model)
                    ? config.gemini_models
                    : [config.gemini_model, ...config.gemini_models]
                  ).map((m) => (
                    <option key={m} value={m}>
                      {m.replace(/^gemini-/, "")}
                    </option>
                  ))}
                </select>
              </label>
            ) : config?.model_provider === "bedrock-mantle" ? (
              <label className="chat__model" title="Bedrock Mantle model — switch if one is rate-limited">
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
                  <path
                    d="M6 1.2l1.4 3 3.4.4-2.5 2.3.7 3.3L6 9.8 3 11.5l.7-3.3L1.2 5.6l3.4-.4L6 1.2z"
                    stroke="currentColor"
                    strokeWidth="1"
                    strokeLinejoin="round"
                  />
                </svg>
                <select
                  value={config.mantle_model}
                  onChange={(e) => changeModel("mantle_model", e.target.value)}
                  disabled={modelSaving}
                  aria-label="Bedrock Mantle model"
                >
                  {(config.mantle_models.includes(config.mantle_model)
                    ? config.mantle_models
                    : [config.mantle_model, ...config.mantle_models]
                  ).map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </label>
            ) : config?.model_provider === "groq" ? (
              <label className="chat__model" title="Groq model — switch if one is rate-limited">
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
                  <path
                    d="M6 1.2l1.4 3 3.4.4-2.5 2.3.7 3.3L6 9.8 3 11.5l.7-3.3L1.2 5.6l3.4-.4L6 1.2z"
                    stroke="currentColor"
                    strokeWidth="1"
                    strokeLinejoin="round"
                  />
                </svg>
                <select
                  value={config.groq_model}
                  onChange={(e) => changeModel("groq_model", e.target.value)}
                  disabled={modelSaving}
                  aria-label="Groq model"
                >
                  {(config.groq_models.includes(config.groq_model)
                    ? config.groq_models
                    : [config.groq_model, ...config.groq_models]
                  ).map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              <span className="chat__model chat__model--static" title="Change provider in Settings">
                model
              </span>
            )}

            <div className="chat__composer-actions">
              <button
                type="button"
                className="chat__voice-btn"
                onClick={() => setVoiceOpen(true)}
                aria-label="Open voice mode"
                title="Voice mode"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <rect x="9" y="2.5" width="6" height="11" rx="3" stroke="currentColor" strokeWidth="1.7" />
                  <path
                    d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M8.5 21h7"
                    stroke="currentColor"
                    strokeWidth="1.7"
                    strokeLinecap="round"
                  />
                </svg>
              </button>
              <button
                className="chat__submit"
                type="submit"
                disabled={!input.trim()}
                aria-label="Send message"
              >
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                  <path
                    d="M8 13V3M8 3L3.5 7.5M8 3l4.5 4.5"
                    stroke="currentColor"
                    strokeWidth="1.7"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
            </div>
          </div>
        </form>
      )}
    </div>
  );
}
