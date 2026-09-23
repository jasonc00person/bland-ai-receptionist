#!/usr/bin/env python3
"""Text-only test call against your receptionist. No phone needed, nothing is dialed.

    python3 scripts/simulate.py                          # runs tests/happy_path.json
    python3 scripts/simulate.py tests/rude_caller.json

Heads up: the flow sends its real text message during the test. It goes to
phone_number in config.json (your own Bland number), not to a customer.
"""
import datetime, json, sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from bland import ROOT, api, load_env, load_config, load_state
import agents


def main():
    key = load_env()
    cfg = load_config()
    state = load_state()
    if not (state.get("pathway_id") or state.get("agent_id")):
        sys.exit("Run python3 scripts/setup.py first.")
    turns_file = ROOT / (sys.argv[1] if len(sys.argv) > 1 else "tests/happy_path.json")
    turns = json.loads(turns_file.read_text())
    number = cfg.get("phone_number", "+15555550100")
    finished = test_agent(state["agent_id"], key, number, turns) if state.get("agent_id") else \
        test_pathway(state["pathway_id"], key, number, turns)
    sys.exit(0 if finished else 1)


def test_agent(agent_id, key, number, turns):
    now = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5)
    since = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")  # same shape as Bland's timestamps
    chat = agents.Chat(agent_id, key, {"from": number, "to": number})
    replies, finished = chat.turn()  # the receptionist picks up and speaks first, like a real call
    for reply in replies:
        print(f"AGENT:  {reply}")
    for line in turns:
        if finished:
            break
        print(f"\nCALLER: {line}")
        replies, finished = chat.turn(line)
        for reply in replies:
            print(f"AGENT:  {reply}")
    text = agents.last_text(key, number, since)
    print("\n--- result ---")
    print("Call ended on its own:", "YES" if finished else "NO (check the last reply above)")
    print("Text message:", f'sent: "{text}"' if text else "not sent")
    if text and "{{" in text:
        print("  The text has blanks in it ({{...}}), so a detail wasn't captured.")
    return finished


def test_pathway(pid, key, number, turns):
    c = api("POST", "/v1/pathway/chat/create", key, {
        "pathway_id": pid,
        "request_data": {"from": number, "to": number},
    })
    chat_id = (c.get("data") or c).get("chat_id")
    if not chat_id:
        sys.exit(f"Could not start a test chat: {json.dumps(c)[:300]}")

    finished = False
    for line in turns:
        r = api("POST", f"/v1/pathway/chat/{chat_id}", key, {"message": line})
        d = r.get("data") or r
        print(f"\nCALLER: {line}")
        for reply in d.get("assistant_responses") or []:
            print(f"AGENT:  {reply}")
        print(f"        [step: {d.get('current_node_name')}]")
        if d.get("completed"):
            finished = True
            break

    v = d.get("variables") or {}
    print("\n--- result ---")
    print("Call ended on its own:", "YES" if finished else "NO (check the last step above)")
    print("Text message step:", "sent" if str(v.get("BlandStatusCode")) == "200" else f"not sent (status {v.get('BlandStatusCode')})")
    for k in ("appointment_day", "appointment_time", "service_items", "caller_name", "car_year", "car_make", "car_model"):
        print(f"{k}: {v.get(k)}")
    return finished


if __name__ == "__main__":
    main()
