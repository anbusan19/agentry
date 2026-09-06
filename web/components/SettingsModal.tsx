"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Platform {
  id: string;
  label: string;
  url: string;
  supported: boolean;
  connected: boolean;
}

interface Settings {
  weekly_budget_inr: number;
  spent_this_week: number;
  gemini_configured: boolean;
  telegram_configured: boolean;
  platforms: Platform[];
  graph_stats: { items: number; co_purchase_links: number };
}

type Section = "general" | "storefronts" | "budget" | "notifications" | "graph" | "about";

const SECTIONS: { id: Section; label: string }[] = [
  { id: "general", label: "General" },
  { id: "storefronts", label: "Storefronts" },
  { id: "budget", label: "Budget" },
  { id: "notifications", label: "Notifications" },
  { id: "graph", label: "Knowledge graph" },
  { id: "about", label: "About" },
];

function StatusDot({ ok }: { ok: boolean }) {
  return <span className={`settings__dot ${ok ? "settings__dot--ok" : "settings__dot--off"}`} />;
}

export default function SettingsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [section, setSection] = useState<Section>("general");
  const [settings, setSettings] = useState<Settings | null>(null);
  const [budgetInput, setBudgetInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    setError("");
    fetch(`${API_BASE}/api/settings`)
      .then((res) => {
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
        return res.json();
      })
      .then((data: Settings) => {
        setSettings(data);
        setBudgetInput(String(data.weekly_budget_inr));
      })
      .catch((err) => setError(err.message || "Could not load settings."));
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  async function saveBudget() {
    const value = Number(budgetInput);
    if (!Number.isFinite(value) || value < 0) return;

    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ weekly_budget_inr: value }),
      });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      setSettings(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save.");
    } finally {
      setSaving(false);
    }
  }

  if (!open) return null;

  return (
    <div className="settings__backdrop" onClick={onClose}>
      <div className="settings__modal" role="dialog" aria-modal="true" aria-label="Settings" onClick={(e) => e.stopPropagation()}>
        <div className="settings__sidebar">
          <span className="settings__sidebar-title">Settings</span>
          <nav className="settings__nav">
            {SECTIONS.map((s) => (
              <button
                key={s.id}
                className={`settings__nav-item ${section === s.id ? "settings__nav-item--active" : ""}`}
                onClick={() => setSection(s.id)}
              >
                {s.label}
              </button>
            ))}
          </nav>
        </div>

        <div className="settings__content">
          <button className="settings__close" onClick={onClose} aria-label="Close settings">
            &times;
          </button>

          {error && <p className="settings__error">{error}</p>}

          {!settings && !error && <p className="settings__loading">Loading…</p>}

          {settings && section === "general" && (
            <section>
              <h2 className="settings__heading">General</h2>
              <div className="settings__row">
                <span className="settings__row-label">Model</span>
                <span className="settings__row-value">Gemini 3.6 Flash</span>
              </div>
              <div className="settings__row">
                <span className="settings__row-label">Gemini API key</span>
                <span className="settings__row-value">
                  <StatusDot ok={settings.gemini_configured} />
                  {settings.gemini_configured ? "Configured" : "Missing — set GEMINI_API_KEY"}
                </span>
              </div>
              <div className="settings__row">
                <span className="settings__row-label">Agent bridge</span>
                <span className="settings__row-value">
                  <StatusDot ok={true} />
                  {API_BASE}
                </span>
              </div>
            </section>
          )}

          {settings && section === "storefronts" && (
            <section>
              <h2 className="settings__heading">Storefronts</h2>
              <p className="settings__intro">
                Each platform needs its own login, captured once and reused after. Shopping tools
                (search, cart, checkout) are only wired up for platforms marked Supported below —
                the rest can still have a session captured ahead of time.
              </p>
              {settings.platforms.map((p) => (
                <div className="settings__platform" key={p.id}>
                  <div className="settings__platform-head">
                    <span className="settings__platform-name">{p.label}</span>
                    <span className={`settings__badge ${p.supported ? "settings__badge--ok" : "settings__badge--soon"}`}>
                      {p.supported ? "Supported" : "Coming soon"}
                    </span>
                  </div>
                  <div className="settings__row">
                    <span className="settings__row-label">Login</span>
                    <span className="settings__row-value">
                      <StatusDot ok={p.connected} />
                      {p.connected ? "Connected" : "Not connected"}
                    </span>
                  </div>
                  {!p.connected && (
                    <code className="settings__cmd">python scripts/capture_session.py {p.id}</code>
                  )}
                </div>
              ))}
            </section>
          )}

          {settings && section === "budget" && (
            <section>
              <h2 className="settings__heading">Budget</h2>
              <p className="settings__intro">
                checkout refuses to run over this without asking you first. Spend is measured over
                the trailing 7 days from every real checkout, not a calendar week.
              </p>
              <div className="settings__row">
                <span className="settings__row-label">Spent, last 7 days</span>
                <span className="settings__row-value">₹{settings.spent_this_week}</span>
              </div>
              <label className="settings__field">
                <span className="settings__row-label">Weekly cap (₹)</span>
                <input
                  className="settings__input"
                  type="number"
                  min="0"
                  value={budgetInput}
                  onChange={(e) => setBudgetInput(e.target.value)}
                />
              </label>
              <button className="settings__save" onClick={saveBudget} disabled={saving}>
                {saving ? "Saving…" : "Save"}
              </button>
            </section>
          )}

          {settings && section === "notifications" && (
            <section>
              <h2 className="settings__heading">Notifications</h2>
              <div className="settings__row">
                <span className="settings__row-label">Telegram</span>
                <span className="settings__row-value">
                  <StatusDot ok={settings.telegram_configured} />
                  {settings.telegram_configured ? "Configured" : "Not configured"}
                </span>
              </div>
              <p className="settings__intro">
                {settings.telegram_configured
                  ? "The agent will message you here when it needs a decision, or once an order is done."
                  : "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env to enable this."}
              </p>
            </section>
          )}

          {settings && section === "graph" && (
            <section>
              <h2 className="settings__heading">Knowledge graph</h2>
              <div className="settings__row">
                <span className="settings__row-label">Items tracked</span>
                <span className="settings__row-value">{settings.graph_stats.items}</span>
              </div>
              <div className="settings__row">
                <span className="settings__row-label">Co-purchase links</span>
                <span className="settings__row-value">{settings.graph_stats.co_purchase_links}</span>
              </div>
              <p className="settings__intro">
                Built from real order history and updated after every checkout. Stored locally in
                data/purchases_graph.json, never committed to the repo.
              </p>
            </section>
          )}

          {settings && section === "about" && (
            <section>
              <h2 className="settings__heading">About</h2>
              <p className="settings__intro">
                Agentry is an autonomous grocery-ordering agent, built on the Strands Agents SDK
                for the Agents for Humans Hackathon (AWS x Strands), Everyday Agents track.
              </p>
              <div className="settings__row">
                <span className="settings__row-label">Source</span>
                <a
                  className="settings__link"
                  href="https://github.com/anbusan19/agentry"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  github.com/anbusan19/agentry
                </a>
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
