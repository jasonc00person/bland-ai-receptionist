"""Tiny shared helpers: .env loading, config, and Bland API calls (stdlib only)."""
import json, os, sys, pathlib, urllib.request, urllib.error

ROOT = pathlib.Path(__file__).resolve().parent.parent
STATE = ROOT / ".bland-state.json"


def load_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    key = os.environ.get("BLAND_API_KEY", "")
    if not key or key.startswith("paste"):
        sys.exit("No API key found. Copy .env.example to .env and paste your Bland API key in it.")
    return key


def load_config():
    p = ROOT / "config.json"
    if not p.exists():
        sys.exit("config.json is missing. Copy config.example.json to config.json and fill it in.")
    return json.loads(p.read_text())


def load_state():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save_state(state):
    STATE.write_text(json.dumps(state, indent=2))


def api(method, path, key, body=None):
    req = urllib.request.Request(
        "https://api.bland.ai" + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "authorization": key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "curl/8.4.0",  # Bland's firewall rejects Python's default user agent
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        text = e.read().decode(errors="replace")
        try:
            return json.loads(text)
        except ValueError:
            return {"status": "error", "message": f"HTTP {e.code}: {text[:300]}"}
