#!/usr/bin/env python3
"""Build platform agent files from one definition and the review prompt."""

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/agents/adversarial-reviewer.json"
PROMPT = ROOT / "skills/executing-plans/references/review-prompt.md"
TARGETS = {
    "claude": ROOT / "agents/adversarial-reviewer.md",
    "opencode": ROOT / "opencode/agents/adversarial-reviewer.md",
}


def frontmatter(data, platform):
    fields = {"name": data["name"], "description": data["description"]}
    fields.update(data[platform])
    lines = ["---"]
    for key, value in fields.items():
        if isinstance(value, dict):
            lines.append(f"{key}:")
            lines.extend(f"  {child}: {setting}" for child, setting in value.items())
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


def build(data, platform, prompt):
    match = re.search(r"^```text\n(.*?)^```\s*$", prompt, re.MULTILINE | re.DOTALL)
    if match is None:
        raise ValueError(f"no text fence in {PROMPT}")
    tail = prompt[match.end() :].strip()
    if not tail.startswith("Severity:") or "\n\nScope:" not in tail:
        raise ValueError(f"missing Severity or Scope paragraphs in {PROMPT}")
    preamble = (
        "You have clean context. Return the review only to the caller. "
        "Never write the review to Ref, a document, or a file."
    )
    return f"{frontmatter(data, platform)}\n\n{preamble}\n\n{match.group(1).strip()}\n\n{tail}\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="check generated files")
    args = parser.parse_args()
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    prompt = PROMPT.read_text(encoding="utf-8")
    stale = []
    for platform, target in TARGETS.items():
        expected = build(data, platform, prompt)
        if args.check:
            if not target.is_file() or target.read_text(encoding="utf-8") != expected:
                stale.append(str(target.relative_to(ROOT)))
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(expected, encoding="utf-8")
            print(f"wrote {target.relative_to(ROOT)}")
    if stale:
        print("stale generated agent files: " + ", ".join(stale), file=sys.stderr)
        return 1
    if args.check:
        print("generated agent files are current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
