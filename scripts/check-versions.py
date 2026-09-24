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
)


def main():
    try:
        root, claude, marketplace = (
            json.loads(path.read_text(encoding="utf-8")) for path in MANIFESTS
        )
        plugins = marketplace["plugins"]
        if len(plugins) != 1:
            raise ValueError("marketplace must list one plugin")
        names = (root["name"], claude["name"], plugins[0]["name"])
        versions = (root["version"], claude["version"], plugins[0]["version"])
        if names != ("code-factory",) * 3:
            raise ValueError(f"plugin names differ: {names}")
        if versions != ("0.1.0",) * 3:
            raise ValueError(f"plugin versions differ: {versions}")
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"manifest check failed: {error}", file=sys.stderr)
        return 1
    print("manifest names and versions match: code-factory 0.1.0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
