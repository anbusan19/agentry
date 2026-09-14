"use client";

import { useCallback, useEffect, useState } from "react";
import FloatingLines from "@/components/FloatingLines";
import GhostFibers from "@/components/GhostFibers";
import Strands from "@/components/Strands";

// A separate, deliberately minimal diagram for the deck — not the landing
// page's <ArchitectureDiagram />, which is authored on a fixed 1564x872
// stage built for a full section of scroll space, not one slide with a nav
// bar docked at the bottom. Same flow, four nodes instead of six, no code
// snippet or knowledge-graph orb, laid out with plain flexbox so it just
// reflows at any slide width instead of needing that component's own
// scroll/scale handling.
const MINI_ARCH_NODES: [string, string][] = [
  ["Goal", "“Restock the pantry”"],
  ["Strands Agent", "Plans, calls tools, reflects"],
  ["Storefront", "Search, cart, checkout"],
  ["Platform wallet", "Pays, no card needed"],
];

const PROBLEM_POINTS = [
  "Open the app, remember what's low, search each item one at a time.",
  "Compare prices and swap out-of-stock brands yourself, every single week.",
  "Pull out a card or scan a UPI code just to pay for a bag of groceries.",
];

const SOLUTION_STEPS = [
  ["Plans", "Turns “restock the pantry” into a real cart — quantities, substitutes, a budget it won’t blow past."],
  ["Shops", "Drives an actual quick-commerce storefront with browser automation. No sandbox, no mock checkout."],
  ["Pays", "Settles from the storefront’s own wallet balance. No card entry needed."],
  ["Reports", "One Telegram message when it's done — or the moment it needs you to decide something."],
];

const DIFFERENTIATORS = [
  ["Genuine Strands", "Agent, tools, model providers and hooks — a real orchestration layer, not a wrapper over an API call."],
  ["Platform-wallet checkout", "Pays from the storefront's native balance. No card entry needed."],
  ["An interrupt budget", "One Telegram thread, spent only on genuine decisions — never step-by-step narration."],
  ["Real-time voice, too", "Amazon Nova 2 Sonic over a live WebSocket — the same tools, spoken instead of typed."],
];

const STACK = [
  "Strands Agents SDK",
  "Gemini / AWS Bedrock",
  "Playwright",
  "Amazon Nova 2 Sonic",
  "Telegram Bot API",
  "AWS Bedrock AgentCore",
];

const TOTAL_SLIDES = 6;

export default function PitchDeck() {
  const [index, setIndex] = useState(0);

  const next = useCallback(() => setIndex((i) => Math.min(TOTAL_SLIDES - 1, i + 1)), []);
  const prev = useCallback(() => setIndex((i) => Math.max(0, i - 1)), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight" || e.key === " ") next();
      else if (e.key === "ArrowLeft") prev();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [next, prev]);

  return (
    <main className="deck">
      <a className="deck__exit" href="/" aria-label="Back to the landing page">
        <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <path d="M3.5 3.5l9 9M12.5 3.5l-9 9" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        </svg>
        Exit
      </a>

      <div className="deck__slide" key={index}>
        {index === 0 && <TitleSlide />}
        {index === 1 && <ProblemSlide />}
        {index === 2 && <SolutionSlide />}
        {index === 3 && <ArchitectureSlide />}
        {index === 4 && <DifferentSlide />}
        {index === 5 && <ClosingSlide />}
      </div>

      <div className="deck__nav">
        <button className="deck__nav-btn" onClick={prev} disabled={index === 0} aria-label="Previous slide">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path d="M10 3l-5 5 5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
        <div className="deck__dots">
          {Array.from({ length: TOTAL_SLIDES }, (_, i) => (
            <button
              key={i}
              className={`deck__dot ${i === index ? "is-active" : ""}`}
              onClick={() => setIndex(i)}
              aria-label={`Go to slide ${i + 1}`}
              aria-current={i === index}
            />
          ))}
        </div>
        <button
          className="deck__nav-btn"
          onClick={next}
          disabled={index === TOTAL_SLIDES - 1}
          aria-label="Next slide"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path d="M6 3l5 5-5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
        <span className="deck__count">
          {index + 1} / {TOTAL_SLIDES}
        </span>
      </div>
    </main>
  );
}

function TitleSlide() {
  return (
    <div className="deck__panel deck__panel--title">
      <div className="deck__bg" aria-hidden="true">
        <Strands
          colors={["#f6dde2", "#d9c7f2", "#6f7563"]}
          count={4}
          speed={0.45}
          amplitude={1.1}
          thickness={0.65}
          glow={2.5}
          intensity={0.6}
          saturation={1.3}
          scale={1.6}
          style={{ width: "100%", height: "100%" }}
        />
      </div>
      <div className="deck__content">
        <p className="deck__eyebrow">Agents for Humans Hackathon &middot; AWS &times; Strands &middot; Everyday Agents</p>
        <h1 className="deck__title">
          Agentry
        </h1>
        <p className="deck__lede">The pantry restocks itself.</p>
        <p className="deck__sub">
          An autonomous grocery-ordering agent that plans the order, drives a real quick-commerce
          storefront, pays from the platform wallet, and only interrupts you when a real decision
          is needed.
        </p>
      </div>
    </div>
  );
}

function ProblemSlide() {
  return (
    <div className="deck__panel">
      <div className="deck__content deck__content--wide">
        <p className="kicker">01 &middot; The problem</p>
        <h2 className="deck__heading">Restocking groceries is a chore nobody enjoys.</h2>
        <ul className="deck__list">
          {PROBLEM_POINTS.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
        <p className="deck__footnote">
          Quick-commerce made buying fast. It didn&rsquo;t make deciding what to buy any easier.
        </p>
      </div>
    </div>
  );
}

function SolutionSlide() {
  return (
    <div className="deck__panel">
      <div className="deck__bg deck__bg--dim" aria-hidden="true">
        <FloatingLines
          enabledWaves={["middle"]}
          lineCount={[8]}
          lineDistance={[7]}
          linesGradient={["#f6dde2", "#d9c7f2", "#6f7563"]}
          topWavePosition={undefined}
          middleWavePosition={undefined}
          interactive={false}
          parallax={false}
          animationSpeed={0.4}
          mixBlendMode="screen"
        />
      </div>
      <div className="deck__content deck__content--wide">
        <p className="kicker">02 &middot; The solution</p>
        <h2 className="deck__heading">Give it a goal. It handles the rest.</h2>
        <ul className="deck__steps">
          {SOLUTION_STEPS.map(([title, body], i) => (
            <li key={title}>
              <span className="deck__step-n">{String(i + 1).padStart(2, "0")}</span>
              <div>
                <h3>{title}</h3>
                <p>{body}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function ArchitectureSlide() {
  return (
    <div className="deck__panel">
      <div className="deck__content deck__content--full">
        <p className="kicker">03 &middot; How it works</p>
        <h2 className="deck__heading">One agent, a handful of tools.</h2>
        <MiniArchitecture />
      </div>
    </div>
  );
}

function MiniArchitecture() {
  return (
    <div className="deck__mini-arch">
      <div className="deck__mini-arch-row">
        {MINI_ARCH_NODES.map(([title, caption], i) => (
          <div className="deck__mini-arch-item" key={title}>
            <div className={`deck__mini-arch-node ${i === 1 ? "is-hub" : ""}`}>
              <span className="deck__mini-arch-n">{String(i + 1).padStart(2, "0")}</span>
              <h3>{title}</h3>
              <p>{caption}</p>
            </div>
            {i < MINI_ARCH_NODES.length - 1 && (
              <span className="deck__mini-arch-arrow" aria-hidden="true">
                &#8594;
              </span>
            )}
          </div>
        ))}
      </div>
      <div className="deck__mini-arch-notes">
        <span>Escalates to Telegram only when a person must decide</span>
        <span>Reads and writes a small purchase-history knowledge graph</span>
      </div>
    </div>
  );
}

function DifferentSlide() {
  return (
    <div className="deck__panel">
      <div className="deck__content deck__content--wide">
        <p className="kicker">04 &middot; Why it&rsquo;s different</p>
        <h2 className="deck__heading">Built to stay out of your way.</h2>
        <ul className="deck__grid">
          {DIFFERENTIATORS.map(([title, body]) => (
            <li key={title}>
              <h3>{title}</h3>
              <p>{body}</p>
            </li>
          ))}
        </ul>
        <div className="deck__pills">
          {STACK.map((s) => (
            <span className="deck__pill" key={s}>
              {s}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

function ClosingSlide() {
  return (
    <div className="deck__panel deck__panel--closing">
      <div className="deck__bg" aria-hidden="true">
        <GhostFibers
          lineColor="#2b2e28"
          glowColor="#6f7563"
          speed={0.18}
          scale={2.1}
          layers={4}
          brightness={1.7}
          blueBoost={0.9}
          vignette={0.85}
          grain={0.04}
        />
      </div>
      <div className="deck__content">
        <p className="kicker">05 &middot; Try it</p>
        <h2 className="deck__heading deck__heading--big">Stop restocking it yourself.</h2>
        <p className="deck__sub">
          Clone the repo, point it at a storefront login, and give it a goal. The next pantry run
          is on it.
        </p>
        <div className="deck__cta-row">
          <a className="btn btn--primary" href="https://github.com/anbusan19/agentry">
            View the repo
          </a>
          <a className="btn btn--ghost" href="/console">
            Open the console
          </a>
        </div>
        <p className="deck__disclosure">
          The product concept and the Playwright automation approach come from a pre-existing
          project. The agent-orchestration layer was rebuilt from scratch on the Strands Agents
          SDK for this hackathon submission.
        </p>
      </div>
    </div>
  );
}
