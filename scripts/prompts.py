#!/usr/bin/env python3
"""Keep the readable prompt files in prompts/ and pathway.json in sync.

    python3 scripts/prompts.py export    # pathway.json -> prompts/*.md
    python3 scripts/prompts.py apply     # prompts/*.md -> pathway.json  (setup.py --update does this for you)

Each step of the call has "<Step Name>.md" (what the agent does there) and, when the
step waits on something, "<Step Name>.exit.md" (what must be true before moving on).
"_global.md" is the personality and house rules every step shares.
"""
import json, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
GRAPH = ROOT / "pathway.json"
DIR = ROOT / "prompts"


def items(g):
    for n in g["nodes"]:
        if "globalConfig" in n:
            yield DIR / "_global.md", n["globalConfig"], "globalPrompt"
            continue
        d = n["data"]
        yield DIR / f"{d['name']}.md", d, "prompt"
        if "condition" in d:
            yield DIR / f"{d['name']}.exit.md", d, "condition"


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    g = json.loads(GRAPH.read_text())
    if mode == "export":
        DIR.mkdir(exist_ok=True)
        for path, holder, field in items(g):
            path.write_text(holder.get(field, "").rstrip() + "\n")
        print(f"Wrote {len(list(DIR.glob('*.md')))} files to prompts/")
    elif mode == "apply":
        changed = 0
        for path, holder, field in items(g):
            if path.exists():
                text = path.read_text().rstrip()
                if holder.get(field, "").rstrip() != text:
                    holder[field] = text
                    changed += 1
        GRAPH.write_text(json.dumps(g, indent=2))
        print(f"Applied prompts/ to pathway.json ({changed} changed)")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
