#!/usr/bin/env python3
"""Mine Claude Code and Codex transcripts into a compact JSON summary for session-retro.

The model reads this summary, never a raw transcript. Every sample string is
scrubbed of secrets and home paths before it is printed.

  retro-mine.py --claude SESSION.jsonl ... --codex ROLLOUT.jsonl|THREAD_ID ...
                [--since ISO-TIME] [--repo PATH] [--history-days 60] [--gate-only]

Claude Code subagent transcripts in <session-id>/subagents/ are included.
Token figures are input-token equivalents: uncached input x1, cache write
x1.25, cache read x0.1, output x5. They compare incidents; they are not bills.
"""
import argparse, glob, json, os, re, statistics, subprocess, sys, time
from collections import defaultdict
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
OUT_RATIO, CACHE_READ, CACHE_WRITE = 5.0, 0.1, 1.25
GAP_CAP_S = 600          # one idle gap counts at most 10 minutes inside a span
SPAN_CALLS = 20          # a recovery span ends at most 20 calls after the failure
STALL_S = 900            # a gap longer than this is reported as a stall

SECRETS = [
    (r"sk-[A-Za-z0-9_-]{20,}", "api-key"), (r"gh[pousr]_[A-Za-z0-9]{30,}", "github-token"),
    (r"xox[abposr]-[A-Za-z0-9-]{10,}", "slack-token"), (r"AKIA[0-9A-Z]{16}", "aws-key"),
    (r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}", "jwt"),
    (r"github_pat_[A-Za-z0-9_]{22,}", "github-token"),
    (r"(?i)(bearer|token|secret|password|api[_-]?key)([\"':= ]+)[A-Za-z0-9_./+-]{12,}", None),
    (r"\b[0-9a-f]{40,}\b", "hex"),
]
FAIL_MARKERS = re.compile(
    r"command not found|unknown recipe|justfile does not contain|no such file or directory|"
    r"unrecognized (option|argument)|unexpected argument|permission denied|operation not permitted|"
    r"traceback \(most recent call last\)|error\[E\d+\]|error: could not compile|"
    r"address already in use|connection refused|cannot connect to the docker|"
    r"no space left on device|disk quota exceeded|database or disk is full", re.I)
# A full disk usually means the orchestrator left finished worktrees in place.
DISK_FULL = re.compile(r"no space left on device|disk quota exceeded|database or disk is full", re.I)
# A missing command, recipe, or flag is a repository defect even when seen once.
SCRIPT_CLASS = re.compile(
    r"command not found|unknown recipe|justfile does not contain|"
    r"unrecognized (option|argument)|unexpected argument", re.I)
# These exit 1 for "no match" or "different"; that is an answer, not a failure.
QUERY_TOOLS = {"grep", "rg", "ugrep", "find", "diff", "test", "[", "cmp", "git diff", "git grep"}
EXIT_NONZERO = re.compile(r'"exit_code":\s*[1-9]|exit code:?\s*[1-9]|exited with (code|status) [1-9]', re.I)
PAIN = re.compile(
    r"\b(still (not|failing|broken)|same error|i (already|told you)|that'?s not what|revert that|"
    r"are you stuck|keep going|continue\.?$|why did you|status\?)", re.I)


def scrub(s, n=240):
    s = s.replace(HOME, "~")
    s = re.sub(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(-----END [A-Z ]*PRIVATE KEY-----|$)",
               "[REDACTED:private-key]", s, flags=re.S)
    s = re.sub(r"://[^/\s:@]+:[^@\s]+@", "://[REDACTED:url-credentials]@", s)
    for pat, kind in SECRETS:
        s = re.sub(pat, (lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]") if kind is None
                   else f"[REDACTED:{kind}]", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:n]


def norm(s):
    s = s.replace(HOME, "~")
    s = re.sub(r"(/[\w.@-]+)+", "<path>", s)
    s = re.sub(r"\b[0-9a-f]{7,}\b", "<hex>", s)
    s = re.sub(r"\d+", "N", s)
    return re.sub(r"\s+", " ", s).strip()[:120]


def needle(err):
    """Longest literal piece of a raw error line, for a cheap history search."""
    parts = re.split(r"(?:/[\w.@-]+)+|\b[0-9a-f]{7,}\b|\d+|[\"'`\\]", err)
    best = max((x.strip() for x in parts), key=len, default="")
    return best if len(best) >= 12 else None


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat(timespec="seconds")


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() if s else None


def cmd_key(tool, inp):
    """Short, stable name for what the call tried to do."""
    c = ""
    if isinstance(inp, dict):
        c = inp.get("command") or inp.get("cmd") or ""
        if isinstance(c, list):
            c = " ".join(map(str, c))
    elif isinstance(inp, str):
        c = inp
    if not c:
        return tool
    inner = re.search(r"nix-shell\s+['\"]([^'\"]+)", c)
    words = [w for w in re.split(r"\s+", (inner.group(1) if inner else c).strip()) if w and "=" not in w]
    words = [w for w in words if w not in ("cd", "&&", "dev/agent-run")] or words
    return f"{tool}:{' '.join(words[:2])}"


def first_error_line(text):
    for line in text.splitlines():
        if FAIL_MARKERS.search(line) or EXIT_NONZERO.search(line) or re.search(r"\berror\b", line, re.I):
            return line
    return text.strip().splitlines()[0] if text.strip() else ""


class Events:
    """One transcript as a list of (time, kind, data) with a token weight per event."""

    def __init__(self, path, agent):
        self.path, self.agent, self.ev = path, agent, []


def load_claude(path, agent):
    E = Events(path, agent)
    calls, usage = {}, {}
    for ln, line in enumerate(open(path, errors="ignore"), 1):
        try:
            o = json.loads(line)
        except ValueError:
            continue
        t = ts(o.get("timestamp"))
        if o.get("type") == "system" and "compact" in str(o.get("subtype", "")):
            E.ev.append((t, "compact", None))
        msg = o.get("message") or {}
        content = msg.get("content")
        if o.get("type") == "assistant":
            u = msg.get("usage") or {}
            w = (u.get("input_tokens", 0) + CACHE_WRITE * u.get("cache_creation_input_tokens", 0)
                 + CACHE_READ * u.get("cache_read_input_tokens", 0) + OUT_RATIO * u.get("output_tokens", 0))
            # A message split across several lines repeats its usage; count it once.
            usage[msg.get("id") or o.get("uuid") or ln] = (t, w)
            for c in content if isinstance(content, list) else []:
                if c.get("type") == "tool_use":
                    calls[c.get("id")] = (c.get("name"), c.get("input"))
        elif o.get("type") == "user":
            if isinstance(content, str) and not o.get("isSidechain"):
                if PAIN.search(content[:400]):
                    E.ev.append((t, "pain", scrub(content, 120)))
                continue
            for c in content if isinstance(content, list) else []:
                if c.get("type") == "tool_result":
                    name, inp = calls.get(c.get("tool_use_id"), ("?", None))
                    body = c.get("content")
                    text = body if isinstance(body, str) else " ".join(
                        x.get("text", "") for x in body or [] if isinstance(x, dict))
                    failed = bool(c.get("is_error")) or bool(FAIL_MARKERS.search(text[:2000])) \
                        or bool(EXIT_NONZERO.search(text[:2000]))
                    E.ev.append((t, "call", (name, inp, failed, text, ln)))
                elif c.get("type") == "text" and PAIN.search(c.get("text", "")[:400]):
                    E.ev.append((t, "pain", scrub(c["text"], 120)))
    E.ev += [(t, "tokens", w) for (t, w) in usage.values()]
    return E


def load_codex(path):
    E = Events(path, "codex:" + os.path.basename(path)[8:27])
    calls, prev = {}, {}
    for ln, line in enumerate(open(path, errors="ignore"), 1):
        try:
            o = json.loads(line)
        except ValueError:
            continue
        t, p = ts(o.get("timestamp")), o.get("payload") or {}
        if o.get("type") == "compacted":
            E.ev.append((t, "compact", None))
        pt = p.get("type")
        if pt == "token_count":
            # token_count repeats snapshots; the cumulative total grows only once per request.
            tot = ((p.get("info") or {}).get("total_token_usage")) or {}
            if tot == prev:
                continue
            u = {k: v - prev.get(k, 0) if v >= prev.get(k, 0) else v for k, v in tot.items()
                 if isinstance(v, (int, float))}
            prev = tot
            cached = u.get("cached_input_tokens", 0)
            w = (max(u.get("input_tokens", 0) - cached, 0) + CACHE_READ * cached
                 + CACHE_WRITE * u.get("cache_write_input_tokens", 0) + OUT_RATIO * u.get("output_tokens", 0))
            E.ev.append((t, "tokens", w))
        elif pt in ("custom_tool_call", "function_call"):
            raw = p.get("input") or p.get("arguments") or ""
            try:
                inp = json.loads(raw) if isinstance(raw, str) and raw.startswith("{") else raw
            except ValueError:
                inp = raw
            calls[p.get("call_id")] = (p.get("name"), inp)
        elif pt in ("custom_tool_call_output", "function_call_output"):
            name, inp = calls.get(p.get("call_id"), ("?", None))
            out = p.get("output")
            text = out if isinstance(out, str) else json.dumps(out)
            failed = bool(EXIT_NONZERO.search(text[:4000])) or bool(FAIL_MARKERS.search(text[:4000]))
            E.ev.append((t, "call", (name, inp, failed, text, ln)))
        elif pt == "message" and p.get("role") == "user":
            tx = " ".join(c.get("text", "") for c in p.get("content", []) if isinstance(c, dict))
            if not tx.startswith("<") and PAIN.search(tx[:400]):
                E.ev.append((t, "pain", scrub(tx, 120)))
    return E


def resolve_codex(arg):
    if os.path.exists(arg):
        return arg
    hits = glob.glob(os.path.join(HOME, ".codex/sessions/*/*/*/rollout-*" + arg + ".jsonl"))
    if not hits:
        sys.exit(f"no Codex rollout for thread {arg}")
    return hits[0]


def analyse(E):
    """Failed calls with the cost of recovering from each one."""
    evs = sorted((e for e in E.ev if e[0] is not None), key=lambda e: e[0])
    incidents, calls, gaps = [], 0, []
    fails = [j for j, e in enumerate(evs) if e[1] == "call" and e[2][2]]
    for i, (t, kind, data) in enumerate(evs):
        if i and t - evs[i - 1][0] > STALL_S:
            prev = next((d for (_, k, d) in reversed(evs[:i]) if k == "call"), None)
            gaps.append({"agent": E.agent, "minutes": round((t - evs[i - 1][0]) / 60),
                         "at": iso(evs[i - 1][0]),
                         "after": scrub(cmd_key(prev[0], prev[1]), 120) if prev else None})
        if kind != "call":
            continue
        calls += 1
        name, inp, failed, text, ln = data
        if not failed:
            continue
        key = cmd_key(name, inp)
        verb = key.split(":", 1)[-1]
        if any(verb == q or verb.startswith(q + " ") for q in QUERY_TOOLS) and not FAIL_MARKERS.search(text[:2000]):
            continue
        # Recovery span: to the next successful call with the same key, else the next success.
        window = [j for j in range(i + 1, len(evs)) if evs[j][1] == "call"][:SPAN_CALLS]
        ok = [j for j in window if not evs[j][2][2]]
        end = next((j for j in ok if cmd_key(evs[j][2][0], evs[j][2][1]) == key), None)
        end = end or (ok[0] if ok else (window[-1] if window else i))
        # Spans never overlap: the next failure starts its own span. Tokens stop
        # before that failure; time runs up to its timestamp.
        nxt = next((j for j in fails if j > i), None)
        stop = nxt if nxt is not None and nxt <= end else end + 1
        toks = sum(d for (_, k, d) in evs[i:stop] if k == "tokens") + len(text) / 4
        secs = sum(min(evs[j][0] - evs[j - 1][0], GAP_CAP_S) for j in range(i + 1, min(stop + 1, len(evs))))
        err = first_error_line(text)
        incidents.append({"key": key, "err": norm(scrub(err, 400)), "sample_cmd": scrub(json.dumps(inp) if inp else ""),
                          "sample_err": scrub(err), "needle": needle(err), "tokens": toks, "seconds": secs, "agent": E.agent,
                          "script_class": bool(SCRIPT_CLASS.search(err)),
                          "disk_full": bool(DISK_FULL.search(text[:4000])),
                          "where": {"file": E.path.replace(HOME, "~"), "line": ln},
                          "at": iso(t)})
    return incidents, calls, gaps


def history_hits(needles, repo, days, exclude):
    """Sessions in the last `days` days, for this repository, whose text contains each needle."""
    cutoff = time.time() - days * 86400
    name = os.path.basename(os.path.abspath(repo)) if repo else ""
    claude = glob.glob(os.path.join(HOME, ".claude/projects", "*", "*.jsonl")) + \
        glob.glob(os.path.join(HOME, ".claude/projects", "*", "*", "subagents", "*.jsonl"))
    files = [f for f in claude if (not name or name in f) and os.path.getmtime(f) > cutoff
             and os.path.realpath(f) not in exclude]
    for f in glob.glob(os.path.join(HOME, ".codex/sessions/*/*/*/rollout-*.jsonl")):
        if os.path.getmtime(f) > cutoff and os.path.realpath(f) not in exclude:
            with open(f, errors="ignore") as fh:
                if not name or name in fh.readline():
                    files.append(f)
    out = {}
    if not files:   # rg with no paths would search the working directory
        return out, 0
    for n in needles:
        if not n:
            continue
        try:
            r = subprocess.run(["rg", "-F", "-l", "--", n, *files], capture_output=True, text=True,
                               stdin=subprocess.DEVNULL)
            hits = len(r.stdout.splitlines())
            out[n] = hits if hits <= len(files) / 2 else "generic"
        except (FileNotFoundError, OSError):
            out[n] = None
    return out, len(files)


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--claude", nargs="*", default=[])
    ap.add_argument("--codex", nargs="*", default=[])
    ap.add_argument("--repo", default=".")
    ap.add_argument("--history-days", type=int, default=60)
    ap.add_argument("--since", help="run start (ISO time): only events after it count, and Codex "
                    "rollouts active in --worktrees since then are added")
    ap.add_argument("--until", help="ISO time; default now")
    ap.add_argument("--worktrees", nargs="*", default=[], help="checkouts the run used; default --repo")
    ap.add_argument("--gate-only", action="store_true")
    a = ap.parse_args()
    start = ts(a.since) if a.since else None
    end = ts(a.until) if a.until else time.time()
    codex = [os.path.realpath(resolve_codex(x)) for x in a.codex]
    if start:
        # A rollout counts when it was active during the run, even if it began earlier.
        roots = [os.path.realpath(w) for w in (a.worktrees or [a.repo])]
        for f in glob.glob(os.path.join(HOME, ".codex/sessions/*/*/*/rollout-*.jsonl")):
            if os.path.getmtime(f) < start:
                continue
            with open(f, errors="ignore") as fh:
                meta = json.loads(fh.readline() or "{}")
            cwd = os.path.realpath((meta.get("payload") or {}).get("cwd", "/nonexistent"))
            if (ts(meta.get("timestamp")) or 0) <= end and any(
                    cwd == r or cwd.startswith(r + os.sep) for r in roots):
                codex.append(os.path.realpath(f))

    transcripts, seen = [], set()
    def add(path, loader, *args):
        rp = os.path.realpath(path)
        if rp not in seen:
            seen.add(rp)
            transcripts.append(loader(rp, *args))
    for p in a.claude:
        add(p, load_claude, "claude:" + os.path.basename(p)[:8])
        for sub in glob.glob(os.path.join(p[:-6], "subagents", "*.jsonl")):
            add(sub, load_claude, "sub:" + os.path.basename(sub)[:14])
    for f in codex:
        add(f, load_codex)
    if start:
        # A long session can hold earlier work; only the run's own events count.
        for E in transcripts:
            E.ev = [e for e in E.ev if e[0] is not None and start <= e[0] <= end]

    incidents, calls, gaps, pain, compactions, tokens = [], 0, [], [], 0, 0.0
    for E in transcripts:
        inc, n, g = analyse(E)
        incidents += inc; calls += n; gaps += g
        compactions += sum(1 for (_, k, _) in E.ev if k == "compact")
        pain += [d for (_, k, d) in E.ev if k == "pain"]
        tokens += sum(d for (_, k, d) in E.ev if k == "tokens")

    # Successful commands run many times are script candidates.
    plain = QUERY_TOOLS | {"git status", "git log", "cat", "sed -n", "ls", "head", "tail", "echo"}
    ok = defaultdict(lambda: [0, set()])
    for E in transcripts:
        for (_, k, d) in E.ev:
            if k == "call" and not d[2]:
                key = cmd_key(d[0], d[1])
                verb = key.split(":", 1)[-1]
                if ":" in key and not any(verb == q or verb.startswith(q + " ") for q in plain):
                    key = scrub(key, 120)
                    ok[key][0] += 1
                    ok[key][1].add(E.agent)
    repeats = sorted(({"key": k, "count": c, "agents": len(ag)} for k, (c, ag) in ok.items() if c >= 8),
                     key=lambda r: -r["count"])[:10]

    groups = defaultdict(list)
    for x in incidents:
        groups[(x["key"], x["err"])].append(x)
    sigs = []
    for (key, err), xs in groups.items():
        agents = {x["agent"] for x in xs}
        if len(xs) < 2 and not xs[0]["script_class"]:
            continue
        t, s = [x["tokens"] for x in xs], [x["seconds"] for x in xs]
        sigs.append({"key": scrub(key, 120), "error": err, "count": len(xs), "agents": len(agents),
                     "script_class": any(x["script_class"] for x in xs),
                     "tokens_median": round(statistics.median(t)), "tokens_p25": round(pct(t, .25)),
                     "tokens_p75": round(pct(t, .75)), "minutes_median": round(statistics.median(s) / 60, 1),
                     "sample_cmd": xs[0]["sample_cmd"], "sample_err": xs[0]["sample_err"],
                     "needle": next((x["needle"] for x in xs if x["needle"]), None),
                     "where": [x["where"] for x in xs[:3]],
                     "incidents": [{"session": x["where"]["file"], "line": x["where"]["line"], "at": x["at"],
                                    "tokens": round(x["tokens"]), "minutes": round(x["seconds"] / 60, 1)}
                                   for x in xs[:50]]})
    sigs.sort(key=lambda x: x["count"] * x["tokens_median"], reverse=True)
    for i, s in enumerate(sigs, 1):
        s["id"] = f"S{i}"

    failed = len(incidents)
    recovery = sum(x["tokens"] for x in incidents)
    reasons = []
    if sum(1 for s in sigs if s["count"] >= 2) >= 2:
        reasons.append("two or more error signatures repeat")
    if calls and failed / calls > 0.05:
        reasons.append(f"{failed}/{calls} tool calls failed")
    if tokens and recovery / tokens > 0.10:
        reasons.append(f"recovery spans hold {recovery / tokens:.0%} of weighted tokens")
    if any(s["script_class"] for s in sigs):
        reasons.append("a command, recipe, or flag did not exist")
    disk_full = sum(1 for x in incidents if x["disk_full"])
    if disk_full:
        reasons.append(f"the disk filled ({disk_full} failed calls)")
    if len(pain) >= 3:
        reasons.append(f"{len(pain)} user corrections or prods")
    if gaps:
        reasons.append(f"{len(gaps)} gaps over {STALL_S // 60} minutes")
    if compactions:
        reasons.append(f"{compactions} context compactions")
    if calls < 50 and not disk_full and not any(s["script_class"] for s in sigs):
        reasons = []

    out = {"transcripts": len(transcripts), "tool_calls": calls, "failed_calls": failed,
           "weighted_tokens": round(tokens), "recovery_tokens": round(recovery),
           "compactions": compactions, "user_prods": len(pain), "disk_full_calls": disk_full,
           "stalls": gaps[:20],
           "gate": {"recommend": bool(reasons), "reasons": reasons}}
    if not a.gate_only:
        top = sigs[:15]
        hits, nfiles = history_hits([s["needle"] for s in top], a.repo, a.history_days,
                                    {os.path.realpath(E.path) for E in transcripts})
        for s in top:
            s["history_sessions"] = hits.get(s.pop("needle"))
            h = s["history_sessions"]
            s["history_rate_30d"] = round(h / a.history_days * 30, 1) if isinstance(h, int) else None
        out.update({"history_files_searched": nfiles, "history_days": a.history_days,
                    "signatures": top, "repeats": repeats, "prod_samples": pain[:10]})
    json.dump(out, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
