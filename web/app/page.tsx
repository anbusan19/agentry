import { ArchitectureDiagram } from "@/components/ArchitectureDiagram";
import { Scene } from "@/components/SylvaScene";

const STEPS = [
  {
    n: "01",
    title: "Plan",
    body: "Give it a goal in plain language — “restock the pantry.” The agent breaks it into a concrete cart: quantities, substitutes, budget.",
  },
  {
    n: "02",
    title: "Shop",
    body: "It opens a real quick-commerce storefront and drives it with stealth browser automation — search, compare, add to cart, handle the DOM as it changes.",
  },
  {
    n: "03",
    title: "Pay",
    body: "Checkout is settled from the storefront’s own platform wallet balance (e.g. Zepto Cash). No cards handed around, no blockchain — just the wallet that’s already there.",
  },
  {
    n: "04",
    title: "Check in",
    body: "It only interrupts you on Telegram when a real decision is needed — an out-of-stock staple, a price past your ceiling. Otherwise the order just lands.",
  },
];

const STACK = [
  ["Strands Agents SDK", "Agent, @tool, model providers and hooks — the orchestration layer, rebuilt from scratch."],
  ["Gemini", "Planning and reasoning via Strands’ GeminiModel provider."],
  ["Playwright", "Stealth-configured Chromium driving the live storefront end to end."],
  ["Telegram Bot API", "The single human-in-the-loop channel — used sparingly, on purpose."],
  ["AWS Bedrock AgentCore", "Stretch target for hosted deployment of the Strands agent."],
];

export default function Home() {
  return (
    <main>
      <section className="hero">
        <div className="hero__scene" aria-hidden="true">
          <Scene />
        </div>
        <div className="hero__scrim" aria-hidden="true" />
        <span className="hero__brand">Agentry</span>
        <nav className="hero__nav" aria-label="Primary">
          <a href="#how">How it works</a>
          <a href="#different">Approach</a>
          <a href="#stack">Stack</a>
          <a href="#architecture">Architecture</a>
          <a href="/console">Console</a>
          <a className="hero__nav-cta" href="https://github.com/anbusan19/agentry">
            GitHub
          </a>
        </nav>
        <div className="hero__content">
          <p className="eyebrow">Agents for Humans Hackathon &middot; AWS &times; Strands &middot; Everyday Agents</p>
          <h1>
            The pantry restocks<br />itself.
          </h1>
          <p className="lede">
            Hand it a goal. It plans the order, drives a real storefront, pays from
            the platform wallet, and pings you only when a person needs to decide.
          </p>
          <div className="cta-row">
            <a className="btn btn--primary" href="https://github.com/anbusan19/agentry">
              View the repo
            </a>
            <a className="btn btn--ghost" href="#how">
              How it works
            </a>
          </div>
          <div className="prompt-chip">
            <span className="prompt-chip__dollar">$</span>
            <span className="prompt-chip__cmd">python main.py --goal &quot;restock the pantry&quot;</span>
          </div>
        </div>
      </section>

      <section className="section" id="how">
        <div className="wrap">
          <p className="kicker">01 &middot; Flow</p>
          <h2 className="section__title">Four moves, one goal</h2>
          <p className="section__intro">
            The whole run is autonomous. You set the intent once and read a Telegram
            message at the end &mdash; or in the middle, if something needs you.
          </p>
          <ol className="steps">
            {STEPS.map((s) => (
              <li className="step" key={s.n}>
                <span className="step__n">{s.n}</span>
                <h3 className="step__title">{s.title}</h3>
                <p className="step__body">{s.body}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="section section--alt" id="different">
        <div className="wrap grid-2">
          <div>
            <p className="kicker">02 &middot; Design</p>
            <h2 className="section__title">Built to stay out of your way</h2>
            <p className="section__intro">
              Most &ldquo;assistants&rdquo; ask you to confirm every step. Agentry inverts that:
              it acts, and saves the interruption for the one moment it matters.
            </p>
          </div>
          <ul className="points">
            <li>
              <strong>Real storefront, not a mock.</strong> It automates an actual
              quick-commerce site, selectors and all.
            </li>
            <li>
              <strong>Platform-wallet checkout.</strong> Pays from the storefront&rsquo;s
              native balance &mdash; no card entry, no x402, no chain.
            </li>
            <li>
              <strong>Interrupt budget.</strong> One Telegram thread, used only for
              genuine decisions.
            </li>
            <li>
              <strong>Genuine Strands.</strong> Agent, tools, model providers and hooks &mdash;
              not a thin wrapper over an API call.
            </li>
          </ul>
        </div>
      </section>

      <section className="section" id="architecture">
        <div className="wrap">
          <p className="kicker">03 &middot; Architecture</p>
          <h2 className="section__title">One agent, a handful of tools</h2>
          <p className="section__intro">
            A goal enters as plain text. The Strands agent plans it, then works a
            real storefront through its tools &mdash; surfacing on Telegram only when a
            person has to decide.
          </p>
          <ArchitectureDiagram />
        </div>
      </section>

      <section className="section" id="stack">
        <div className="wrap">
          <p className="kicker">04 &middot; Stack</p>
          <h2 className="section__title">What it&rsquo;s made of</h2>
          <ul className="stack">
            {STACK.map(([name, desc]) => (
              <li className="stack__row" key={name}>
                <span className="stack__name">{name}</span>
                <span className="stack__desc">{desc}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <footer className="footer">
        <div className="wrap">
          <p className="footer__disclosure">
            <strong>Disclosure.</strong> The product concept and the Playwright automation
            approach come from a pre-existing project (Zepto402 &rarr; Pantry &rarr; Agentry).
            The agent-orchestration layer was rebuilt from scratch on the Strands Agents SDK
            for this hackathon submission.
          </p>
          <p className="footer__meta">
            MIT licensed &middot; Background scene: <code>SylvaLivingWorldScene</code> (Living
            Green) from ThreeUI.
          </p>
        </div>
      </footer>
    </main>
  );
}
