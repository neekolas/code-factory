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
- Keep review bodies and conversation comments from all heads and dates.
- Only a marker from a --trusted-author identity marks a reply as handled.
- Keep item version keys and optional recorded dispositions in the evidence.
- Save each source with an atomic write. Flush source progress to stdout.
- Keep partial evidence on an API error. Exit 2 means incomplete evidence.
- Recheck the head at the end. A changed head makes the snapshot STALE.

Exit status: 0 complete, 2 incomplete or stale, 1 usage error.
"""
import argparse
import hashlib
import tempfile
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
          nodes{id url author{login} createdAt updatedAt body commit{oid} originalCommit{oid}}}}}}}}
"""

THREAD_COMMENTS = """
query($id:ID!,$cursor:String){node(id:$id){... on PullRequestReviewThread{
  comments(last:100,before:$cursor){pageInfo{hasPreviousPage startCursor}
    nodes{id url author{login} createdAt updatedAt body commit{oid} originalCommit{oid}}}}}}
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
      nodes{id url author{login} state submittedAt updatedAt body commit{oid}}}}}}
"""

COMMENTS = """
query($owner:String!,$name:String!,$pr:Int!,$cursor:String){
  repository(owner:$owner,name:$name){pullRequest(number:$pr){
    comments(first:100,after:$cursor){pageInfo{hasNextPage endCursor}
      nodes{id url author{login} createdAt updatedAt body}}}}}
"""


class Incomplete(Exception):
    pass


def gh(args):
    try:
        run = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise Incomplete("gh call failed or exceeded 60 seconds") from error
    if run.returncode != 0:
        raise Incomplete(f"gh exited {run.returncode}")
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
        raise Incomplete("GraphQL returned an error")
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
    cursor = None
    while True:
        conn = pull(graphql(query, owner=owner, name=name, pr=number, cursor=cursor)).get(key)
        if (not isinstance(conn, dict) or not isinstance(conn.get("nodes"), list)
                or not isinstance((conn.get("pageInfo") or {}).get("hasNextPage"), bool)):
            raise Incomplete(f"{key}: page has no nodes")
        yield from conn["nodes"]
        if not conn["pageInfo"].get("hasNextPage"):
            return
        cursor = conn["pageInfo"].get("endCursor")
        if not cursor:
            raise Incomplete(f"{key}: next page has no cursor")


def thread_comments(thread, publish=None):
    """All comments of a thread, oldest first."""
    conn = thread["comments"]
    comments = list(conn["nodes"])
    info = conn["pageInfo"]
    if not isinstance(info.get("hasPreviousPage"), bool):
        raise Incomplete(f"thread {thread['id']}: comment page has no page state")
    while info.get("hasPreviousPage"):
        if not info.get("startCursor"):
            raise Incomplete(f"thread {thread['id']}: earlier page has no cursor")
        node = graphql(THREAD_COMMENTS, id=thread["id"], cursor=info["startCursor"]).get("node")
        if not node or not node.get("comments"):
            raise Incomplete(f"thread {thread['id']}: comment page missing")
        page = node["comments"]
        if (not isinstance(page.get("nodes"), list)
                or not isinstance((page.get("pageInfo") or {}).get("hasPreviousPage"), bool)):
            raise Incomplete(f"thread {thread['id']}: comment page has no page state")
        comments = page["nodes"] + comments
        info = page["pageInfo"]
        if publish:
            publish(comments)
    if len(comments) != conn["totalCount"]:
        raise Incomplete(f"thread {thread['id']}: {len(comments)} of {conn['totalCount']} comments read")
    return comments


def check_runs(repo, sha):
    count, page = 0, 1
    while True:
        data = gh(["api", f"repos/{repo}/commits/{sha}/check-runs?per_page=100&page={page}"])
        batch = data.get("check_runs")
        total = data.get("total_count")
        if not isinstance(batch, list) or not isinstance(total, int) or total < 0:
            raise Incomplete("check runs: page has no check_runs")
        yield from batch
        count += len(batch)
        if count >= total:
            return
        if not batch:
            raise Incomplete(f"check runs: {count} of {total} read")
        page += 1


def visible(body):
    """True when the body has text outside HTML comments."""
    return bool(re.sub(r"<!--.*?-->", "", body, flags=re.S).strip())


def login(item):
    return (item.get("author") or {}).get("login") or "ghost"


def body_hash(body):
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def evidence(item, at, dispositions):
    body = item.get("body") or ""
    digest = body_hash(body)
    updated = item.get("updatedAt")
    version = f"{item['id']}:{updated or ''}:{digest}"
    return {"id": item["id"], "author": login(item), "at": at,
            "updated_at": updated, "url": item.get("url", ""), "body": body,
            "body_hash": digest, "version_key": version,
            "source_commit": (item.get("commit") or {}).get("oid") or (item.get("originalCommit") or {}).get("oid"),
            "disposition": dispositions.get(version)}


def handled(item, marker, trusted):
    return login(item) in trusted and (item.get("body") or "").lstrip().startswith(marker)


def summarize_runs(runs, head):
    # A replacement is proved only within the same app, suite, and head.
    latest = {}
    def identity(run):
        app = (run.get("app") or {}).get("id")
        suite = (run.get("check_suite") or {}).get("id")
        sha = run.get("head_sha")
        if app is None or suite is None or sha != head or not run.get("started_at"):
            return None
        return (app, suite, sha, run["name"])
    for run in runs:
        key = identity(run)
        if key is not None:
            latest[key] = max(latest.get(key, ""), run["started_at"])
    checks, pending = [], 0
    for run in runs:
        key = identity(run)
        if key is not None and run["started_at"] < latest[key]:
            continue
        if run.get("status") != "completed":
            pending += 1
        elif run.get("conclusion") in FAILING:
            output = run.get("output") or {}
            checks.append({"id": run["id"], "name": run["name"], "conclusion": run["conclusion"],
                           "source_commit": run.get("head_sha"),
                           "app_id": (run.get("app") or {}).get("id"),
                           "suite_id": (run.get("check_suite") or {}).get("id"),
                           "url": run.get("html_url", ""), "title": output.get("title") or "",
                           "summary": output.get("summary") or "", "text": output.get("text") or ""})
    return checks, pending


def collect(repo, number, marker, trusted=(), dispositions=None, publish=None):
    dispositions = dispositions or {}
    owner, name = repo.split("/", 1)
    result = {"pr": number, "head": "", "marker": marker, "complete": False,
              "snapshot_state": "INCOMPLETE", "sources": {}, "errors": [],
              "threads": [], "reviews": [], "comments": [], "check_runs": [],
              "checks": [], "checks_pending": 0}

    def progress(source, complete=False, error=None):
        result["sources"][source] = {"complete": complete, "error": error}
        if error:
            result["errors"].append(f"{source}: {error}")
        if publish:
            publish(result, source)

    try:
        pr = pull(graphql(HEAD, owner=owner, name=name, pr=number))
        head = pr.get("headRefOid")
        if not isinstance(head, str) or not head:
            raise Incomplete("PR head is missing")
        commits = pr["commits"]["nodes"]
        result.update({"url": pr["url"], "state": pr["state"], "branch": pr["headRefName"],
                       "base": pr["baseRefName"], "head": head, "mergeable": pr["mergeable"],
                       "head_committed_at": commits[0]["commit"]["committedDate"] if commits else ""})
    except Incomplete as error:
        progress("head", error=str(error))
        return result
    progress("head", complete=True)

    try:
        for thread in pages(THREADS, "reviewThreads", owner, name, number):
            if thread["isResolved"]:
                continue
            # Keep the fetched page even if an earlier comment page fails.
            partial = [evidence(c, c["createdAt"], dispositions) for c in thread["comments"]["nodes"]]
            last = partial[-1] if partial else {}
            item = {"id": thread["id"], "path": thread["path"],
                    "line": thread["line"] or thread["originalLine"], "outdated": thread["isOutdated"],
                    "url": partial[0]["url"] if partial else "", "last_author": last.get("author", "ghost"),
                    "last_at": last.get("at", ""), "needs_reply": True, "comments": partial,
                    "comments_complete": False, "expected_head": head,
                    "expected_last_comment_id": last.get("id"),
                    "expected_last_comment_updated_at": last.get("updated_at"),
                    "expected_last_comment_hash": last.get("body_hash"), "version_key": last.get("version_key")}
            result["threads"].append(item)
            progress("threads")
            def publish_comments(comments):
                item["comments"] = [evidence(c, c["createdAt"], dispositions) for c in comments]
                progress("threads")
            comments = thread_comments(thread, publish_comments)
            item["comments"] = [evidence(c, c["createdAt"], dispositions) for c in comments]
            item["comments_complete"] = True
            item["url"] = comments[0]["url"] if comments else ""
            item["needs_reply"] = not handled(comments[-1] if comments else {}, marker, trusted)
        progress("threads", complete=True)
    except Incomplete as error:
        progress("threads", error=str(error))

    for source, query, connection in (("reviews", REVIEWS, "reviews"), ("comments", COMMENTS, "comments")):
        try:
            for item in pages(query, connection, owner, name, number):
                if not visible(item["body"]):
                    continue
                record = evidence(item, item.get("submittedAt") or item.get("createdAt"), dispositions)
                record["needs_reply"] = not handled(item, marker, trusted)
                if source == "reviews":
                    record["state"] = item["state"]
                result[source].append(record)
                progress(source)
            progress(source, complete=True)
        except Incomplete as error:
            progress(source, error=str(error))
    try:
        for run in check_runs(repo, head):
            result["check_runs"].append(run)
            result["checks"], result["checks_pending"] = summarize_runs(result["check_runs"], head)
            progress("checks")
        progress("checks", complete=True)
    except Incomplete as error:
        progress("checks", error=str(error))
    try:
        current = pull(graphql(HEAD, owner=owner, name=name, pr=number))["headRefOid"]
        if not isinstance(current, str) or not current:
            raise Incomplete("final PR head is missing")
        result["observed_head"] = current
        if current != head:
            result["snapshot_state"] = "STALE"
            progress("final_head", error="PR head changed during collection")
        else:
            progress("final_head", complete=True)
    except Incomplete as error:
        progress("final_head", error=str(error))
    result["complete"] = all(s["complete"] for s in result["sources"].values())
    if result["complete"]:
        result["snapshot_state"] = "COMPLETE"
    return result


def atomic_write(path, result):
    fd, temporary = tempfile.mkstemp(prefix=".feedback-", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=1, ensure_ascii=False)
            fh.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


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
        f"checks_pending={result['checks_pending']} {result['snapshot_state']}"
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
    parser.add_argument("--trusted-author", action="append", default=[], help="login of our reply author; repeat as needed")
    parser.add_argument("--dispositions", help="JSON object: version_key to recorded disposition")
    parser.add_argument("repo", help="OWNER/REPO")
    parser.add_argument("prs", nargs="+", type=int, metavar="PR")
    args = parser.parse_args()
    if "/" not in args.repo:
        parser.error("repo must be OWNER/REPO")
    os.makedirs(args.out, exist_ok=True)

    dispositions = {}
    if args.dispositions:
        try:
            with open(args.dispositions, encoding="utf-8") as fh:
                dispositions = json.load(fh)
            if not isinstance(dispositions, dict):
                parser.error("dispositions must be a JSON object")
        except (OSError, ValueError):
            parser.error("cannot read dispositions as JSON")
    incomplete = False
    for number in args.prs:
        path = os.path.join(args.out, f"pr-{number}.json")
        def publish(result, source):
            atomic_write(path, result)
            status = result["sources"][source]
            state = "READY" if status["complete"] else ("INCOMPLETE" if status["error"] else "PARTIAL")
            print(f"SOURCE PR {number} {source} {state} file={path}", flush=True)
        result = collect(args.repo, number, args.marker, args.trusted_author, dispositions, publish)
        incomplete |= not result["complete"]
        atomic_write(path, result)
        report(result)
        for error in result["errors"]:
            print(f"PR {number} INCOMPLETE: {error}", flush=True)
        sys.stdout.flush()
    print(f"files: {os.path.abspath(args.out)}", flush=True)
    return 2 if incomplete else 0


if __name__ == "__main__":
    sys.exit(main())
