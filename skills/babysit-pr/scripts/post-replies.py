#!/usr/bin/env python3
"""Post PR review-thread replies from a file, by thread ID only.

  post-replies.py [--post] [--git-dir DIR] [--base REF] [--marker TEXT] OWNER/REPO PR FILE

FILE has one reply on each line; blank lines and lines that start with "#"
are ignored:

  <thread id>|<action>|<body>

  action  reply          post the reply and leave the thread open
          reply+resolve  post the reply, then resolve the thread
          (keep and resolve are accepted as older names for these two)

The body must start with the marker (default "🤖"). It can name commits in
two ways:

  <sha:commit subject>  replaced by the one pushed commit with that subject
  a hex token (7-40)    kept when it is a pushed commit; when --git-dir
                        resolves it to a local commit that is not pushed (for
                        example before a restack), replaced by the one pushed
                        commit with the same subject; left as it is when it
                        is not a commit (for example the number 104857600).
                        Without --git-dir, a token that is not pushed is an
                        error, unless it has only digits or only letters.

"Pushed commits" are the commits between the base (default: the PR's base
branch; use --base <trunk> for a stack) and the PR's current head on GitHub.
A subject with no match or with two matches is an error.

Before anything is posted, the script checks every entry: the ID is a review
thread of this PR, the action is known, no ID repeats, and every commit
reference maps. Any failure stops the script with exit 1 and posts nothing.
The script never finds a thread by its text.

Without --post the script is a dry run: it prints what it would do and
changes nothing. With --post it posts each reply (skipping a body the thread
already has) and resolves only reply+resolve threads.

Exit status: 0 success, 1 validation error (nothing posted), 2 API error.
"""
import argparse
import json
import re
import subprocess
import sys

ACTIONS = {"reply": False, "keep": False, "reply+resolve": True, "resolve": True}
PLACEHOLDER = re.compile(r"<sha:([^<>]+)>")
HEX = re.compile(r"(?<![0-9A-Za-z_])[0-9a-f]{7,40}(?![0-9A-Za-z_])")

HEAD = """
query($owner:String!,$name:String!,$pr:Int!){
  repository(owner:$owner,name:$name){pullRequest(number:$pr){headRefOid baseRefName}}}
"""

THREAD = """
query($id:ID!){node(id:$id){__typename ... on PullRequestReviewThread{
  isResolved pullRequest{number repository{nameWithOwner}}
  comments(last:100){nodes{body}}}}}
"""

REPLY = """
mutation($t:ID!,$b:String!){addPullRequestReviewThreadReply(
  input:{pullRequestReviewThreadId:$t,body:$b}){comment{url}}}
"""

RESOLVE = """
mutation($t:ID!){resolveReviewThread(input:{threadId:$t}){thread{isResolved}}}
"""


class ApiError(Exception):
    pass


def gh(args):
    try:
        run = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ApiError(str(error))
    try:
        data = json.loads(run.stdout)
    except ValueError:
        data = None
    if run.returncode != 0 and not (isinstance(data, dict) and data.get("errors")):
        first = (run.stderr.strip() or run.stdout.strip() or "no output").splitlines()[0]
        raise ApiError(f"gh exited {run.returncode}: {first}")
    if data is None:
        raise ApiError("gh returned no JSON")
    return data


def graphql(query, **variables):
    args = ["api", "graphql", "-f", "query=" + query]
    for key, value in variables.items():
        args += ["-F" if isinstance(value, int) else "-f", f"{key}={value}"]
    data = gh(args)
    if data.get("errors"):
        raise ApiError("GraphQL: " + data["errors"][0].get("message", "error"))
    return data["data"]


def git(git_dir, *args):
    run = subprocess.run(["git", "-C", git_dir, *args], capture_output=True, text=True)
    return run.stdout.strip() if run.returncode == 0 else ""


def pushed_commits(repo, base, head):
    """(sha, subject) for each commit in base...head on GitHub, all pages."""
    commits, page = [], 1
    while True:
        data = gh(["api", f"repos/{repo}/compare/{base}...{head}?per_page=100&page={page}"])
        batch, total = data.get("commits"), data.get("total_commits")
        if batch is None or total is None:
            raise ApiError("compare: page has no commits")
        commits += [(c["sha"], c["commit"]["message"].split("\n", 1)[0]) for c in batch]
        if len(commits) >= total:
            return commits
        if not batch:
            raise ApiError(f"compare: {len(commits)} of {total} commits read")
        page += 1


def parse(path):
    entries, errors = [], []
    with open(path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            line = line.rstrip("\n")
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.split("|", 2)
            if len(parts) != 3 or not parts[0].strip():
                errors.append(f"line {n}: expected <thread id>|<action>|<body>")
                continue
            tid, action, body = parts[0].strip(), parts[1].strip(), parts[2].strip()
            if action not in ACTIONS:
                errors.append(f"line {n}: unknown action {action!r}")
                continue
            entries.append({"line": n, "id": tid, "resolve": ACTIONS[action], "body": body})
    return entries, errors


def map_body(body, pushed, git_dir):
    """Return (body, notes, errors) with every commit reference mapped to a pushed commit."""
    notes, errors = [], []
    by_subject = {}
    for sha, subject in pushed:
        by_subject.setdefault(subject, []).append(sha)

    def placeholder(match):
        subject = match.group(1).strip()
        found = by_subject.get(subject, [])
        if len(found) != 1:
            errors.append(f"<sha:{subject}>: {len(found)} pushed commits have this subject")
            return match.group(0)
        notes.append(f"<sha:{subject[:40]}>->{found[0][:9]}")
        return found[0][:9]

    def token(match):
        tok = match.group(0)
        on_head = [sha for sha, _ in pushed if sha.startswith(tok)]
        if len(on_head) == 1:
            return tok
        if len(on_head) > 1:
            errors.append(f"{tok}: matches {len(on_head)} pushed commits")
            return tok
        full = git(git_dir, "rev-parse", "--verify", "-q", tok + "^{commit}") if git_dir else ""
        if not full:
            if git_dir or tok.isdigit() or tok.isalpha():
                notes.append(f"skip {tok} (not a commit)")
            else:
                errors.append(f"{tok}: not a pushed commit; pass --git-dir to map a local commit")
            return tok
        subject = git(git_dir, "log", "-1", "--format=%s", full)
        found = by_subject.get(subject, [])
        if len(found) != 1:
            errors.append(f"{tok} ({subject[:60]!r}): {len(found)} pushed commits have this subject")
            return tok
        new = found[0][: len(tok)]
        notes.append(f"{tok}->{new}")
        return new

    body = PLACEHOLDER.sub(placeholder, body)
    body = HEX.sub(token, body)
    return body, notes, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--post", action="store_true", help="post and resolve; without it, a dry run")
    parser.add_argument("--git-dir", help="local clone used to map unpushed commit IDs by subject")
    parser.add_argument("--base", help="base ref for pushed commits (default: the PR's base branch)")
    parser.add_argument("--marker", default="🤖", help="required prefix of each reply (default: 🤖)")
    parser.add_argument("repo", help="OWNER/REPO")
    parser.add_argument("pr", type=int)
    parser.add_argument("file")
    args = parser.parse_args()
    if "/" not in args.repo:
        parser.error("repo must be OWNER/REPO")
    owner, name = args.repo.split("/", 1)

    entries, errors = parse(args.file)
    seen = {}
    for e in entries:
        if e["id"] in seen:
            errors.append(f"line {e['line']}: thread {e['id']} repeats line {seen[e['id']]}")
        seen.setdefault(e["id"], e["line"])
        if not e["body"].startswith(args.marker):
            errors.append(f"line {e['line']}: body does not start with {args.marker!r}")

    try:
        pr = (graphql(HEAD, owner=owner, name=name, pr=args.pr).get("repository") or {}).get("pullRequest")
        if not pr:
            raise ApiError(f"PR {args.pr} not found in {args.repo}")
        pushed = pushed_commits(args.repo, args.base or pr["baseRefName"], pr["headRefOid"])
    except ApiError as error:
        print(f"ERROR {error}")
        return 2

    for e in entries:
        e["body"], e["notes"], body_errors = map_body(e["body"], pushed, args.git_dir)
        errors += [f"line {e['line']}: {msg}" for msg in body_errors]
        try:
            node = graphql(THREAD, id=e["id"]).get("node")
        except ApiError as error:
            errors.append(f"line {e['line']}: {e['id']}: {error}")
            continue
        if not node or node.get("__typename") != "PullRequestReviewThread":
            errors.append(f"line {e['line']}: {e['id']} is not a review thread")
            continue
        where = node["pullRequest"]
        if where["number"] != args.pr or where["repository"]["nameWithOwner"].lower() != args.repo.lower():
            errors.append(
                f"line {e['line']}: {e['id']} is a thread of "
                f"{where['repository']['nameWithOwner']}#{where['number']}, not #{args.pr}")
            continue
        e["resolved"] = node["isResolved"]
        e["posted"] = any(c["body"].strip() == e["body"] for c in node["comments"]["nodes"])

    print(f"PR {args.pr} head={pr['headRefOid'][:9]} pushed_commits={len(pushed)} entries={len(entries)}")
    if errors:
        for msg in errors:
            print(f"ERROR {msg}")
        print("nothing posted")
        return 1

    mode = "POST" if args.post else "DRY"
    for e in entries:
        steps = ["already-posted" if e["posted"] else "reply"]
        if e["resolve"]:
            steps.append("already-resolved" if e["resolved"] else "resolve")
        print(f"{mode} {e['id']} {'+'.join(steps)} {' '.join(e['notes'])}".rstrip())
        if not args.post:
            continue
        try:
            if not e["posted"]:
                graphql(REPLY, t=e["id"], b=e["body"])
            if e["resolve"] and not e["resolved"]:
                graphql(RESOLVE, t=e["id"])
        except ApiError as error:
            print(f"ERROR {e['id']}: {error}; later entries not posted")
            return 2
    if not args.post:
        print("dry run: nothing posted (use --post)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
