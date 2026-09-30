---
name: babysit-pr
description: "Use when taking one feedback round on a pull request or stack: collect current-head failures and review feedback, apply verified fixes in stack order, and push once. Repeat rounds until the PRs are ready. Works with Graphite (gt), GitHub stacked PRs (gh stack), and standalone branches."
---

# Babysit PR

One round collects available feedback, applies ready verified fixes, pushes
at most once, and checks the new state. Deliver each actionable item to the
implementer as it arrives. Do not wait for a full CI run or all bot comments.
Start a round as soon as one fresh review item or current-head failure appears. Check every PR in
the stack before closing the round. Delivery can start before collection
finishes. Do not wait for other checks to finish.
New feedback can join an active repair at a safe point. Items that arrive
after its push, or cannot join safely, enter the next round. In an
`executing-plans` run, that skill names the PR implementer and push owner.
Send all CI comments and review findings directly to the implementer. It
validates findings and owns repairs. Use scripts for collection; a collector
agent is optional. This skill defines one round, not the wait schedule.

User instructions take precedence over this skill. Check the host's tools
and access before starting. Use an available GitHub connector when `gh` is
absent. If collection is incomplete, report the missing source. Do not treat
missing tools or credentials as a passing check. Do not install a local CLI
or change host configuration without authorization.

## Hard rules

- Do not merge the PR, use `--no-verify`, or disable a failing test to get a
  green check.
- Stage changed files by name. Do not use `git add -A` or `git add .`.
- Use new commits. Do not amend or force-push history you did not create.
  Graphite's `gt modify --commit` and restacks are allowed for its stacks.
- Use check results only for the PR's current head to establish check status.
  Preserve older-head feedback and source identity for validation. A pending
  or missing current-head check is not a pass. A snapshot that changes head
  during collection is STALE and cannot establish readiness.
- Start each PR reply with `🤖 `. Resolve only after the named closure proof
  and any required independent scoped review pass. Guard by the validated
  head and last comment version. Leave newer or uncertain threads, questions,
  disagreements, and owner decisions open. GitHub provides no atomic
  compare-and-swap guard for thread resolution.
- Find a thread only by its ID. Never select threads to reply to or resolve by
  matching words in their text.
- Apply fixes from the bottom of a stack upward. Restack after a lower branch
  changes, then check higher branches again.
- Make at most one push for the stack in a round. Apply ready verified fixes
  locally before that push. Do not hold a completed repair for future comments.
  A round with no code change has no push.

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

1. **Snapshot each affected PR.** If a signal includes a raw comment or
   failure, deliver it with its source head immediately. Complete its evidence
   and check the other PRs while the implementer works. List the whole stack
   from bottom to top. For each
   branch with a PR, record its current head SHA, merge state, required and
   optional checks, and review state. Skip branches without PRs. Stop with an
   error if there is no PR. Use the repository's PR status command, or
   `scripts/check-pr.sh <pr> <repo-dir>` as a fallback. A missing check result
   is not a pass.
2. **Collect and deliver feedback as it becomes available.** Preserve all
   source identities, known `source_commit` values, and older-head comments.
   A source can have a null commit; do not assign it the current head without
   evidence. Get current-head check logs and annotations as failures appear.
   Record running checks as PENDING. Fetch all pages of unresolved threads,
   review bodies, conversation comments, and check output. Keep item IDs,
   version keys, links, and raw evidence. A bot marker alone does not make a
   thread handled. Only caller-trusted author identity and a disposition for
   that exact version can establish that it was handled. A newer comment
   version reopens validation, including a new comment from a bot.

   Use repository tools first. Otherwise run:

   ```sh
   scripts/collect-feedback.py --out <dir> --trusted-author <login> \
     --dispositions <version-dispositions.json> <owner/repo> <pr>...
   ```

   `--trusted-author` is repeatable and names only identities the caller
   trusts. `--dispositions` maps `version_key` to its disposition. It does
   not remove evidence. Omit these options when there is no such record.
   The collector writes `pr-N.json` atomically after each source and flushes
   `SOURCE N threads|reviews|comments|checks READY|INCOMPLETE` updates.
   Deliver each available snapshot path to its implementer immediately.
   Native agents use native messages. Active CLI sessions use the durable
   inbox in `executing-plans/references/feedback-inbox.md`; resume idle lanes
   with that path. Continue other sources and PRs without waiting for checks.

   The JSON records the observed `head`, nullable item `source_commit`,
   comment `updated_at`, `body_hash`, and `version_key`. Threads include
   `expected_last_comment_*` for reply guards. Stable check identity includes
   provider and run identity, not only a display name. `sources` records each
   source's `complete` and `error`. `snapshot_state` is COMPLETE, INCOMPLETE,
   or STALE. `complete=false` and exit 2 signal failed or stale collection.
   Partial or stale evidence can start validation and repair, but cannot
   establish readiness. Refresh changed heads and incomplete sources.
3. **The implementer validates every item.** Pass raw feedback paths and item
   IDs to the existing implementer. Do not send CI comments through a reviewer
   first. Reproduce or trace a reported defect before fixing it. Validate old
   comments against current code and preserve the source head. Find the cause
   of a failed check; mark a base-branch or environment
   failure separately. For a question or false report, give a concrete answer
   with evidence and leave the thread open. Flag a scope, style, or design
   decision for the PR author and leave it open. Do not silently implement an
   architectural suggestion. Keep the verdict for each item ID so the next
   round does not repeat a reply.
4. **Fix in order.** The owning implementer makes the repair. Close routine
   fixes with useful executable evidence and affected required checks. There
   is no default reviewer triage or fix-check turn. In an `executing-plans`
   run, track risk and required scoped closure flags. Do not dispatch a
   reviewer during CI or Macroscope repair loops. Assess accumulated behavior
   and risk changes only after successful current-head checks and handled
   feedback. A high-risk report does not bypass that ordering.
   Resolve the lowest merge conflict first. Then apply all
   verified code fixes from bottom to top. After each lower-branch change,
   restack and check higher branches again. Run fast, cheap local checks,
   not the full repository CI suite. Keep slow required checks pending for
   CI or a separate run. Commit the fixes, and push the affected stack once. A fix on the base branch
   needs a rebase and a new push; rerunning the old PR checks cannot test it.
   A shared stack has one push owner. Lane implementers report commits and
   replies to it; they do not switch branches or edit another lane's files.
   Required checks gate readiness. Investigate optional failures and report
   any that remain.
5. **Close the round.** Reply with fix commits, named closure proof, or
   disposition evidence. Resolve a thread only after its named proof and any
   required independent scoped review pass. A repaired thread can stay open
   solely for the deferred review. Other slow checks still gate readiness.
   Leave owner decisions and disputed items open. Use repository tools first.
   Otherwise use `scripts/post-replies.py <owner/repo> <pr> <file>` with JSON
   Lines. Each line needs `id`, `action`, `body`, `expected_head`,
   `expected_last_comment_id`, and either `expected_last_comment_updated_at`
   or `expected_last_comment_hash`. Example:

   ```json
   {"id":"<thread ID>","action":"reply+resolve","body":"🤖 Fixed in <sha>. Closure: <named test> PASS.","expected_head":"<validated PR head>","expected_last_comment_id":"<comment ID>","expected_last_comment_hash":"<validated body hash>","closure_passed":true,"scoped_review_required":true,"scoped_review_passed":true}
   ```

   Use `action: "reply"` when resolution is not authorized or closure is
   pending. Resolution needs `closure_passed: true` and an explicit
   `scoped_review_required` boolean. When it is true, also require
   `scoped_review_passed: true`. Do not assert a pass without evidence. Legacy
   unguarded pipe entries are not supported. Read the dry run, then add
   `--post` when authorized. Optional `--git-dir <clone>` maps local commit
   references to pushed commits when the helper supports that mapping.

   The poster checks the head and last comment before reply, after reply,
   and before resolution. These checks are best effort. GitHub has no
   compare-and-swap parameter for the mutation. If a newer head or comment
   appears, or the result is uncertain, leave the thread open and collect
   again. Snapshot new heads. Required checks must succeed on those heads.

Repeat the round when a new push, failed check, or review item changes the
state. If required checks finish without findings, check the exit condition.
Stop and report with evidence when the same failure does not improve after
repeated verified fixes, a check stalls, or an owner decision is needed. Do
not keep making equivalent pushes.

## Exit condition

For an `executing-plans` run, first finish the pre-submission review gate.
During CI loops, feedback goes directly to the implementer with no reviewer
triage or repair review. After all current-head CI and Macroscope
checks succeed, all sources are complete, and feedback is handled, record
the accumulated divergence decision. A required second review can then run.
A finding returns to repair and CI before a needed scoped recheck.

For that post-CI gate, handled means validated, dispositioned, and repaired
with available proof. Name any threads open solely for deferred review.
Owner decisions, blocking defects, missing proof, incomplete sources, and
unhandled new comments cannot use this exception. They prevent the gate.

Every PR must have no merge conflict, all required checks passing on its
current head, all feedback addressed, and all required approvals. A reply to
an owner decision records it but does not supply the owner's approval. If a
human review or an external check is still pending, report that state; do not
call the PR ready. Do not merge the PR.
