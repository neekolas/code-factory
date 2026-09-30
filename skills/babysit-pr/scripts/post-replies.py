#!/usr/bin/env python3
"""Post PR review-thread replies from a file, by thread ID only.

  post-replies.py [--post] [--git-dir DIR] [--base REF] [--marker TEXT] OWNER/REPO PR FILE

FILE is JSON Lines. Each object requires:
  id, action (reply or reply+resolve), body, expected_head,
  expected_last_comment_id, and expected_last_comment_updated_at
  or expected_last_comment_hash (SHA-256 of the exact comment body).
Resolution also requires closure_passed=true and scoped_review_required.
When scoped_review_required=true, scoped_review_passed must be true.
The caller sets these fields only after the named closure proof and required
review pass. A push can occur before these checks pass.

All entries are checked before any mutation. Each entry is checked again
before a reply, after a reply, and before resolution. These reads are best
effort. GitHub does not offer an atomic compare-and-resolve operation.
A stale head, new comment, or edited comment stops the remaining actions.
Legacy pipe input is not accepted. Use explicit JSON guards for every entry.

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

Without --post the script checks all entries and prints a dry run.
An exact latest reply from the authenticated author can be reused on a retry
only when it still follows the validated comment version.

Exit status: 0 success, 1 validation error (nothing posted), 2 API error.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys

PLACEHOLDER = re.compile(r"<sha:([^<>]+)>")
HEX = re.compile(r"(?<![0-9A-Za-z_])[0-9a-f]{7,40}(?![0-9A-Za-z_])")

HEAD = """
query($owner:String!,$name:String!,$pr:Int!){
  repository(owner:$owner,name:$name){pullRequest(number:$pr){headRefOid baseRefName}} viewer{login}}
"""

THREAD = """
query($id:ID!){node(id:$id){__typename ... on PullRequestReviewThread{
  isResolved pullRequest{number headRefOid repository{nameWithOwner}}
  comments(last:2){nodes{id updatedAt body author{login}}}}}}
"""

REPLY = """
mutation($t:ID!,$b:String!){addPullRequestReviewThreadReply(
  input:{pullRequestReviewThreadId:$t,body:$b}){comment{id updatedAt body author{login} url}}}
"""

RESOLVE = """
mutation($t:ID!){resolveReviewThread(input:{threadId:$t}){thread{isResolved}}}
"""


class ApiError(Exception):
    pass


def gh(args):
    try:
        run = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ApiError("gh call failed or exceeded 60 seconds") from error
    try:
        data = json.loads(run.stdout)
    except ValueError:
        data = None
    if run.returncode != 0 and not (isinstance(data, dict) and data.get("errors")):
        raise ApiError(f"gh exited {run.returncode}")
    if data is None:
        raise ApiError("gh returned no JSON")
    return data


def graphql(query, **variables):
    args = ["api", "graphql", "-f", "query=" + query]
    for key, value in variables.items():
        args += ["-F" if isinstance(value, int) else "-f", f"{key}={value}"]
    data = gh(args)
    if data.get("errors"):
        raise ApiError("GraphQL returned an error")
    if not isinstance(data.get("data"), dict):
        raise ApiError("GraphQL response has no data")
    return data["data"]


def git(git_dir, *args):
    try:
        run = subprocess.run(["git", "-C", git_dir, *args], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ApiError("git call failed or exceeded 60 seconds") from error
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
            if not line.strip() or line.startswith("#"):
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                errors.append(f"line {n}: expected a guarded JSON object")
                continue
            if not isinstance(entry, dict):
                errors.append(f"line {n}: expected a guarded JSON object")
                continue
            required = ("id", "action", "body", "expected_head", "expected_last_comment_id")
            if any(not isinstance(entry.get(k), str) or not entry[k] for k in required):
                errors.append(f"line {n}: missing required string fields")
                continue
            action = entry["action"]
            if action not in ("reply", "reply+resolve"):
                errors.append(f"line {n}: unknown action {action!r}")
                continue
            if not (isinstance(entry.get("expected_last_comment_updated_at"), str)
                    and entry["expected_last_comment_updated_at"]) and not (
                    isinstance(entry.get("expected_last_comment_hash"), str)
                    and re.fullmatch(r"[0-9a-f]{64}", entry["expected_last_comment_hash"])):
                errors.append(f"line {n}: a last comment timestamp or SHA-256 hash is required")
                continue
            resolve = action == "reply+resolve"
            if resolve and (entry.get("closure_passed") is not True
                            or not isinstance(entry.get("scoped_review_required"), bool)
                            or (entry["scoped_review_required"] and entry.get("scoped_review_passed") is not True)):
                errors.append(f"line {n}: resolution requires passed closure proof and required scoped review")
                continue
            entry.update({"line": n, "resolve": resolve})
            entries.append(entry)
    return entries, errors


class StaleEntry(Exception):
    pass


def body_hash(body):
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def matches(comment, entry):
    if comment.get("id") != entry["expected_last_comment_id"]:
        return False
    stamp = entry.get("expected_last_comment_updated_at")
    digest = entry.get("expected_last_comment_hash")
    return ((not stamp or comment.get("updatedAt") == stamp)
            and (not digest or body_hash(comment.get("body") or "") == digest))


def validate(entry, node, repo, number, viewer, own=None):
    if not node or node.get("__typename") != "PullRequestReviewThread":
        raise StaleEntry(f"{entry['id']} is not a review thread")
    where = node["pullRequest"]
    if where["number"] != number or where["repository"]["nameWithOwner"].lower() != repo.lower():
        raise StaleEntry(f"{entry['id']} is a thread of {where['repository']['nameWithOwner']}#{where['number']}, not #{number}")
    if where.get("headRefOid") != entry["expected_head"]:
        raise StaleEntry("PR head changed; collect and validate the current feedback")
    comments = node["comments"]["nodes"]
    latest = comments[-1] if comments else {}
    if own is not None:
        if (latest.get("id") != own.get("id") or latest.get("updatedAt") != own.get("updatedAt")
                or latest.get("body") != entry["body"]
                or (latest.get("author") or {}).get("login") != viewer
                or len(comments) < 2 or not matches(comments[-2], entry)):
            raise StaleEntry("thread changed after the reply; leave it open and validate again")
        return True
    # Only the latest exact response can prove a safe retry. Older text has no effect.
    posted = (latest.get("body") == entry["body"]
              and bool(viewer) and (latest.get("author") or {}).get("login") == viewer)
    if matches(latest, entry):
        return posted
    if posted and len(comments) >= 2 and matches(comments[-2], entry):
        return True
    raise StaleEntry("last comment changed or was edited; collect and validate the current feedback")


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

    try:
        entries, errors = parse(args.file)
    except OSError:
        print("ERROR cannot read the reply file; nothing posted")
        return 1
    seen = {}
    for e in entries:
        if e["id"] in seen:
            errors.append(f"line {e['line']}: thread {e['id']} repeats line {seen[e['id']]}")
        seen.setdefault(e["id"], e["line"])
        if not e["body"].startswith(args.marker):
            errors.append(f"line {e['line']}: body does not start with {args.marker!r}")

    try:
        data = graphql(HEAD, owner=owner, name=name, pr=args.pr)
        pr = (data.get("repository") or {}).get("pullRequest")
        if not pr:
            raise ApiError(f"PR {args.pr} not found in {args.repo}")
        pushed = pushed_commits(args.repo, args.base or pr["baseRefName"], pr["headRefOid"])
    except ApiError as error:
        print(f"ERROR {error}")
        return 2

    viewer = (data.get("viewer") or {}).get("login")
    if not viewer:
        print("ERROR authenticated author is missing; nothing posted")
        return 2
    for e in entries:
        try:
            e["body"], e["notes"], body_errors = map_body(e["body"], pushed, args.git_dir)
            errors += [f"line {e['line']}: {msg}" for msg in body_errors]
            if e["expected_head"] != pr["headRefOid"]:
                raise StaleEntry("candidate head does not match the PR head")
            node = graphql(THREAD, id=e["id"]).get("node")
            e["posted"] = validate(e, node, args.repo, args.pr, viewer)
            e["resolved"] = node["isResolved"]
            if e["resolved"] and not e["posted"]:
                raise StaleEntry("thread is already resolved without the expected reply")
        except (ApiError, StaleEntry) as error:
            errors.append(f"line {e['line']}: {e['id']}: {error}")

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
            node = graphql(THREAD, id=e["id"]).get("node")
            posted = validate(e, node, args.repo, args.pr, viewer)
            own = None
            if not posted:
                if node["isResolved"]:
                    raise StaleEntry("thread was resolved before the reply")
                own = graphql(REPLY, t=e["id"], b=e["body"])["addPullRequestReviewThreadReply"]["comment"]
                if not own.get("id") or not own.get("updatedAt"):
                    raise StaleEntry("reply version is missing; leave the thread open")
                node = graphql(THREAD, id=e["id"]).get("node")
                validate(e, node, args.repo, args.pr, viewer, own)
            if e["resolve"] and not node["isResolved"]:
                # This is a best-effort read. GitHub has no conditional resolution mutation.
                node = graphql(THREAD, id=e["id"]).get("node")
                validate(e, node, args.repo, args.pr, viewer, own)
                if not node["isResolved"]:
                    graphql(RESOLVE, t=e["id"])
        except StaleEntry as error:
            print(f"ERROR {e['id']}: {error}; later entries not posted")
            return 1
        except ApiError as error:
            print(f"ERROR {e['id']}: {error}; later entries not posted")
            return 2
    if not args.post:
        print("dry run: nothing posted (use --post)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
