#!/usr/bin/env python3
"""Validate skills with support for Claude's invocation policy."""

import subprocess
import sys
import tempfile
from pathlib import Path


def standard_content(content):
    """Check the Claude extension before passing standard fields to skills-ref."""
    header, separator, body = content.partition("\n---\n")
    if not content.startswith("---\n") or not separator:
        return content

    lines = header.splitlines()
    policies = [line for line in lines if line.startswith("disable-model-invocation:")]
    if len(policies) > 1:
        raise ValueError("Duplicate disable-model-invocation field")
    for policy in policies:
        if policy not in (
            "disable-model-invocation: true",
            "disable-model-invocation: false",
        ):
            raise ValueError("disable-model-invocation must be true or false")
        lines.remove(policy)
    return "\n".join(lines) + separator + body


def main():
    root = Path(__file__).resolve().parent.parent
    skills = [Path(arg) for arg in sys.argv[1:]] or sorted((root / "skills").iterdir())
    status = 0
    with tempfile.TemporaryDirectory(prefix="code-factory-skills-") as temporary:
        for skill in skills:
            print(f"Validating {skill}", flush=True)
            try:
                content = standard_content((skill / "SKILL.md").read_text())
            except (OSError, ValueError) as error:
                print(f"{skill}: {error}", file=sys.stderr)
                status = 1
                continue
            target = Path(temporary) / skill.name
            target.mkdir(exist_ok=True)
            (target / "SKILL.md").write_text(content)
            result = subprocess.run(
                ["npx", "--yes", "skills-ref@0.1.5", "validate", str(target)],
                check=False,
            )
            if result.returncode:
                status = 1
    return status


if __name__ == "__main__":
    sys.exit(main())
