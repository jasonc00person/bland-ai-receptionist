#!/usr/bin/env python3
"""One-command installer for the AI receptionist.

Reads BLAND_API_KEY from .env and your business details from config.json,
creates the call flow (a Bland "pathway") in YOUR Bland account, and
optionally points your Bland phone number at it.

    python3 scripts/setup.py             # first run: asks for your key and details, installs,
                                         # runs a test call, and offers to connect your number
    python3 scripts/setup.py --attach    # point phone_number from config.json at it
    python3 scripts/setup.py --update    # re-upload after editing prompts/ or config.json
                                         # (overwrites changes made in the Bland editor)

Never creates duplicates: it remembers your pathway in .bland-state.json.
No third-party packages needed.
"""
import getpass, json, os, re, sys, pathlib, subprocess

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from bland import ROOT, api, load_env, load_config, save_state, load_state

PLACEHOLDER_KEY = "REPLACE_WITH_BLAND_API_KEY"
PHONE = re.compile(r"\+\d{11,15}")


def ask(question, default=""):
    answer = input(f"{question}{f' [{default}]' if default else ''}: ").strip()
    return answer or default


def ask_phone(question, default=""):
    while True:
        n = re.sub(r"[^\d+]", "", ask(question, default))
        if not n.startswith("+"):
            n = ("+1" if len(n) == 10 else "+") + n
        if PHONE.fullmatch(n):
            return n
        print("  That doesn't look like a phone number. Try again, like 555-123-4567.")


def yes(question):
    return input(f"{question} [Y/n]: ").strip().lower() in ("", "y", "yes")


def first_run():
    """In a real terminal, ask for anything missing instead of making people edit files."""
    if not sys.stdin.isatty():
        return  # run by a script or Claude Code: the missing-file messages explain what to do
    env, conf = ROOT / ".env", ROOT / "config.json"
    if not os.environ.get("BLAND_API_KEY") and (not env.exists() or "paste-your-key-here" in env.read_text()):
        print("Paste your Bland API key (Bland dashboard > Settings > API Keys).")
        print("Nothing shows on screen while you paste. That's normal, just press Enter after.")
        while True:
            key = getpass.getpass("API key: ").strip()
            if key and not api("GET", "/v1/me", key).get("errors"):
                break
            print("  Bland didn't accept that key. Copy it again and paste it.")
        env.write_text(f"BLAND_API_KEY={key}\n")
        env.chmod(0o600)
        print("Saved your key in .env (it stays on this computer).\n")
    if conf.exists():
        return
    key = load_env()
    numbers = [n["phone_number"] for n in api("GET", "/v1/inbound", key).get("inbound_numbers") or []]
    if not numbers:
        sys.exit("Your Bland account has no phone number yet. Get one in the Bland dashboard, then run this again.")
    cfg = json.loads((ROOT / "config.example.json").read_text())
    cfg["shop_name"] = ask("Business name, the way it should be said on the phone", cfg["shop_name"])
    cfg["agent_name"] = ask("Receptionist's first name", cfg["agent_name"])
    if len(numbers) == 1:
        cfg["phone_number"] = numbers[0]
        print(f"Your receptionist will answer {numbers[0]}.")
    else:
        print("Your Bland numbers: " + ", ".join(numbers))
        cfg["phone_number"] = ask_phone("Which one should the receptionist answer", numbers[0])
    cfg["transfer_number"] = ask_phone("A real person's number, for callers who ask for a human")
    conf.write_text(json.dumps(cfg, indent=2) + "\n")
    print("Saved config.json. Open it any time to change these.\n")


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
    first_run()
    key = load_env()
    cfg = load_config()
    state = load_state()
    if not PHONE.fullmatch(cfg.get("transfer_number", "")):
        sys.exit("Set transfer_number in config.json to a real person's number (format +15551234567).")

    me = api("GET", "/v1/me", key)
    if me.get("status") == "error" or me.get("errors"):
        sys.exit(f"Bland rejected the API key: {json.dumps(me)[:300]}")
    print("Connected to Bland.")

    pid = state.get("pathway_id")
    first = not pid
    if first:
        r = api("POST", "/v1/pathway/create", key, {
            "name": f"{cfg['shop_name']} Receptionist",
            "description": "AI receptionist: books the appointment, takes the work list, texts the caller, hangs up.",
        })
        r = r.get("data") or r
        pid = r.get("pathway_id")
        if not pid:
            sys.exit(f"Could not create the pathway: {json.dumps(r)[:300]}")
        state.update(pathway_id=pid, uploaded=False)
        save_state(state)
        print(f"Created pathway {pid}")
    update = update or not state.get("uploaded", True)  # also retries a first upload that failed
    if not first and update:
        print(f"Updating existing pathway {pid}")
    if not (update or attach):
        print(f"Already installed as pathway {pid}.")
        print("Use --update to re-upload your edits, or --attach to point your phone number at it.")
        return

    if update:
        upload(cfg, key, pid)
        state["uploaded"] = True
        save_state(state)
    if first and sys.stdin.isatty():
        if yes("\nRun a test call now? Takes about a minute, and the test text goes to your own Bland number."):
            if subprocess.run([sys.executable, str(ROOT / "scripts" / "simulate.py")]).returncode:
                print("The test call didn't wrap up on its own this time. It varies a little, so run "
                      "python3 scripts/simulate.py to try again.")
        attach = attach or yes(f"\nConnect {cfg['phone_number']} so the receptionist answers real calls?")
    if attach:
        attach_number(cfg, key, pid)
    else:
        print("Pathway is ready. Run with --attach to point your phone number at it.")
    # The editor opens on an empty draft unless you ask for the live version (version=0)
    print(f"\nSee it in the Bland editor: https://v1.app.bland.ai/dashboard/convo-pathways?id={pid}&version=0")


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
            "interruptibility": cfg.get("interruptibility", 3),  # 0-4, higher = stops talking sooner when the caller cuts in
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
