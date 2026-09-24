#!/usr/bin/env python3
"""Tests for scripts/retro-mine.py and scripts/retro-ledger.py on synthetic transcripts."""
import json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
MINE = os.path.join(HERE, "..", "scripts", "retro-mine.py")
LEDGER = os.path.join(HERE, "..", "scripts", "retro-ledger.py")
fails = 0


def check(name, want, got):
    global fails
    ok = want == got
    fails += not ok
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": want {want!r}, got {got!r}"))


def ts(sec):
    return f"2026-09-20T10:{sec // 60:02d}:{sec % 60:02d}Z"


def claude_file(path, events):
    """events: (sec, kind, payload). kinds: bash (cmd, output, is_error), usage (msg_id, tokens)."""
    lines, n = [], 0
    for sec, kind, p in events:
        if kind == "compact":
            lines.append({"type": "system", "subtype": "compact_boundary", "timestamp": ts(sec)})
        elif kind == "usage":
            lines.append({"type": "assistant", "timestamp": ts(sec),
                          "message": {"id": p[0], "content": [], "usage": {"input_tokens": p[1]}}})
        elif kind == "bash":
            n += 1
            lines.append({"type": "assistant", "timestamp": ts(sec), "message": {
                "id": f"call{n}", "content": [{"type": "tool_use", "id": f"t{n}", "name": "Bash",
                                                "input": {"command": p[0]}}]}})
            lines.append({"type": "user", "timestamp": ts(sec), "message": {"content": [
                {"type": "tool_result", "tool_use_id": f"t{n}", "content": p[1], "is_error": p[2]}]}})
    with open(path, "w") as fh:
        fh.write("\n".join(json.dumps(x) for x in lines) + "\n")


def codex_file(path, cwd, sec0, events):
    lines = [{"timestamp": ts(sec0), "type": "session_meta", "payload": {"cwd": cwd}}]
    for sec, kind, p in events:
        if kind == "total":
            lines.append({"timestamp": ts(sec), "type": "event_msg",
                          "payload": {"type": "token_count", "info": {"total_token_usage": {"input_tokens": p}}}})
    with open(path, "w") as fh:
        fh.write("\n".join(json.dumps(x) for x in lines) + "\n")


def mine(home, *args):
    env = {**os.environ, "HOME": home}
    out = subprocess.run([sys.executable, MINE, "--history-days", "1", *args],
                         capture_output=True, text=True, env=env, check=True).stdout
    return json.loads(out)


with tempfile.TemporaryDirectory() as home:
    repo = os.path.join(home, "repo")
    os.makedirs(repo)

    # Secrets: a URL credential in the command and a private key body in the output.
    key = "-----BEGIN RSA PRIVATE KEY-----\nMIIEsecretbody\n-----END RSA PRIVATE KEY-----"
    c1 = os.path.join(home, "c1.jsonl")
    claude_file(c1, [(0, "bash", ("git clone https://bob:hunter2pass@example.com/r.git", f"error: {key}", True)),
                     (5, "bash", ("git clone https://bob:hunter2pass@example.com/r.git", f"error: {key}", True))])
    text = json.dumps(mine(home, "--repo", repo, "--claude", c1))
    check("URL credentials never reach the output", False, "hunter2pass" in text)
    check("private key bodies never reach the output", False, "MIIEsecretbody" in text)

    # Usage repeated on several lines of one message counts once.
    c2 = os.path.join(home, "c2.jsonl")
    claude_file(c2, [(0, "usage", ("m1", 100)), (1, "usage", ("m1", 100)), (2, "usage", ("m2", 50))])
    check("repeated usage of one message counts once", 150, mine(home, "--repo", repo, "--claude", c2)["weighted_tokens"])

    # Retries: two failures then a success. Spans must not overlap.
    c3 = os.path.join(home, "c3.jsonl")
    claude_file(c3, [(0, "bash", ("just test", "error: test run failed", True)), (0, "usage", ("u1", 100)),
                     (2, "bash", ("just test", "error: test run failed", True)), (2, "usage", ("u2", 100)),
                     (4, "bash", ("just test", "ok", False))])
    r = mine(home, "--repo", repo, "--claude", c3)
    sig = r["signatures"][0]
    total = sum(i["tokens"] for i in sig["incidents"])
    check("retry spans do not overlap (tokens)", True, total <= 200 + 2 * len("error: test run failed") / 4 + 1)
    check("retry spans do not overlap (recovery total)", True, r["recovery_tokens"] <= r["weighted_tokens"] + 20)

    # A Codex rollout named by thread ID and also found by --since is read once.
    day = os.path.join(home, ".codex", "sessions", "2026", "09", "20")
    os.makedirs(day)
    rollout = os.path.join(day, "rollout-2026-09-20T10-00-00-thread-abc.jsonl")
    codex_file(rollout, repo, 0, [(10, "total", 1000), (11, "total", 1000), (20, "total", 1500)])
    r = mine(home, "--repo", repo, "--codex", "thread-abc", "--since", ts(0), "--worktrees", repo)
    check("a rollout named twice is read once", 1, r["transcripts"])
    check("repeated cumulative token snapshots count once", 1500, r["weighted_tokens"])

    # Only events inside the run window count.
    r = mine(home, "--repo", repo, "--codex", "thread-abc", "--since", ts(15), "--worktrees", repo)
    check("events before --since are ignored", 500, r["weighted_tokens"])

    # The gate is advisory.
    check("the gate recommends, it does not decide", True, "recommend" in r["gate"])

    # Ledger: evidence dedupe, carrying cost, and fixed groups stay visible.
    env = {**os.environ, "RETRO_LEDGER": os.path.join(home, "ledger.jsonl")}
    ev = [{"session": "s1", "line": 1, "at": "2026-09-01T00:00:00", "tokens": 1000, "minutes": 2},
          {"session": "s2", "line": 5, "at": "2026-09-20T00:00:00", "tokens": 3000, "minutes": 4}]
    rec = {"repo": "r", "kind": "agents-md", "target": "AGENTS.md", "title": "t", "evidence": ev,
           "carrying_tokens_30d": 999999}
    src = os.path.join(home, "p.jsonl")
    with open(src, "w") as fh:
        fh.write(json.dumps(rec) + "\n" + json.dumps({**rec, "evidence": ev[:1]}) + "\n")
    ids = subprocess.run([sys.executable, LEDGER, "add", src], env=env, capture_output=True, text=True,
                         check=True).stdout.split()
    agg = json.loads(subprocess.run([sys.executable, LEDGER, "aggregate", "--repo", "r"], env=env,
                                    capture_output=True, text=True, check=True).stdout)
    check("two proposals stay two groups unless grouped", 2, len(agg))
    subprocess.run([sys.executable, LEDGER, "set", ids[1], f"group={ids[0]}"], env=env, check=True)
    agg = json.loads(subprocess.run([sys.executable, LEDGER, "aggregate", "--repo", "r"], env=env,
                                    capture_output=True, text=True, check=True).stdout)
    check("shared evidence is counted once", 2, agg[0]["occurrences"])
    check("carrying cost can make a rule a net loss", True, agg[0]["tokens_saved_30d"] < 0)
    check("ranges are reported", True, agg[0]["tokens_saved_30d_range"][0] <= agg[0]["tokens_saved_30d_range"][1])
    subprocess.run([sys.executable, LEDGER, "set", ids[0], "status=fixed", "merged_at=2026-09-10T00:00:00"],
                   env=env, check=True)
    subprocess.run([sys.executable, LEDGER, "set", ids[1], "status=fixed", "merged_at=2026-09-10T00:00:00"],
                   env=env, check=True)
    listed = json.loads(subprocess.run([sys.executable, LEDGER, "list", "--repo", "r", "--open"], env=env,
                                       capture_output=True, text=True, check=True).stdout)
    check("fixed groups stay visible to the analysis", 2, len(listed))
    agg = json.loads(subprocess.run([sys.executable, LEDGER, "aggregate", "--repo", "r"], env=env,
                                    capture_output=True, text=True, check=True).stdout)
    check("evidence after the merge date marks the fix ineffective", True, agg[0]["fix_ineffective"])

    # A stall after a command with credentials does not leak them.
    c4 = os.path.join(home, "c4.jsonl")
    claude_file(c4, [(0, "bash", ("curl https://alice:s3cretpw@example.test", "ok", False)),
                     (2000, "bash", ("echo hi", "hi", False))])
    check("stall summaries are scrubbed", False, "s3cretpw" in json.dumps(mine(home, "--repo", repo, "--claude", c4)))

    # Recovery time runs to the next failure's timestamp.
    c5 = os.path.join(home, "c5.jsonl")
    claude_file(c5, [(0, "bash", ("just test", "error: test run failed", True)), (10, "usage", ("v1", 1)),
                     (60, "bash", ("just test", "error: test run failed", True)), (70, "usage", ("v2", 1)),
                     (120, "bash", ("just test", "ok", False))])
    inc = mine(home, "--repo", repo, "--claude", c5)["signatures"][0]["incidents"]
    check("recovery time covers the whole retry sequence", 2.0, round(sum(i["minutes"] for i in inc), 1))
    check("incident times carry a time zone", True, inc[0]["at"].endswith("+00:00"))

    # A compaction before the run window does not count.
    c6 = os.path.join(home, "c6.jsonl")
    claude_file(c6, [(0, "compact", None), (100, "bash", ("echo hi", "hi", False))])
    check("compactions outside the run window are ignored", 0,
          mine(home, "--repo", repo, "--claude", c6, "--since", ts(50))["compactions"])

    # The ledger uses the history rate and compares instants, not strings.
    rec2 = {"repo": "r2", "kind": "script", "target": "justfile", "title": "t2", "history_rate_30d": 30,
            "evidence": [{"session": "s9", "line": 1, "at": "2026-09-20T07:30:00-07:00", "tokens": 1000, "minutes": 1}]}
    src2 = os.path.join(home, "p2.jsonl")
    with open(src2, "w") as fh:
        fh.write(json.dumps(rec2) + "\n")
    rid = subprocess.run([sys.executable, LEDGER, "add", src2], env=env, capture_output=True, text=True,
                         check=True).stdout.split()[0]
    agg = json.loads(subprocess.run([sys.executable, LEDGER, "aggregate", "--repo", "r2"], env=env,
                                    capture_output=True, text=True, check=True).stdout)
    check("the history rate drives the forecast", 27000, agg[0]["tokens_saved_30d"])
    subprocess.run([sys.executable, LEDGER, "set", rid, "status=fixed", "merged_at=2026-09-20T14:00:00Z"],
                   env=env, check=True)
    agg = json.loads(subprocess.run([sys.executable, LEDGER, "aggregate", "--repo", "r2"], env=env,
                                    capture_output=True, text=True, check=True).stdout)
    check("recurrence compares instants across time zones", True, agg[0]["fix_ineffective"])

    # A full disk opens the gate by itself, even in a short run.
    c7 = os.path.join(home, "c7.jsonl")
    claude_file(c7, [(0, "bash", ("cargo build", "error: failed to write: No space left on device (os error 28)", True))])
    gate = mine(home, "--repo", repo, "--claude", c7, "--gate-only")["gate"]
    check("a full disk is a gate reason", True, any("disk filled" in x for x in gate["reasons"]))

print("all passed" if not fails else f"{fails} failed")
sys.exit(1 if fails else 0)
