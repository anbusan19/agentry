import { ArchitectureDiagram } from "@/components/ArchitectureDiagram";
import { Scene } from "@/components/SylvaScene";
import FloatingLines from "@/components/FloatingLines";
import GhostFibers from "@/components/GhostFibers";
import Strands from "@/components/Strands";

const STOREFRONTS = [
  { id: "zepto", label: "Zepto", src: "/zepto.png" },
  { id: "blinkit", label: "Blinkit", src: "/blinkit.png" },
];

const FEATURES = [
  {
    n: "01",
    title: "Plans the order",
    body: "Hand it a goal in plain language — “restock the pantry.” It turns that into a real cart: quantities, substitutes, a budget it won’t blow past.",
    big: true,
  },
  {
    n: "02",
    title: "Shops for real",
    body: "No sandbox, no mock checkout. It opens an actual quick-commerce storefront and drives it end to end, DOM changes and all.",
  },
  {
    n: "03",
    title: "Pays like you would",
    body: "Checkout settles from the storefront’s own wallet balance. No cards handed around, nothing on-chain — just the money that’s already there.",
  },
  {
    n: "04",
    title: "Speaks up only when it matters",
    body: "One Telegram thread, saved for the moments a person actually has to decide — an out-of-stock staple, a price past the ceiling.",
  },
];

const DIFFERENTIATORS = [
  {
    title: "Real storefront, not a mock",
    body: "It automates an actual quick-commerce site — selectors, stock, prices, all of it live.",
  },
  {
    title: "Platform-wallet checkout",
    body: "Pays from the storefront’s native balance. No card entry, no x402, no chain.",
  },
  {
    title: "A budget for interruptions",
    body: "One Telegram thread, spent only on genuine decisions — never step-by-step narration.",
  },
  {
    title: "Genuine Strands",
    body: "Agent, tools, model providers and hooks — a real orchestration layer, not a wrapper over an API call.",
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

      <section className="section feature-section" id="how">
        <div className="feature-section__bg" aria-hidden="true">
          <FloatingLines
            enabledWaves={["middle"]}
            lineCount={[10]}
            lineDistance={[7]}
            linesGradient={["#f6dde2", "#d9c7f2", "#6f7563"]}
            topWavePosition={undefined}
            middleWavePosition={undefined}
            interactive={false}
            parallax={false}
            animationSpeed={0.5}
            mixBlendMode="screen"
          />
        </div>
        <div className="wrap">
          <p className="kicker">Product</p>
          <h2 className="section__title">Everything a pantry run needs, done for you</h2>
          <p className="section__intro">
            One goal in, one order out. Agentry plans, shops, pays and reports back —
            you only hear from it when it counts.
          </p>
          <ul className="bento">
            {FEATURES.map((f) => (
              <li className={`bento__card${f.big ? " bento__card--big" : ""}`} key={f.n}>
                <span className="bento__n">{f.n}</span>
                <h3 className="bento__title">{f.title}</h3>
                <p className="bento__body">{f.body}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="section section--alt" id="different">
        <div className="wrap grid-2 different">
          <div className="different__lead">
            <p className="kicker">Why it&rsquo;s different</p>
            <h2 className="section__title">Built to stay out of your way</h2>
            <p className="section__intro">
              Most &ldquo;assistants&rdquo; ask you to confirm every step. Agentry inverts that:
              it acts, and saves the interruption for the one moment it matters.
            </p>
            <div className="different__visual" aria-hidden="true">
              <Strands
                colors={["#f6dde2", "#d9c7f2", "#6f7563"]}
                count={3}
                speed={0.4}
                amplitude={0.9}
                thickness={0.6}
                glow={2.2}
                intensity={0.55}
                saturation={1.2}
                scale={1.7}
                style={{ width: "100%", height: "100%" }}
              />
            </div>
          </div>
          <ul className="feature-grid">
            {DIFFERENTIATORS.map((d) => (
              <li className="feature-card" key={d.title}>
                <h3>{d.title}</h3>
                <p>{d.body}</p>
              </li>
            ))}
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
          <p className="kicker">Under the hood</p>
          <h2 className="section__title">What it&rsquo;s made of</h2>
          <p className="section__intro">
            No proprietary glue &mdash; a small stack of tools doing exactly what
            they&rsquo;re good at.
          </p>
          <ul className="stack-grid">
            {STACK.map(([name, desc]) => (
              <li className="stack-card" key={name}>
                <span className="stack-card__name">{name}</span>
                <p className="stack-card__desc">{desc}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="cta">
        <div className="cta__bg" aria-hidden="true">
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
        <div className="wrap cta__content">
          <p className="kicker">Get started</p>
          <h2 className="cta__title">Stop restocking it yourself.</h2>
          <p className="cta__body">
            Clone the repo, point it at a storefront login, and give it a goal.
            The next pantry run is on it.
          </p>
          <div className="cta-row">
            <a className="btn btn--primary" href="https://github.com/anbusan19/agentry">
              View the repo
            </a>
            <a className="btn btn--ghost" href="/console">
              Open the console
            </a>
          </div>
          <div className="prompt-chip">
            <span className="prompt-chip__dollar">$</span>
            <span className="prompt-chip__cmd">python main.py --goal &quot;restock the pantry&quot;</span>
          </div>
        </div>
      </section>

      <footer className="footer">
        <div className="wrap footer__grid">
          <div>
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
          <nav className="footer__links" aria-label="Footer">
            <a href="#how">How it works</a>
            <a href="#different">Approach</a>
            <a href="#stack">Stack</a>
            <a href="#architecture">Architecture</a>
            <a href="/console">Console</a>
            <a href="https://github.com/anbusan19/agentry">GitHub</a>
          </nav>
        </div>
      </footer>
    </main>
  );
}
