#!/usr/bin/env python3
"""Tests for scripts/collect-feedback.py and scripts/post-replies.py with a fake gh."""
import json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
COLLECT = os.path.join(HERE, "..", "scripts", "collect-feedback.py")
POST = os.path.join(HERE, "..", "scripts", "post-replies.py")
fails = 0

# The fake gh answers with the first rule whose substrings all occur in its
# joined arguments, and logs each call.
FAKE_GH = r'''#!/usr/bin/env python3
import json, os, sys
args = " ".join(sys.argv[1:])
with open(os.environ["FAKE_GH_LOG"], "a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\n")
for rule in json.load(open(os.environ["FAKE_GH_RULES"])):
    if all(s in args for s in rule["match"]):
        out = rule.get("stdout")
        if out is not None:
            print(json.dumps(out))
        if rule.get("stderr"):
            print(rule["stderr"], file=sys.stderr)
        sys.exit(rule.get("exit", 0))
print("fake gh: no rule for " + args, file=sys.stderr)
sys.exit(9)
'''


def check(name, want, got):
    global fails
    ok = want == got
    fails += not ok
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": want {want!r}, got {got!r}"))


def run(tmp, script, rules, *args, cwd=None):
    bindir = os.path.join(tmp, "bin")
    os.makedirs(bindir, exist_ok=True)
    gh = os.path.join(bindir, "gh")
    with open(gh, "w") as fh:
        fh.write(FAKE_GH)
    os.chmod(gh, 0o755)
    rules_path = os.path.join(tmp, "rules.json")
    log_path = os.path.join(tmp, "gh.log")
    with open(rules_path, "w") as fh:
        json.dump(rules, fh)
    open(log_path, "w").close()
    env = {**os.environ, "PATH": bindir + os.pathsep + os.environ["PATH"],
           "FAKE_GH_RULES": rules_path, "FAKE_GH_LOG": log_path}
    proc = subprocess.run([sys.executable, script, *args], capture_output=True, text=True,
                          env=env, cwd=cwd or tmp)
    calls = [json.loads(line) for line in open(log_path)]
    return proc.returncode, proc.stdout, calls


# ---------- collect-feedback.py ----------

def comment(cid, author, body, at="2026-09-28T10:00:00Z"):
    return {"id": cid, "url": f"https://example.test/{cid}", "author": {"login": author},
            "createdAt": at, "body": body}


def thread(tid, comments, resolved=False, earlier=False):
    return {"id": tid, "isResolved": resolved, "isOutdated": False, "path": "src/a.rs", "line": 7,
            "originalLine": 7, "comments": {
                "totalCount": len(comments) + (1 if earlier else 0),
                "pageInfo": {"hasPreviousPage": earlier, "startCursor": "c-" + tid if earlier else None},
                "nodes": comments}}


def pr_data(key, nodes, next_cursor=None):
    return {"data": {"repository": {"pullRequest": {key: {
        "pageInfo": {"hasNextPage": next_cursor is not None, "endCursor": next_cursor},
        "nodes": nodes}}}}}


HEAD_SHA = "a" * 40
HEAD_RULE = {"match": ["headRefOid baseRefName mergeable"], "stdout": {"data": {"repository": {"pullRequest": {
    "number": 7, "url": "https://example.test/pull/7", "state": "OPEN", "headRefName": "topic",
    "headRefOid": HEAD_SHA, "baseRefName": "main", "mergeable": "MERGEABLE",
    "commits": {"nodes": [{"commit": {"oid": HEAD_SHA, "committedDate": "2026-09-28T09:00:00Z"}}]}}}}}}

THREAD_PAGE_2 = {"match": ["reviewThreads(", "cursor=t2"], "stdout": pr_data("reviewThreads", [
    thread("T-bot-after-us", [comment("c1", "bot[bot]", "Finding"), comment("c2", "me", "🤖 Fixed"),
                              comment("c3", "macroscopeapp", "Still broken")]),
    thread("T-long", [comment("c5", "me", "🤖 Not a defect."), comment("c6", "reviewer", "Why?")], earlier=True),
])}
THREAD_PAGE_1 = {"match": ["reviewThreads("], "stdout": pr_data("reviewThreads", [
    thread("T-answered", [comment("c7", "macroscopeapp", "Finding"), comment("c8", "me", "🤖 Fixed in abc1234.")]),
    thread("T-resolved", [comment("c9", "reviewer", "Nit")], resolved=True),
], next_cursor="t2")}
EARLIER_COMMENTS = {"match": ["comments(last:100,before:$cursor)", "cursor=c-T-long"], "stdout": {"data": {"node": {
    "comments": {"pageInfo": {"hasPreviousPage": False, "startCursor": None},
                 "nodes": [comment("c4", "reviewer", "First finding")]}}}}}
REVIEWS = {"match": ["reviews(first:100"], "stdout": pr_data("reviews", [
    {"id": "R-old", "url": "u1", "author": {"login": "x"}, "state": "COMMENTED", "submittedAt": "t",
     "body": "Old head", "commit": {"oid": "b" * 40}},
    {"id": "R-head", "url": "u2", "author": {"login": "x"}, "state": "CHANGES_REQUESTED", "submittedAt": "t",
     "body": "Please fix the lock.", "commit": {"oid": HEAD_SHA}},
    {"id": "R-empty", "url": "u3", "author": {"login": "x"}, "state": "COMMENTED", "submittedAt": "t",
     "body": "", "commit": {"oid": HEAD_SHA}},
    {"id": "R-marker", "url": "u4", "author": {"login": "bot"}, "state": "APPROVED", "submittedAt": "t",
     "body": "<!-- review marker -->\n<!-- meta: {} -->", "commit": {"oid": HEAD_SHA}},
])}
COMMENTS = {"match": ["comments(first:100"], "stdout": pr_data("comments", [
    comment("IC-before", "bot", "Before the push", at="2026-09-28T08:00:00Z"),
    comment("IC-after", "bot", "After the push", at="2026-09-28T09:30:00Z"),
    comment("IC-ours", "me", "🤖 Answered", at="2026-09-28T09:40:00Z"),
])}


def run_check(name, conclusion, started, status="completed", title=""):
    return {"id": hash((name, started)) & 0xFFFF, "name": name, "status": status, "conclusion": conclusion,
            "started_at": started, "html_url": "https://example.test/run/" + name,
            "output": {"title": title, "summary": "summary of " + name, "text": "details"}}


CHECKS_1 = {"match": ["check-runs", "page=1"], "stdout": {"total_count": 4, "check_runs": [
    run_check("build", "cancelled", "2026-09-28T09:01:00Z"),
    run_check("build", "success", "2026-09-28T09:05:00Z"),
    run_check("Security", "failure", "2026-09-28T09:02:00Z", title="Security: 1 blocker"),
]}}
CHECKS_2 = {"match": ["check-runs", "page=2"], "stdout": {"total_count": 4, "check_runs": [
    run_check("tests", None, "2026-09-28T09:03:00Z", status="in_progress"),
]}}
GOOD = [HEAD_RULE, THREAD_PAGE_2, EARLIER_COMMENTS, THREAD_PAGE_1, REVIEWS, COMMENTS, CHECKS_2, CHECKS_1]

with tempfile.TemporaryDirectory() as tmp:
    code, out, calls = run(tmp, COLLECT, GOOD, "--out", "fb", "o/r", "7")
    check("collect: exit 0", 0, code)
    line = out.splitlines()[0]
    check("collect: index line", "PR 7 head=aaaaaaaaa threads=3 needs_reply=2 reviews=1 comments=1 "
          "checks_failing=1 checks_pending=1 COMPLETE", line)
    data = json.load(open(os.path.join(tmp, "fb", "pr-7.json")))
    reply = {t["id"]: t["needs_reply"] for t in data["threads"]}
    check("collect: bot reply after our reply reopens the thread", True, reply.get("T-bot-after-us"))
    check("collect: thread whose last comment is ours is handled", False, reply.get("T-answered"))
    check("collect: resolved thread is not listed", False, "T-resolved" in reply)
    check("collect: second thread page is read", True, "T-long" in reply)
    long = next(t for t in data["threads"] if t["id"] == "T-long")
    check("collect: earlier comment page is read", ["c4", "c5", "c6"], [c["id"] for c in long["comments"]])
    check("collect: only head review bodies", ["R-head"], [r["id"] for r in data["reviews"]])
    check("collect: only comments after the push", ["IC-after"], [c["id"] for c in data["comments"]])
    check("collect: superseded run ignored", ["Security"], [c["name"] for c in data["checks"]])
    check("collect: check output kept", "summary of Security", data["checks"][0]["summary"])
    check("collect: thread listed in output", True, any(" thread T-bot-after-us " in l for l in out.splitlines()))
    check("collect: handled thread not in output", False, "T-answered" in out)
    check("collect: read-only (no mutation)", False, any("mutation" in " ".join(c) for c in calls))

with tempfile.TemporaryDirectory() as tmp:
    error = {"match": ["reviewThreads("], "stdout": {"errors": [{"message": "Field 'x' doesn't exist"}]},
             "stderr": "gh: Field 'x' doesn't exist", "exit": 1}
    code, out, _ = run(tmp, COLLECT, [HEAD_RULE, error], "--out", "fb", "o/r", "7")
    check("collect: GraphQL error exits 2", 2, code)
    check("collect: GraphQL error prints INCOMPLETE", True, out.startswith("PR 7 INCOMPLETE"))
    check("collect: GraphQL error prints no counts", False, "threads=" in out)

with tempfile.TemporaryDirectory() as tmp:
    broken = {"match": ["reviewThreads("], "stdout": pr_data("reviewThreads", [], next_cursor=None)}
    broken["stdout"]["data"]["repository"]["pullRequest"]["reviewThreads"]["pageInfo"]["hasNextPage"] = True
    code, out, _ = run(tmp, COLLECT, [HEAD_RULE, broken], "--out", "fb", "o/r", "7")
    check("collect: missing page cursor exits 2", 2, code)

with tempfile.TemporaryDirectory() as tmp:
    short = {"match": ["check-runs", "page=2"], "stdout": {"total_count": 4, "check_runs": []}}
    rules = [HEAD_RULE, THREAD_PAGE_2, EARLIER_COMMENTS, THREAD_PAGE_1, REVIEWS, COMMENTS, short, CHECKS_1]
    code, out, _ = run(tmp, COLLECT, rules, "--out", "fb", "o/r", "7")
    check("collect: short check-run page exits 2", 2, code)


# ---------- post-replies.py ----------

def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True, text=True).stdout.strip()


P1, P2, P3, P4 = "1" * 7 + "f" * 33, "2" * 7 + "e" * 33, "3" * 7 + "d" * 33, "4" * 7 + "c" * 33
PUSHED = {"match": ["compare/main..."], "stdout": {"total_commits": 4, "commits": [
    {"sha": P1, "commit": {"message": "fix: alpha\n\nbody"}},
    {"sha": P2, "commit": {"message": "fix: beta"}},
    {"sha": P3, "commit": {"message": "chore: dup"}},
    {"sha": P4, "commit": {"message": "chore: dup"}},
]}}
PR_HEAD = {"match": ["headRefOid baseRefName}"], "stdout": {"data": {"repository": {"pullRequest": {
    "headRefOid": P4, "baseRefName": "main"}}}}}
REPLY_OK = {"match": ["addPullRequestReviewThreadReply"], "stdout": {"data": {
    "addPullRequestReviewThreadReply": {"comment": {"url": "u"}}}}}
RESOLVE_OK = {"match": ["resolveReviewThread"], "stdout": {"data": {"resolveReviewThread": {"thread": {"isResolved": True}}}}}


def thread_node(tid, pr=7, resolved=False, bodies=()):
    return {"match": ["PullRequestReviewThread{", "id=" + tid], "stdout": {"data": {"node": {
        "__typename": "PullRequestReviewThread", "isResolved": resolved,
        "pullRequest": {"number": pr, "repository": {"nameWithOwner": "o/r"}},
        "comments": {"nodes": [{"body": b} for b in bodies]}}}}}


MISSING = {"match": ["PullRequestReviewThread{", "id=PRRT_missing"], "stdout": {
    "data": {"node": None}, "errors": [{"message": "Could not resolve to a node"}]}, "exit": 1}
BASE_RULES = [REPLY_OK, RESOLVE_OK, PR_HEAD, PUSHED, MISSING,
              thread_node("PRRT_a"), thread_node("PRRT_b"), thread_node("PRRT_other", pr=8),
              thread_node("PRRT_done", resolved=True, bodies=["🤖 Already said."])]


def mutations(calls, name):
    return [c for c in calls if any(name in a for a in c)]


def ids(calls):
    return [a.split("=", 1)[1] for c in calls for a in c if a.startswith("t=")]


with tempfile.TemporaryDirectory() as tmp:
    repo = os.path.join(tmp, "clone")
    os.makedirs(repo)
    git(repo, "init", "-q")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "fix: alpha")
    local = git(repo, "rev-parse", "--short=9", "HEAD")
    replies = os.path.join(tmp, "replies.md")

    def write(*lines):
        with open(replies, "w") as fh:
            fh.write("\n".join(lines) + "\n")

    write("# round 1",
          f"PRRT_a|reply+resolve|🤖 Fixed in {local}. The limit stays 104857600 bytes.",
          "PRRT_b|reply|🤖 Fixed in <sha:fix: beta>; not a defect otherwise.")
    code, out, calls = run(tmp, POST, BASE_RULES, "--git-dir", repo, "o/r", "7", replies)
    check("post dry: exit 0", 0, code)
    check("post dry: local commit mapped by subject", True, f"{local}->{P1[:9]}" in out)
    check("post dry: 9-digit number skipped", True, "skip 104857600 (not a commit)" in out)
    check("post dry: placeholder mapped", True, f"<sha:fix: beta>->{P2[:9]}" in out)
    check("post dry: nothing posted", [], mutations(calls, "mutation"))

    code, out, calls = run(tmp, POST, BASE_RULES, "--git-dir", repo, "--post", "o/r", "7", replies)
    check("post: exit 0", 0, code)
    posted = mutations(calls, "addPullRequestReviewThreadReply")
    check("post: two replies by ID", ["PRRT_a", "PRRT_b"], ids(posted))
    check("post: mapped body posted", True,
          any(a == f"b=🤖 Fixed in {P1[:9]}. The limit stays 104857600 bytes." for c in posted for a in c))
    check("post: only reply+resolve is resolved", ["PRRT_a"], ids(mutations(calls, "resolveReviewThread")))

    write("PRRT_done|resolve|🤖 Already said.")
    code, out, calls = run(tmp, POST, BASE_RULES, "--post", "o/r", "7", replies)
    check("post: an existing body is not posted again", ([], []),
          (mutations(calls, "addPullRequestReviewThreadReply"), mutations(calls, "resolveReviewThread")))

    bad_cases = [
        ("thread of another PR", "PRRT_other|reply|🤖 Fixed.", "is a thread of o/r#8, not #7"),
        ("unknown thread ID", "PRRT_missing|reply|🤖 Fixed.", "PRRT_missing"),
        ("subject with two pushed commits", "PRRT_a|reply|🤖 Fixed in <sha:chore: dup>.", "2 pushed commits"),
        ("subject with no pushed commit", "PRRT_a|reply|🤖 Fixed in <sha:gone>.", "0 pushed commits"),
        ("reply without the marker", "PRRT_a|reply|Fixed.", "does not start with"),
        ("unknown action", "PRRT_a|close|🤖 Fixed.", "unknown action"),
        ("line without an ID", "|reply|🤖 Fixed.", "expected <thread id>"),
    ]
    for label, line, needle in bad_cases:
        write("PRRT_b|reply+resolve|🤖 Fine.", line)
        code, out, calls = run(tmp, POST, BASE_RULES, "--git-dir", repo, "--post", "o/r", "7", replies)
        check(f"post rejects {label}: exit 1", 1, code)
        check(f"post rejects {label}: message", True, needle in out)
        check(f"post rejects {label}: nothing posted", [], mutations(calls, "mutation"))

    write(f"PRRT_a|reply|🤖 Fixed in {local}.")
    code, out, calls = run(tmp, POST, BASE_RULES, "o/r", "7", replies)
    check("post: unpushed commit without --git-dir is an error", (1, True),
          (code, "pass --git-dir" in out))

if fails:
    print(f"{fails} failed")
    sys.exit(1)
print("all passed")
