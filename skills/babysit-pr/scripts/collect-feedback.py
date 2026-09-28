#!/usr/bin/env python3
"""Collect the open review feedback of one or more PRs. Read-only.

  collect-feedback.py --out DIR [--marker TEXT] OWNER/REPO PR [PR ...]

For each PR, the script writes DIR/pr-<n>.json and prints one index line,
then one line for each item that needs attention:

  PR <n> head=<sha9> threads=<open> needs_reply=<n> reviews=<n> comments=<n> checks_failing=<n> checks_pending=<n> COMPLETE
    thread <id> <path>:<line> last=<author> <time> <url>
    review <id> <author> <state> <url>
    comment <id> <author> <url>
    check <name> <conclusion>: <title> <url>

Rules:
- A thread counts only while it is unresolved. It needs a reply when its last
  comment does not start with the marker (default "🤖"). A later comment from
  anyone, a review bot included, reopens a thread that we answered. Thread IDs
  from earlier rounds never mark a thread as handled.
- Review bodies: every review body on the current head commit that has text
  outside HTML comments.
- Conversation comments: every comment created after the head commit, except
  comments that start with the marker.
- Check runs: every check run on the current head whose conclusion is not
  success or skipped, with its output title, summary, and text. Runs that are
  not complete are counted as pending. A run that a later run of the same name
  on the same head supersedes is ignored.
- Every page of every list is read. On an API error or a missing page the PR
  line ends with INCOMPLETE, it shows no counts, and the script exits 2.

Exit status: 0 when every PR is complete, 2 when any PR is INCOMPLETE,
1 for a usage error.
"""
import argparse
import json
import os
import re
import subprocess
import sys

FAILING = {"failure", "timed_out", "action_required", "cancelled", "startup_failure", "stale", "neutral"}

THREADS = """
query($owner:String!,$name:String!,$pr:Int!,$cursor:String){
  repository(owner:$owner,name:$name){pullRequest(number:$pr){
    reviewThreads(first:50,after:$cursor){
      pageInfo{hasNextPage endCursor}
      nodes{id isResolved isOutdated path line originalLine
        comments(last:100){totalCount pageInfo{hasPreviousPage startCursor}
          nodes{id url author{login} createdAt body}}}}}}}
"""

THREAD_COMMENTS = """
query($id:ID!,$cursor:String){node(id:$id){... on PullRequestReviewThread{
  comments(last:100,before:$cursor){pageInfo{hasPreviousPage startCursor}
    nodes{id url author{login} createdAt body}}}}}
"""

HEAD = """
query($owner:String!,$name:String!,$pr:Int!){
  repository(owner:$owner,name:$name){pullRequest(number:$pr){
    number url state headRefName headRefOid baseRefName mergeable
    commits(last:1){nodes{commit{oid committedDate}}}}}}
"""

REVIEWS = """
query($owner:String!,$name:String!,$pr:Int!,$cursor:String){
  repository(owner:$owner,name:$name){pullRequest(number:$pr){
    reviews(first:100,after:$cursor){pageInfo{hasNextPage endCursor}
      nodes{id url author{login} state submittedAt body commit{oid}}}}}}
"""

COMMENTS = """
query($owner:String!,$name:String!,$pr:Int!,$cursor:String){
  repository(owner:$owner,name:$name){pullRequest(number:$pr){
    comments(first:100,after:$cursor){pageInfo{hasNextPage endCursor}
      nodes{id url author{login} createdAt body}}}}}
"""


class Incomplete(Exception):
    pass


def gh(args):
    try:
        run = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise Incomplete(f"gh {args[0]} {args[1] if len(args) > 1 else ''}: {error}")
    if run.returncode != 0:
        first = (run.stderr.strip() or run.stdout.strip() or "no output").splitlines()[0]
        raise Incomplete(f"gh exited {run.returncode}: {first}")
    try:
        return json.loads(run.stdout)
    except ValueError:
        raise Incomplete("gh returned no JSON")


def graphql(query, **variables):
    args = ["api", "graphql", "-f", "query=" + query]
    for key, value in variables.items():
        if value is None:
            continue
        args += ["-F" if isinstance(value, int) else "-f", f"{key}={value}"]
    data = gh(args)
    if data.get("errors"):
        raise Incomplete("GraphQL: " + data["errors"][0].get("message", "error"))
    if not isinstance(data.get("data"), dict):
        raise Incomplete("GraphQL response has no data")
    return data["data"]


def pull(data):
    pr = (data.get("repository") or {}).get("pullRequest")
    if pr is None:
        raise Incomplete("pull request not found")
    return pr


def pages(query, key, owner, name, number):
    """Every node of a forward-paginated connection on the pull request."""
    nodes, cursor = [], None
    while True:
        conn = pull(graphql(query, owner=owner, name=name, pr=number, cursor=cursor)).get(key)
        if not conn or conn.get("nodes") is None or "pageInfo" not in conn:
            raise Incomplete(f"{key}: page has no nodes")
        nodes += conn["nodes"]
        if not conn["pageInfo"].get("hasNextPage"):
            return nodes
        cursor = conn["pageInfo"].get("endCursor")
        if not cursor:
            raise Incomplete(f"{key}: next page has no cursor")


def thread_comments(thread):
    """All comments of a thread, oldest first."""
    conn = thread["comments"]
    comments = list(conn["nodes"])
    info = conn["pageInfo"]
    while info.get("hasPreviousPage"):
        if not info.get("startCursor"):
            raise Incomplete(f"thread {thread['id']}: earlier page has no cursor")
        node = graphql(THREAD_COMMENTS, id=thread["id"], cursor=info["startCursor"]).get("node")
        if not node or not node.get("comments"):
            raise Incomplete(f"thread {thread['id']}: comment page missing")
        comments = node["comments"]["nodes"] + comments
        info = node["comments"]["pageInfo"]
    if len(comments) != conn["totalCount"]:
        raise Incomplete(f"thread {thread['id']}: {len(comments)} of {conn['totalCount']} comments read")
    return comments


def check_runs(repo, sha):
    runs, page = [], 1
    while True:
        data = gh(["api", f"repos/{repo}/commits/{sha}/check-runs?per_page=100&page={page}"])
        batch = data.get("check_runs")
        total = data.get("total_count")
        if batch is None or total is None:
            raise Incomplete("check runs: page has no check_runs")
        runs += batch
        if len(runs) >= total:
            return runs
        if not batch:
            raise Incomplete(f"check runs: {len(runs)} of {total} read")
        page += 1


def visible(body):
    """True when the body has text outside HTML comments."""
    return bool(re.sub(r"<!--.*?-->", "", body, flags=re.S).strip())


def login(item):
    return (item.get("author") or {}).get("login") or "ghost"


def collect(repo, number, marker):
    owner, name = repo.split("/", 1)
    pr = pull(graphql(HEAD, owner=owner, name=name, pr=number))
    head = pr["headRefOid"]
    commits = pr["commits"]["nodes"]
    since = commits[0]["commit"]["committedDate"] if commits else ""

    threads = []
    for thread in pages(THREADS, "reviewThreads", owner, name, number):
        if thread["isResolved"]:
            continue
        comments = thread_comments(thread)
        last = comments[-1] if comments else {}
        threads.append({
            "id": thread["id"],
            "path": thread["path"],
            "line": thread["line"] or thread["originalLine"],
            "outdated": thread["isOutdated"],
            "url": comments[0]["url"] if comments else "",
            "last_author": login(last),
            "last_at": last.get("createdAt", ""),
            "needs_reply": not last.get("body", "").lstrip().startswith(marker),
            "comments": [
                {"id": c["id"], "author": login(c), "at": c["createdAt"], "url": c["url"], "body": c["body"]}
                for c in comments
            ],
        })

    reviews = [
        {"id": r["id"], "author": login(r), "state": r["state"], "at": r["submittedAt"],
         "url": r["url"], "body": r["body"]}
        for r in pages(REVIEWS, "reviews", owner, name, number)
        if (r.get("commit") or {}).get("oid") == head and visible(r["body"])
        and not r["body"].lstrip().startswith(marker)
    ]
    conversation = [
        {"id": c["id"], "author": login(c), "at": c["createdAt"], "url": c["url"], "body": c["body"]}
        for c in pages(COMMENTS, "comments", owner, name, number)
        if c["createdAt"] > since and not c["body"].lstrip().startswith(marker)
    ]

    runs = check_runs(repo, head)
    # A rerun or a new workflow run supersedes an earlier run of the same name.
    latest = {}
    for run in runs:
        latest[run["name"]] = max(latest.get(run["name"], ""), run.get("started_at") or "")
    checks, pending = [], 0
    for run in runs:
        if (run.get("started_at") or "") < latest[run["name"]]:
            continue
        if run.get("status") != "completed":
            pending += 1
        elif run.get("conclusion") in FAILING:
            output = run.get("output") or {}
            checks.append({
                "id": run["id"], "name": run["name"], "conclusion": run["conclusion"],
                "url": run.get("html_url", ""), "title": output.get("title") or "",
                "summary": output.get("summary") or "", "text": output.get("text") or "",
            })

    return {
        "pr": number, "url": pr["url"], "state": pr["state"], "branch": pr["headRefName"],
        "base": pr["baseRefName"], "head": head, "head_committed_at": since,
        "mergeable": pr["mergeable"], "marker": marker, "complete": True,
        "threads": threads, "reviews": reviews, "comments": conversation,
        "checks": checks, "checks_pending": pending,
    }


def one_line(text, limit=100):
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def report(result):
    open_threads = result["threads"]
    reply = [t for t in open_threads if t["needs_reply"]]
    print(
        f"PR {result['pr']} head={result['head'][:9]} threads={len(open_threads)} "
        f"needs_reply={len(reply)} reviews={len(result['reviews'])} "
        f"comments={len(result['comments'])} checks_failing={len(result['checks'])} "
        f"checks_pending={result['checks_pending']} COMPLETE"
    )
    for t in reply:
        print(f"  thread {t['id']} {t['path']}:{t['line']} last={t['last_author']} {t['last_at']} {t['url']}")
    for r in result["reviews"]:
        print(f"  review {r['id']} {r['author']} {r['state']} {r['url']}")
    for c in result["comments"]:
        print(f"  comment {c['id']} {c['author']} {c['url']}")
    for c in result["checks"]:
        print(f"  check {c['name']} {c['conclusion']}: {one_line(c['title'])} {c['url']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", required=True, help="directory for pr-<n>.json files")
    parser.add_argument("--marker", default="🤖", help="prefix of our own replies (default: 🤖)")
    parser.add_argument("repo", help="OWNER/REPO")
    parser.add_argument("prs", nargs="+", type=int, metavar="PR")
    args = parser.parse_args()
    if "/" not in args.repo:
        parser.error("repo must be OWNER/REPO")
    os.makedirs(args.out, exist_ok=True)

    incomplete = False
    for number in args.prs:
        path = os.path.join(args.out, f"pr-{number}.json")
        try:
            result = collect(args.repo, number, args.marker)
        except Incomplete as error:
            incomplete = True
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"pr": number, "complete": False, "error": str(error)}, fh, indent=1)
            print(f"PR {number} INCOMPLETE: {error}")
            continue
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=1, ensure_ascii=False)
        report(result)
    print(f"files: {os.path.abspath(args.out)}")
    return 2 if incomplete else 0


if __name__ == "__main__":
    sys.exit(main())
