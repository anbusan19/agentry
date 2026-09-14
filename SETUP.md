## Testing instructions

**Note up front:** Agentry places a real order and pays from a real platform wallet balance
(e.g. Zepto Cash) on a live storefront. To fully exercise checkout, you'll need your own
account on the storefront with a funded wallet — we can't provide test credentials or a
sandboxed storefront (none exists for Zepto/Blinkit). Everything up through cart-building
can be tested with $0 at risk; only the final `checkout` call spends money, and it requires
`confirm=True`. If you'd rather not fund a wallet, the demo video shows a full live run
end-to-end, including checkout.

### 1. Prerequisites

- Python 3.10+
- Node.js + [pnpm](https://pnpm.io/) (only if testing the optional web console)
- A [Gemini API key](https://aistudio.google.com/apikey) (free tier works)
- A Telegram bot token + chat ID for notifications ([BotFather](https://t.me/BotFather) on Telegram — takes ~2 min)
- A Zepto or Blinkit account, logged in manually once (see step 3) — a funded wallet is only needed if you want to test checkout itself

### 2. Install

```bash
git clone https://github.com/anbusan19/agentry.git
cd agentry

python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

pip install 'strands-agents[gemini]' strands-agents-tools
pip install -r requirements.txt
playwright install --with-deps chromium
```

### 3. Configure

```bash
cp .env.example .env
```

Fill in at minimum:
```
GEMINI_API_KEY=your_key
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
```
(`MODEL_PROVIDER=gemini` is the default — leave it as is unless you want to test the Bedrock
or Groq paths, which need their own keys documented in `.env.example`.)

### 4. Log in to the storefront once

There's no automated phone/OTP flow — you log in manually, once, and the session is reused:

```bash
python scripts/capture_session.py
```

A real browser window opens. Log in as you normally would on the site, then from a second
terminal:

```bash
touch /tmp/agentry_capture_done
```

The session is cached locally (gitignored) and every subsequent run reuses it.

### 5. Run the agent

```bash
python main.py --goal "restock the pantry"
```

or a specific list:

```bash
python main.py --goal "get me a wheat bread and some ice cream"
```

Watch the terminal for the agent's plan and tool calls. It will search the storefront, build
a cart, check the wallet balance, and — only if you've funded the wallet and it proceeds to
`checkout` — place a real order. You should also get exactly one Telegram message when it
finishes, or sooner if it needs a decision from you (out of stock, over budget, etc.).

### 6. (Optional) Web console + voice mode

Two terminals:

```bash
# terminal 1 — agent bridge
source .venv/bin/activate
uvicorn server:app --reload --port 8000

# terminal 2 — frontend
cd web
pnpm install
pnpm dev
```

Open `http://localhost:3000/console` for the chat UI and a live view of the purchase-history
knowledge graph. The mic button in the console enables real-time voice mode (Nova Sonic) —
same tools, spoken instead of typed.

### What to expect / known limits

- First run against a storefront can be slow (page loads, stealth automation) — this is
  normal, not a hang.
- If a run fails partway, it's most likely a live DOM change on the storefront's end, not
  agent logic — the README's "Things to watch for" section has notes on this.
- Bedrock (`MODEL_PROVIDER=bedrock-mantle`) requires both IAM credentials *and* that model
  access be explicitly enabled in the AWS console for your region — a common gotcha if you
  try that path.
