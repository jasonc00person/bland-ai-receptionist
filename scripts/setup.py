#!/usr/bin/env python3
"""One-command installer for the AI receptionist.

Reads BLAND_API_KEY from .env and your business details from config.json,
creates the call flow (a Bland "pathway") in YOUR Bland account, and
optionally points your Bland phone number at it.

    python3 scripts/setup.py             # first run: create the pathway in your account
    python3 scripts/setup.py --attach    # point phone_number from config.json at it
    python3 scripts/setup.py --update    # re-upload after editing prompts/ or config.json
                                         # (overwrites changes made in the Bland editor)

Never creates duplicates: it remembers your pathway in .bland-state.json.
No third-party packages needed.
"""
import json, os, sys, pathlib, subprocess

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from bland import ROOT, api, load_env, load_config, save_state, load_state

PLACEHOLDER_KEY = "REPLACE_WITH_BLAND_API_KEY"


def build_graph(cfg, key):
    raw = (ROOT / "pathway.json").read_text()
    # The text-message step calls Bland's own SMS API from inside your pathway,
    # so it needs your key in its auth header. It is stored only in your Bland account.
    raw = raw.replace(PLACEHOLDER_KEY, key)
    swaps = {
        "Apex Auto Works": cfg["shop_name"],
        "Clint": cfg["agent_name"],
        "+15550000000": cfg["transfer_number"],
        "+1 (555) 000-0000": cfg["transfer_number"],
    }
    for old, new in swaps.items():
        raw = raw.replace(old, json.dumps(new)[1:-1])
    g = json.loads(raw)
    # This upload endpoint reads the edge condition from a top-level "label"
    for e in g["edges"]:
        e["label"] = (e.get("data") or {}).get("label", "")
    return g


def main():
    attach = "--attach" in sys.argv
    update = "--update" in sys.argv
    key = load_env()
    cfg = load_config()
    state = load_state()

    me = api("GET", "/v1/me", key)
    if me.get("status") == "error" or me.get("errors"):
        sys.exit(f"Bland rejected the API key: {json.dumps(me)[:300]}")
    print("Connected to Bland.")

    pid = state.get("pathway_id")
    if not pid:
        r = api("POST", "/v1/pathway/create", key, {
            "name": f"{cfg['shop_name']} Receptionist",
            "description": "AI receptionist: books the appointment, takes the work list, texts the caller, hangs up.",
        })
        r = r.get("data") or r
        pid = r.get("pathway_id")
        if not pid:
            sys.exit(f"Could not create the pathway: {json.dumps(r)[:300]}")
        state["pathway_id"] = pid
        save_state(state)
        print(f"Created pathway {pid}")
        update = True
    elif update:
        print(f"Updating existing pathway {pid}")
    elif not attach:
        print(f"Already installed as pathway {pid}.")
        print("Use --update to re-upload your edits, or --attach to point your phone number at it.")
        return

    if update:
        upload(cfg, key, pid)
    if attach:
        attach_number(cfg, key, pid)
    else:
        print("Pathway is ready. Run with --attach to point your phone number at it.")
    print(f"\nOpen it in Bland: https://app.bland.ai/dashboard/convo-pathways?id={pid}")


def upload(cfg, key, pid):
    subprocess.run([sys.executable, str(ROOT / "scripts" / "prompts.py"), "apply"], check=True)
    g = build_graph(cfg, key)
    r = api("POST", f"/v1/pathway/{pid}", key, {
        "name": f"{cfg['shop_name']} Receptionist",
        "description": "AI receptionist built from the bland-ai-receptionist template.",
        "nodes": g["nodes"],
        "edges": g["edges"],
    })
    if r.get("status") == "error" or r.get("errors"):
        sys.exit(f"Could not upload the call flow: {json.dumps(r)[:400]}")
    print(f"Uploaded call flow: {len(g['nodes'])} steps, {len(g['edges'])} connections.")


def attach_number(cfg, key, pid):
    if True:
        number = cfg.get("phone_number", "").strip()
        if not number or "X" in number.upper():
            sys.exit("Set phone_number in config.json to your Bland number first (format +15551234567).")
        body = {
            "pathway_id": pid,
            "pathway_version": None,  # follow the live version; clears any old pin left on the number
            "interruption_threshold": cfg.get("interruption_threshold", 250),
            "background_track": cfg.get("background_track", "none"),
            "record": cfg.get("record_calls", True),
            "max_duration": cfg.get("max_call_minutes", 15),
        }
        if cfg.get("voice_id"):
            body["voice"] = cfg["voice_id"]
        r = api("POST", f"/v1/inbound/{number}", key, body)
        if r.get("status") == "error" or r.get("errors"):
            sys.exit(f"Could not attach the number: {json.dumps(r)[:400]}")
        print(f"Attached to {number}. Call it to talk to your receptionist.")


if __name__ == "__main__":
    main()
