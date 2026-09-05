# CLAUDE.md

Guidance for Claude Code (and any other AI assistant) working in this repository. Read this before making changes.

## Project context

**Agentry** is an autonomous grocery-ordering agent, submitted to the [Agents for Humans Hackathon](https://agentsforhumans.devpost.com/) (AWS × Strands Agents SDK), **Everyday Agents** track. Deadline: **Sep 14, 2026, 5:00pm PDT**.

It takes a goal ("restock the pantry") and autonomously plans the order, drives a real quick-commerce storefront via browser automation, pays using the storefront's own platform wallet (e.g. Zepto Cash), and only interrupts the user (via Telegram) when a real decision is needed.

This is a **port**, not a from-scratch build: the product concept and the Playwright automation approach come from a pre-existing project (previously named Zepto402, then Pantry, now renamed **Agentry** for this submission). The agent orchestration layer is being rebuilt from scratch on the **Strands Agents SDK** for this hackathon. See the README's Disclosure section — this distinction matters for hackathon rules compliance, so don't blur it in commit messages or docs (e.g. don't describe the whole project as "built from scratch").

Payment is platform-cash checkout only (Zepto Cash or equivalent) — there is no x402/blockchain payment integration in this project, by design. Don't reintroduce x402, wallet keys, or on-chain settlement without the user explicitly asking for it.

## Hackathon constraints — do not violate these

- **Genuine Strands usage matters for scoring.** "Technical Implementation" judges specifically on how thoroughly and skillfully Strands Agents is used, and whether the implementation is non-trivial. Don't build a thin wrapper that could just as easily be a raw API call — use Strands' actual primitives (`Agent`, `@tool`, model providers, hooks) properly.
- **Disclosure, not obfuscation.** When porting logic from the old ADK version, keep it clear in code comments and commit messages that this is adapted from prior work, per the "New Projects Only" rule's disclosure requirement. Don't write commit messages that imply the whole system was invented today.
- **License must stay intact.** The repo must have an MIT or Apache 2.0 `LICENSE` file at the root, visible in GitHub's About section. Don't delete or rename it.
- **No secrets in commits, ever.** `.env`, API keys, Telegram tokens, wallet keys — never in a commit, never in a code comment, never in a docstring example with a real-looking value. Use `.env.example` with placeholder values only.
- **Keep the agent runnable end-to-end.** Judges may run this from the README instructions. Every commit that touches `agent/`, `tools/`, or `main.py` should leave the project in a state where `python main.py --goal "..."` still works, or be clearly marked WIP in the commit message.

## Tech stack

| Layer | Tool |
|---|---|
| Agent framework | Strands Agents SDK (Python) |
| Model | Gemini via Strands' `GeminiModel` (default); Bedrock Claude/Nova is a possible stretch swap |
| Browser automation | Playwright (stealth) |
| Payments | Platform-native wallet balance at checkout (e.g. Zepto Cash) — no x402/blockchain |
| Notifications | Telegram Bot API |
| (Stretch) Deployment | Bedrock AgentCore Runtime |

## Repo conventions

- Tools live in `tools/`, one file per capability, each exposing a single `@tool`-decorated function with a clear docstring (Strands surfaces the docstring to the model as the tool description — write it for the model, not just for humans)
- Agent definition and model config live in `agent/agent.py`; system/planning prompts live in `agent/prompts.py` — keep prompt text out of `agent.py` itself
- Environment variables are the only place secrets live; reference them via `os.environ`, never hardcode
- Keep `requirements.txt` pinned to versions you've actually tested — this is a judged deliverable, not a personal script

## Development commands

```bash
# install
pip install 'strands-agents[gemini]' strands-agents-tools
pip install -r requirements.txt
playwright install --with-deps chromium

# run
python main.py --goal "restock the pantry"
```

There is no test suite yet — if you add one, prefer testing tool functions in isolation (mock the Playwright/Telegram calls) over trying to test full agent runs, since those are slow and non-deterministic.

## Git workflow

Commit periodically, not in one large end-of-project dump. This repo's commit history is part of the evidence that the Strands port was genuinely built during the Aug 10 – Sep 14, 2026 submission window, so a realistic, incremental history is worth more than a clean-looking single commit.

- **Commit after each logical unit of work**: a tool ported to Strands, a bug fixed, a working end-to-end run achieved — not after a whole day of unrelated changes bundled together
- **Message format**: `feat: ...`, `fix: ...`, `docs: ...`, `chore: ...`, `refactor: ...` — short, imperative, specific (e.g. `feat: port browser_automation tool to Strands @tool`, not `feat: updates`)
- **Never commit secrets** — check the diff before committing if you've touched anything under `agent/` or the repo root for stray `.env` values
- **Push regularly** so the remote timestamps reflect the real build timeline, not a burst at the end
- If asked to "make progress and commit," default to: implement one coherent piece → confirm it runs → commit with a message describing exactly what changed and why → move to the next piece. Don't queue up multiple unrelated changes before committing.

## Things to watch for

- **Model swap risk**: if switching from Gemini to Bedrock, expect to re-tune the planning prompt — Bedrock models (Claude/Nova) don't necessarily respond to the same prompt structure Gemini does. Don't assume a drop-in swap works without a fresh end-to-end test.
- **Playwright stealth flags**: storefront automation is fragile to selector/DOM changes on the live site; if a run fails, check for site changes before assuming the agent logic broke.
- **Platform wallet balance**: `browser_automation` pays from whatever platform wallet balance (e.g. Zepto Cash) is available at checkout — make sure the storefront account used for testing has a balance you're actually willing to spend.
- **AgentCore is optional** — don't burn remaining time on it before the core submission checklist (README, license, video, text description, repo public) is done.

## Reference links

- [Strands Agents Quickstart](https://strandsagents.com/docs/user-guide/quickstart/overview/)
- [Strands Agents Examples](https://strandsagents.com/docs/examples/)
- [Amazon Bedrock AgentCore docs](https://docs.aws.amazon.com/bedrock-agentcore/)
- [Deploy a Strands Agent to AgentCore Runtime](https://aws.github.io/bedrock-agentcore-starter-toolkit/user-guide/runtime/quickstart.html)
- [Hackathon Rules](https://agentsforhumans.devpost.com/rules)
- [Hackathon Resources](https://agentsforhumans.devpost.com/resources)