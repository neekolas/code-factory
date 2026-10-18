#!/usr/bin/env python3
"""Build platform agent files from the definitions in src/agents."""

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "src/agents"
TARGETS = {
    "claude": ROOT / "agents",
    "opencode": ROOT / "opencode/agents",
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


def build(data, platform):
    prompt = (ROOT / data["prompt"]).read_text(encoding="utf-8").strip()
    return f"{frontmatter(data, platform)}\n\n{prompt}\n"


def expected_files():
    expected = {}
    for source in sorted(SOURCES.glob("*.json")):
        data = json.loads(source.read_text(encoding="utf-8"))
        for platform, folder in TARGETS.items():
            expected[folder / f"{data['name']}.md"] = build(data, platform)
    return expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="check generated files")
    args = parser.parse_args()
    expected = expected_files()
    orphans = [
        path
        for folder in TARGETS.values()
        for path in sorted(folder.glob("*.md"))
        if path not in expected
    ]
    if args.check:
        stale = [
            path
            for path, text in expected.items()
            if not path.is_file() or path.read_text(encoding="utf-8") != text
        ]
        problems = [f"stale: {path.relative_to(ROOT)}" for path in stale]
        problems += [f"no source: {path.relative_to(ROOT)}" for path in orphans]
        if problems:
            print("generated agent files are not current:", file=sys.stderr)
            for problem in problems:
                print(f"  {problem}", file=sys.stderr)
            return 1
        print("generated agent files are current")
        return 0
    for path, text in expected.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")
    for path in orphans:
        print(f"no source, not removed: {path.relative_to(ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
