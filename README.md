# Agentry

**An autonomous grocery agent that plans, shops, and checks out — end to end, without a human clicking through the flow.**

Built for the [Agents for Humans Hackathon](https://agentsforhumans.devpost.com/) (AWS × Strands Agents SDK) — **Everyday Agents** track.

---

## The problem

Grocery ordering is a small, repetitive chore that still demands full attention: browsing a storefront, checking what's actually in stock, picking substitutes, and clicking through checkout — every time the pantry runs low. It's minor on any one day, but it adds up to real time and attention lost to a task that doesn't need a human doing the clicking.

## What Agentry does

Agentry takes a goal — *"restock the pantry"* or a specific shopping list — and handles it autonomously:

1. **Plans** the order from the goal (what's needed, in what quantity)
2. **Shops** by driving a real quick-commerce storefront directly (search, cart, substitutions)
3. **Pays** via an autonomous payment flow at checkout
4. **Only interrupts you** when there's a real decision to make — an item is out of stock, a price has jumped, a substitution needs your call — via Telegram

It's not a chatbot you have to manage. It runs in the background and reports back.

## Who it's for

Anyone who wants grocery restocking off their plate — busy professionals, people running a household, anyone who'd rather approve a decision than execute a checklist.

---

## How it works

Agentry is built as a [Strands Agents SDK](https://strandsagents.com/) agent. The model reasons over the shopping goal and drives a small set of tools that do the actual work; the agent loop, tool orchestration, and decision-making all run without step-by-step human input.

```
User goal ("restock the pantry")
        |
        v
   Strands Agent  <----->  Model provider (Gemini, via Strands' GeminiModel)
        |
        |-- @tool: browser_automation  --> live storefront (search, cart, checkout)
        |-- @tool: process_payment     --> x402 payment settlement
        |-- @tool: notify_user         --> Telegram (confirmations / decisions needed)
        |
        v
   Completed order + a message in your pocket
        |
        v
   (optional, stretch) Deployed to Bedrock AgentCore Runtime for a live demo link
```

### Tech stack

| Layer | Tool |
|---|---|
| Agent framework | [Strands Agents SDK](https://strandsagents.com/) |
| Model | Google Gemini (via Strands' `GeminiModel` provider) — Bedrock (Claude/Nova) as a stretch swap |
| Storefront automation | Playwright (stealth browser automation) |
| Payments | x402 / HTTP 402 payment protocol |
| Notifications | Telegram Bot API |
| (Stretch) Deployment | Amazon Bedrock AgentCore Runtime |

---

## Getting started

### 0. Hackathon account setup (do this early — separate deadlines apply)

1. [Create a free AWS account](https://signin.aws.amazon.com/signup?request_type=register) if you don't have one
2. Create an **AWS Builder ID** (separate from an AWS account) — required as a submission field
3. Request **$50 in AWS Promotional Credits** via the form linked on the [hackathon Resources page](https://agentsforhumans.devpost.com/resources) — **due September 11, 2026, 12pm PT**, before the Sep 14 submission deadline
4. [Install the Strands Agents SDK](https://strandsagents.com/docs/user-guide/quickstart/overview/) — the quickstart gets a working agent running in under 20 minutes

### Prerequisites

- Python 3.10+
- A Gemini API key
- A Telegram bot token (for notifications)
- Wallet/payment credentials configured for the x402 flow

### Installation

```bash
git clone https://github.com/anbusan19/agentry.git
cd agentry

python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

pip install 'strands-agents[gemini]' strands-agents-tools
pip install -r requirements.txt

playwright install --with-deps chromium
```

### Configuration

Create a `.env` file in the project root (never commit this — see `.gitignore`):

```bash
GEMINI_API_KEY=your_gemini_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id
X402_WALLET_KEY=your_wallet_key
```

### Running locally

```bash
python main.py --goal "restock the pantry"
```

Agentry will plan the order, run the checkout flow against the storefront, settle payment, and send a Telegram message when it's done — or sooner, if it needs a decision from you.

---

## Project structure

```
agentry/
├── agent/
│   ├── agent.py          # Strands Agent definition + model config
│   └── prompts.py        # System prompt / planning instructions
├── tools/
│   ├── browser.py        # Playwright storefront automation tool
│   ├── payment.py        # x402 payment tool
│   └── notify.py         # Telegram notification tool
├── main.py               # Entry point
├── requirements.txt
├── .env.example
├── LICENSE
└── CLAUDE.md             # Guidance for Claude Code working in this repo
```

*(Adjust to match your actual repo layout before submitting.)*

---

## Development workflow

Commit periodically and with meaningful messages rather than one giant commit at the end — this repo's git history is part of the evidence that the Strands port was genuinely built during the Aug 10 – Sep 14 submission window.

- Commit after each logical unit of work (a tool ported, a bug fixed, a working end-to-end run) rather than batching days of work into one commit
- Use a consistent prefix: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`
- Never commit `.env`, API keys, or wallet credentials — double check `.gitignore` covers them
- Push regularly so the remote history (with real timestamps) reflects the actual build timeline

Suggested cadence while building: commit at the end of each work session, and always right after you get something working end-to-end (a fresh checkpoint you can roll back to is worth more than a tidy history).

---

## Submission checklist

- [ ] Track: **Everyday Agents**
- [ ] Text description (features + functionality, who it's for, how it works)
- [ ] Public repo (GitHub/GitLab/Bitbucket) with source, assets, setup instructions
- [ ] `LICENSE` file (MIT or Apache 2.0) — must show in the repo's **About** section
- [ ] This README
- [ ] Architecture diagram (image, not just this text block)
- [ ] Demo video, ≤5 min, uploaded **public to YouTube or Vimeo**, covering: (1) the problem, (2) who it's for, (3) why it matters, plus the agent working live
- [ ] AWS Builder ID linked in submission
- [ ] (Optional) Live demo link — scores better on Technical Implementation
- [ ] (Optional, bonus) builder.aws.com blog post with "Agents for Humans" in the title

## Demo video

[Link to demo video] *(add before submission — must be public on YouTube or Vimeo)*

## Live demo

[Link, if deployed] *(optional — strengthens Technical Implementation scoring)*

---

## License

Licensed under the [MIT License](LICENSE).

## Acknowledgments

Built on the [Strands Agents SDK](https://github.com/strands-agents/harness-sdk) for the Agents for Humans Hackathon, sponsored by AWS. Adapted from the Zepto402/Pantry project, renamed Agentry for this submission (see Disclosure above).