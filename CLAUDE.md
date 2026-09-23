# bland-ai-receptionist

A Bland (bland.ai) voice receptionist template. The user is probably not a developer. Do the work for them and explain in plain English.

## How it works
- `pathway.json` is the single source of truth: the full Bland pathway graph (nodes, edges, webhook step).
- `prompts/` holds every node prompt as a text file. `python3 scripts/prompts.py apply` writes them into `pathway.json`; `export` does the reverse. Edit prompts in `prompts/`, never both places.
- `scripts/setup.py` installs into the user's Bland account (first run), `--update` re-uploads, `--attach` points `phone_number` from `config.json` at it. `.bland-state.json` holds either `agent_id` or `pathway_id`, and that decides how every later update, attach and sim runs.
- Two Bland systems. By default the first run builds a v2 **agent** (the only kind on accounts made after Sept 18, 2026). `--v1` on the first run builds a classic v1 **pathway** instead (retired by Bland on Nov 15, 2026). `scripts/agents.py` does the v2 side: it sends the `pathway.json` graph through Bland's own converter (`POST /v2/agents/migrate/pathways`, `create: false`), then puts `_global.md` into `settings.systemPrompt`, lifts the End Call step out to a top-level `end-call` node (the converter's version never hangs up), and points the inbound edge straight at the flow so Greeting speaks first. `--update` publishes and promotes a new version. The v2 editor lives at v2.app.bland.ai; changes made there are overwritten by `--update`, same as v1.
- `scripts/simulate.py [tests/x.json]` runs a text-only call and exits 0 only if the call reached the end on its own. On v2 it uses Bland's test-chat WebSocket (the agent speaks first, like a real call) and reports the SMS that actually went out instead of variables. The flow's real SMS fires during a sim and goes to the user's own Bland number (Agent Phone Plan caps texts at 20/hour, so don't run more than about 15 sims an hour).
- `.env` holds `BLAND_API_KEY`. Never print it, never commit it, never ask the user to paste it in chat. `setup.py` injects it into the SMS webhook header at upload time, which is why `pathway.json` only contains the placeholder `REPLACE_WITH_BLAND_API_KEY`. Keep it that way.

## First-time setup for a user
Easiest: have the user run `python3 scripts/setup.py` in their own terminal. In a real terminal it asks for the key (hidden), business name, agent name and transfer number, finds their Bland number via `GET /v1/inbound`, installs, runs a test call, and offers to attach. Your Bash tool has no terminal, so when you run it the prompts are skipped and it needs the files already in place:
1. If `config.json` is missing, copy `config.example.json` and fill it in yourself (ask for the business name, agent name and transfer number; `phone_number` comes from `GET /v1/inbound`). If `.env` is missing, `cp .env.example .env` and have the user paste the key into it themselves.
2. `python3 scripts/setup.py`
3. Run all three sims in `tests/`. All must exit 0.
4. `python3 scripts/setup.py --attach`, then have the user call their number.

## Customizing for a different business
Edit `prompts/_global.md` (CONFIG block, who you are, rules) and the step prompts, the `agent_message` in `pathway.json`, the variable names/descriptions in `extractVars` if the collected info changes, and the scripted callers in `tests/`. Then `--update` and re-run every sim at least 3 times. A single pass proves nothing, routing is probabilistic.

## Rules that keep this flow from breaking (each one cost a failed live call)
- A Webhook node re-fires every time it is re-entered, and the global "AI Disclosure" node returns to the previous node. So the caller must never get a turn on the webhook node. It routes instantly via `responsePathways` on `BlandStatusCode`, and the spoken follow-up lives in the next node (Wrap Up).
- Exit conditions (`*.exit.md`) and edge labels may depend only on what the CALLER said, never on something the agent must say first.
- Keep the graph linear. Handle out-of-order info with prompts and whole-conversation `extractVars`, not extra edges. Any variable used in the SMS body must be extracted again in the node right before the webhook.
- Global node labels must start with "ONLY when the caller's most recent message explicitly..." and list what never counts.
- Write prompts like a transcript (contractions, "uh", false starts, loose example lines). Stiff example lines get parroted word for word.
- The pause marker `<|1|>` gives a one second beat at pickup and before hang-up. Allowed performance tags: [chuckles] [laughs] [sighs] [exhales] [say warmly] [say playfully], max one per reply.
- The AI disclosure must always say yes and always offer a human, leading with the offer when the caller is angry. Do not weaken this.
