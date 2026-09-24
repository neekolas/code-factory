---
name: babysit-pr
description: "Use when taking one feedback round on a pull request or stack: collect current-head failures and review feedback, apply verified fixes in stack order, and push once. Repeat rounds until the PRs are ready. Works with Graphite (gt), GitHub stacked PRs (gh stack), and standalone branches."
---

# Babysit PR

One round collects all feedback available across the stack, applies verified
fixes, pushes at most once, and checks the new state. Start a round as soon as
one fresh review item or current-head check failure appears. Check every PR in
the stack before reporting the round. Do not wait for other checks to finish.
Feedback that arrives later enters the next round. In an
`executing-plans` run, that skill assigns the collector, reviewers,
implementers, and push owner. This skill defines the work in a round, not the
agents or wait schedule.

## Hard rules

- Do not merge the PR, use `--no-verify`, or disable a failing test to get a
  green check.
- Stage changed files by name. Do not use `git add -A` or `git add .`.
- Use new commits. Do not amend or force-push history you did not create.
  Graphite's `gt modify --commit` and restacks are allowed for its stacks.
- Read check results only for the PR's current head commit. A failure on an
  older head is stale. A pending check on the new head is not a pass.
- Start each PR reply with `🤖 `. Resolve a thread only after its issue is
  fixed. Leave questions, disagreements, and owner decisions open.
- Apply fixes from the bottom of a stack upward. Restack after a lower branch
  changes, then check higher branches again.
- Make at most one push for the stack in a round. Apply all verified fixes
  locally before that push. A round with no code change has no push.

## Backend

Detect the backend once. Read `references/graphite.md` or
`references/gh-stack.md` before using its commands. A standalone PR uses
plain `git` and `gh`.

```
if [ -f .git/.graphite_repo_config ] || gt ls >/dev/null 2>&1  → GRAPHITE
elif gh stack view --json >/dev/null 2>&1                      → GH-STACK
else                                                           → STANDALONE
```

| Verb | Graphite | gh-stack | Standalone |
| --- | --- | --- | --- |
| List bottom to top | `gt ls` | `gh stack view --json` | Current branch |
| Switch branch | `gt checkout <br>` | `gh stack checkout <br>` | `git checkout <br>` |
| Commit fix | `gt modify --commit -m "..."` | `git add <files> && git commit` | `git add <files> && git commit` |
| Restack and push | `gt restack && gt submit --stack` | `gh stack rebase --upstack && gh stack submit --auto` | `git push` |

## One feedback round

1. **Snapshot every PR.** List the whole stack from bottom to top. For each
   branch with a PR, record its current head SHA, merge state, required and
   optional checks, and review state. Skip branches without PRs. Stop with an
   error if there is no PR. Use the repository's PR status command, or
   `scripts/check-pr.sh <pr> <repo-dir>` as a fallback. A missing check result
   is not a pass.
2. **Collect all current feedback across the stack before reporting.** Get
   logs and annotations for every check that has failed so far on each current
   head. Record checks still running as pending. Fetch all pages of unresolved
   review threads, review bodies, and conversation comments. Keep each item's
   ID, PR, head SHA, link, and evidence. Ignore resolved threads and comments
   already answered by a `🤖 ` reply. Do not treat a stale check as a current
   failure.
   Use repository commands first; use `gh` when they do not cover a source.
3. **Triage every item.** Reproduce or verify a reported defect before fixing
   it. Find the root cause of a failed check; mark a base-branch or environment
   failure separately. For a question or false report, give a concrete answer
   with evidence and leave the thread open. Flag a scope, style, or design
   decision for the PR author and leave it open. Do not silently implement an
   architectural suggestion. Keep the verdict for each item ID so the next
   round does not repeat a reply.
4. **Fix in order.** Resolve the lowest merge conflict first. Then apply all
   verified code fixes from bottom to top. After each lower-branch change,
   restack and check higher branches again. Run targeted local checks, commit
   the fixes, and push the affected stack once. A fix on the base branch
   needs a rebase and a new push; rerunning the old PR checks cannot test it.
   Required checks gate readiness. Investigate optional failures and report
   any that remain.
5. **Close the round.** After the push, reply `🤖 Fixed in <commit>` on fixed
   threads and resolve them. Answer or flag other reviewed items with their
   evidence, without resolving owner decisions. Snapshot the new heads. All
   required checks must pass on those heads before the PRs can be ready.

Repeat the round when a new push, failed check, or review item changes the
state. If required checks finish without findings, check the exit condition.
Stop and report with evidence when the same failure does not improve after
repeated verified fixes, a check stalls, or an owner decision is needed. Do
not keep making equivalent pushes.

## Exit condition

Every PR must have no merge conflict, all required checks passing on its
current head, all feedback addressed, and all required approvals. A reply to
an owner decision records it but does not supply the owner's approval. If a
human review or an external check is still pending, report that state; do not
call the PR ready. Do not merge the PR.
