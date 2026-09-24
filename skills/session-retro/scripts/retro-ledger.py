#!/usr/bin/env python3
"""Shared ledger of retro proposals, for every agent and CLI on this machine.

One JSON object per line in ~/.agents/retro/proposals.jsonl (override with
RETRO_LEDGER). Appends are single lines, so agents can write at the same time.
The latest line for an id wins.

  retro-ledger.py list      --repo URL [--open]          proposals and groups for a repository
  retro-ledger.py add       FILE.jsonl                   append proposals (id and time are filled in)
  retro-ledger.py set       ID key=value ...             record a decision, PR, issue, or merge date
  retro-ledger.py aggregate --repo URL [--group G]       combined evidence and 30-day estimates per group

A proposal record:
  {"id", "group", "repo", "kind": "script|check|skill|agents-md|remove",
   "target": "path", "title", "before", "after",
   "evidence": [{"session": "file", "line": n, "at": "ISO time", "tokens": t, "minutes": m}],
   "carrying_tokens_30d": tokens an added rule costs in 30 days (agents-md only),
   "history_rate_30d": occurrences per 30 days from the miner's history search,
   "status": "proposed|approved|fixed|issue|skipped|withdrawn",
   "pr", "issue", "merged_at", "created_at", "agent"}
The analysis agent chooses "group": the id of an earlier proposal for the same
defect, or a new id. This script only does the arithmetic.
"""
import json, os, statistics, sys, time, uuid
from collections import defaultdict
from datetime import datetime, timezone

LEDGER = os.environ.get("RETRO_LEDGER", os.path.expanduser("~/.agents/retro/proposals.jsonl"))
EFFICACY = {"script": 0.9, "check": 0.9, "skill": 0.6, "agents-md": 0.4, "remove": 0.4}
OPEN = {"proposed", "approved", "issue"}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load():
    latest = {}
    if os.path.exists(LEDGER):
        for line in open(LEDGER):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            latest[r["id"]] = {**latest.get(r["id"], {}), **r}
    return latest


def append(rec):
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with open(LEDGER, "a") as fh:
        fh.write(json.dumps(rec, separators=(",", ":")) + "\n")


def epoch(s):
    """Seconds since the epoch; a time without a zone is taken as UTC."""
    if not s:
        return None
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))]


def aggregate(recs):
    """Combine evidence across proposals, counting each incident once."""
    ev = {}
    for r in recs:
        for e in r.get("evidence", []):
            ev[(e["session"], e.get("line"))] = e
    stamps = [epoch(e["at"]) for e in ev.values() if e.get("at")]
    days = max(30.0, (max(stamps) - min(stamps)) / 86400) if stamps else 30.0
    toks = [e.get("tokens", 0) for e in ev.values()] or [0]
    mins = [e.get("minutes", 0) for e in ev.values()] or [0]
    kind = recs[-1].get("kind", "agents-md")
    # The history rate measured by the miner beats this run's own count.
    rates = [float(r["history_rate_30d"]) for r in recs if r.get("history_rate_30d") not in (None, "")]
    per30 = rates[-1] if rates else len(ev) / days * 30
    eff = EFFICACY.get(kind, 0.4)
    carry = max((float(r.get("carrying_tokens_30d", 0) or 0) for r in recs), default=0.0)
    saved = lambda t: round(t * per30 * eff - carry)
    merged = [epoch(r["merged_at"]) for r in recs if r.get("status") == "fixed" and r.get("merged_at")]
    after_fix = bool(merged) and any(e.get("at") and epoch(e["at"]) > max(merged) for e in ev.values())
    return {"group": recs[0].get("group"), "title": recs[-1].get("title"), "kind": kind,
            "target": recs[-1].get("target"), "proposals": len(recs),
            "agents": len({r.get("agent") for r in recs}),
            "sessions": len({s for (s, _) in ev}), "occurrences": len(ev), "window_days": round(days),
            "tokens_saved_30d": saved(statistics.median(toks)),
            "tokens_saved_30d_range": [saved(pct(toks, .25)), saved(pct(toks, .75))],
            "minutes_saved_30d": round(statistics.median(mins) * per30 * eff, 1),
            "carrying_tokens_30d": round(carry),
            "status": sorted({r.get("status") for r in recs}),
            "links": sorted({x for r in recs for x in (r.get("pr"), r.get("issue")) if x}),
            "fix_ineffective": after_fix}


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd, args = sys.argv[1], sys.argv[2:]
    opt = {args[i]: args[i + 1] for i in range(len(args) - 1) if args[i].startswith("--")}
    recs = load()
    if cmd == "add":
        for line in open(args[0]):
            if line.strip():
                r = json.loads(line)
                r.setdefault("id", "R-" + uuid.uuid4().hex[:8])
                r.setdefault("group", r["id"])
                r.setdefault("status", "proposed")
                r.setdefault("created_at", now())
                append(r)
                print(r["id"])
    elif cmd == "set":
        rid, pairs = args[0], dict(a.split("=", 1) for a in args[1:])
        if rid not in recs:
            sys.exit(f"unknown id {rid}")
        append({"id": rid, **pairs, "updated_at": now()})
    elif cmd in ("list", "aggregate"):
        repo = opt.get("--repo")
        rows = [r for r in recs.values() if not repo or r.get("repo") == repo]
        if cmd == "list":
            if "--open" in args:
                # Fixed groups stay visible so a recurrence can be matched to them.
                groups = {r["group"] for r in rows if r.get("status") in OPEN | {"fixed"}}
                rows = [r for r in rows if r["group"] in groups]
            json.dump(sorted(rows, key=lambda r: (r["group"], r.get("created_at", ""))), sys.stdout, indent=1)
        else:
            by = defaultdict(list)
            for r in sorted(rows, key=lambda r: r.get("created_at", "")):
                if not opt.get("--group") or r["group"] == opt["--group"]:
                    by[r["group"]].append(r)
            json.dump(sorted((aggregate(v) for v in by.values()), key=lambda g: -g["tokens_saved_30d"]),
                      sys.stdout, indent=1)
        print()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
