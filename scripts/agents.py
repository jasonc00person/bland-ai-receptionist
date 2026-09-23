"""Bland's new agent system (accounts made after Sept 18, 2026 only have this one).

pathway.json stays the single source of truth. Bland's own converter turns it into
an agent "scenario", and this file wraps it in a full agent: the house rules become
the system prompt, the End Call step becomes a top-level hang-up, and the call
settings from config.json become agent settings.
"""
import base64, json, os, socket, ssl, struct, sys

from bland import api


def check(r, what):
    if r.get("errors") or r.get("status") == "error":
        sys.exit(f"Could not {what}: {json.dumps(r)[:400]}")
    return r.get("data") or r


def available(key):
    return not api("GET", "/v2/agents?limit=1", key).get("errors")


def build_snapshot(g, cfg, key):
    glob = next(n for n in g["nodes"] if "globalConfig" in n)
    nodes = [n for n in g["nodes"] if n is not glob]
    r = check(api("POST", "/v2/agents/migrate/pathways", key, {
        "pathways": [{"pathway": {"nodes": nodes, "edges": g["edges"], "name": "Receptionist"}}],
        "create": False,
    }), "convert the call flow")
    scenario = r["scenarios"][0]
    flow = scenario["data"]["flow"]
    end_pill = next(n["id"] for n in flow["nodes"] if n["type"] == "end")

    # The converter turns End Call into a talking step that hands back to the hub
    # without hanging up. Lift it out to a real top-level end-call node instead.
    roots = []
    for ec in (n for n in nodes if n.get("type") == "End Call"):
        step = next(n for n in flow["nodes"] if n["id"] == ec["id"])
        into = [e for e in flow["edges"] if e["target"] == step["id"]]
        flow["nodes"].remove(step)
        flow["edges"] = [e for e in flow["edges"] if e["source"] != step["id"]]
        for e in into:
            e["target"] = end_pill
        d = step["data"]
        roots.append({"id": step["id"], "type": "end-call", "position": {"x": 400, "y": 520}, "data": {
            "name": d["name"], "prompt": d["prompt"], "settings": d["settings"], "variables": d["variables"],
            "entry": {"mode": "llm", "label": d["name"], "alwaysPick": False, "conditions": [],
                      "description": " or ".join(e["data"]["label"] for e in into)},
            "useStaticText": False, "loopWhile": "", "ignorePreviousExtractions": False, "useAudioExtraction": False,
        }})

    scenario["data"]["name"] = scenario["data"]["rule"] = "Receptionist"
    scenario["data"]["entry"].update(label="Receptionist", description=(
        "Every caller belongs here for the whole call: booking, the car, questions, banter, complaints, "
        "asking if this is an AI. Only leave once the caller has said they have nothing else."))
    hub = {"id": "agent", "type": "agent", "position": {"x": 400, "y": 160}, "data": {
        "prompt": "Never run the conversation yourself. Keep every caller in the Receptionist flow, "
                  "and once they have said they have nothing else, end the call.",
        "variables": [], "loopWhile": ""}}
    inbound = {"id": "inbound", "type": "inbound", "position": {"x": 400, "y": 0}, "data": {"number": ""},
               "deletable": False, "draggable": False}
    return {
        "behavior": {
            "nodes": [inbound, hub, scenario] + roots,
            # Calls start in the receptionist flow, so the greeting step speaks first
            "edges": [{"id": "e-inbound-agent", "type": "straight", "source": "inbound", "target": scenario["id"],
                       "animated": True, "deletable": False, "selectable": False}],
        },
        "settings": {
            "systemPrompt": glob["globalConfig"]["globalPrompt"],
            "displayName": cfg["agent_name"],
            "voice": cfg.get("voice_id", ""),
            "languages": ["english"],
            "interruptionSensitivity": cfg.get("interruption_threshold", 250),
            "interruptibility": cfg.get("interruptibility", 3),
            "backgroundNoise": "off" if cfg.get("background_track", "none") == "none" else cfg["background_track"],
            "enableMemory": False,
            "voiceCall": {"enabled": True, "record": cfg.get("record_calls", True),
                          "maxDurationMinutes": cfg.get("max_call_minutes", 15), "fallbackNumber": "",
                          "waitForGreeting": False, "noiseCancellation": True, "ignoreButtonPress": False,
                          "requestData": [], "metadata": []},
        },
        "contact": {"inboundNumbers": []},
    }


def create(name, key):
    r = check(api("POST", "/v2/agents", key, {"name": name}), "create the agent")
    return (r.get("agent") or r)["id"]


def ship(agent_id, snapshot, key):
    """Save a new version and put it live (dev -> staging -> production)."""
    check(api("POST", f"/v2/agents/{agent_id}/publish", key, {"snapshot": snapshot}), "publish the agent")
    check(api("POST", f"/v2/agents/{agent_id}/promote", key), "promote the agent to production")


def attach(agent_id, number, key):
    check(api("POST", f"/v2/agents/{agent_id}/inbound/attach", key, {"inbound_numbers": [number]}),
          "attach the number")


# --- Text test chat over Bland's test-chat WebSocket (stdlib only) ---

class Chat:
    def __init__(self, agent_id, key, request_data):
        token = check(api("GET", "/v1/pathway/session", key), "start a test chat")["token"]
        host = "stream-v2.aws.dc8.bland.ai"
        path = f"/ws/connect/blandpathwaychat?agent_chat={agent_id}&version_id=latest&token={token}"
        raw = socket.create_connection((host, 443), timeout=90)
        self.s = ssl.create_default_context().wrap_socket(raw, server_hostname=host)
        k = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall((f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                        f"Sec-WebSocket-Key: {k}\r\nSec-WebSocket-Version: 13\r\nUser-Agent: curl/8.4.0\r\n\r\n").encode())
        head = b""
        while b"\r\n\r\n" not in head:
            head += self.s.recv(1)
        status = head.split(b"\r\n")[0].decode()
        if " 101 " not in status:
            sys.exit(f"Test chat refused: {status}")
        self.send({"type": "setup", "payload": {"requestData": [{"key": k2, "value": v} for k2, v in request_data.items()]}})

    def send(self, obj, opcode=1):
        data = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
        n = len(data)
        head = bytes([0x80 | opcode]) + (bytes([0x80 | n]) if n < 126 else
                                         struct.pack("!BH", 0x80 | 126, n) if n < 65536 else struct.pack("!BQ", 0x80 | 127, n))
        mask = os.urandom(4)
        self.s.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def _exact(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.s.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("closed")
            buf += chunk
        return buf

    def recv(self):
        """Next message as (opcode, bytes). Answers pings itself."""
        while True:
            b1, b2 = self._exact(2)
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack("!H", self._exact(2))[0]
            elif n == 127:
                n = struct.unpack("!Q", self._exact(8))[0]
            data = self._exact(n)
            if b1 & 0x0F == 9:
                self.send(data, opcode=10)
                continue
            return b1 & 0x0F, data

    def turn(self, text=None):
        """Send a caller line (or nothing, for the pickup). Returns (agent replies, hung up)."""
        if text is not None:
            self.send({"type": "text", "payload": text})
        replies, current = [], ""
        self.s.settimeout(90)
        while True:
            try:
                op, data = self.recv()
                m = json.loads(data) if op == 1 else {}
            except (socket.timeout, TimeoutError):  # quiet after "done": waiting on the caller
                return replies + [current] * bool(current), False
            except ConnectionError:
                op = 8
            if op == 8 or "Action Executed to End Call" in m.get("payload", ""):
                return replies + [current] * bool(current), True
            if m.get("type") == "text":
                current += m["payload"]  # replies stream in sentence-sized pieces
            elif m.get("type") == "done":
                replies, current = replies + [current] * bool(current), ""
                self.s.settimeout(4)  # a turn can hold two replies (the text step, then Wrap Up)

def last_text(key, number, since):
    """The text message this number sent after `since` (ISO UTC), if any."""
    for c in api("GET", "/v1/sms/conversations?limit=10", key).get("data") or []:
        if c.get("agent_number") == number and (c.get("last_message_at") or "") >= since:
            return c.get("last_message")
