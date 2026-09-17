# bland-ai-receptionist

A Bland (bland.ai) voice receptionist template. The user is probably not a developer. Do the work for them and explain in plain English.

## How it works
- `pathway.json` is the single source of truth: the full Bland pathway graph (nodes, edges, webhook step).
- `prompts/` holds every node prompt as a text file. `python3 scripts/prompts.py apply` writes them into `pathway.json`; `export` does the reverse. Edit prompts in `prompts/`, never both places.
- `scripts/setup.py` creates the pathway in the user's Bland account (first run), `--update` re-uploads, `--attach` points `phone_number` from `config.json` at it. State lives in `.bland-state.json`.
- `scripts/simulate.py [tests/x.json]` runs a text-only call and exits 0 only if the call reached the end on its own. The flow's real SMS fires during a sim and goes to the user's own Bland number.
- `.env` holds `BLAND_API_KEY`. Never print it, never commit it, never ask the user to paste it in chat. `setup.py` injects it into the SMS webhook header at upload time, which is why `pathway.json` only contains the placeholder `REPLACE_WITH_BLAND_API_KEY`. Keep it that way.

## First-time setup for a user
1. Check `.env` and `config.json` exist (copy from the `.example` files if not) and ask the user to fill in the key themselves.
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
