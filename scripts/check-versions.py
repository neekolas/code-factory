#!/usr/bin/env python3
"""Check that all plugin manifests use one name and version."""

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = (
    ROOT / "plugin.json",
    ROOT / ".claude-plugin/plugin.json",
    ROOT / ".claude-plugin/marketplace.json",
    ROOT / ".factory-plugin/plugin.json",
    ROOT / ".factory-plugin/marketplace.json",
)


def main():
    try:
        manifests = [json.loads(path.read_text(encoding="utf-8")) for path in MANIFESTS]
        entries = []
        for manifest in manifests:
            if "plugins" in manifest:
                if len(manifest["plugins"]) != 1:
                    raise ValueError("marketplace must list one plugin")
                entries.append(manifest["plugins"][0])
            else:
                entries.append(manifest)
        names = tuple(entry["name"] for entry in entries)
        versions = tuple(entry["version"] for entry in entries)
        if names != ("code-factory",) * len(MANIFESTS):
            raise ValueError(f"plugin names differ: {names}")
        if versions != ("0.4.1",) * len(MANIFESTS):
            raise ValueError(f"plugin versions differ: {versions}")
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"manifest check failed: {error}", file=sys.stderr)
        return 1
    print("manifest names and versions match: code-factory 0.4.1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
