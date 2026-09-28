---
name: executing-plans
description: Use when running an approved plan, or any change of several tasks, as an orchestrator - prepares a verified context brief, keeps implementers per lane and bounded reviewer sessions per PR, collects PR feedback with a cheap read-only agent, routes verified fixes, and recovers stalled sessions. Has a Claude Code variant and a Codex variant. Replaces code-factory:execute-dynamic-workflow
---

# Executing plans

You are the orchestrator. You own the result: every requirement in the plan is
met and proven, or the gap is reported with evidence. You decide, dispatch,
check git, and integrate. Subagents do the reading and writing.

Read your variant now. It says how to start, message, wait for, and recover
sessions on your platform. This file says what to do.

- Claude Code: `references/claude-code.md`
- Codex: `references/codex.md`

An OpenCode session can use the other skills in this plugin, but it cannot
orchestrate with this one yet: no OpenCode variant exists. Run the
orchestrator in Claude Code or Codex.

`<skill dir>` in those files is the directory of this file. Claude Code gives
it as `${CLAUDE_SKILL_DIR}`; Codex and OpenCode show it in their skill list.

## 1. Start

1. Read the plan and the repository instructions on the path to the code. If
   the plan has no requirements with proofs, stop and use `writing-plans`. If
   the plan or design is in Ref, read it directly with the Plans tools. Use
   `working-with-ref` for section reads and agent access. Pass Ref IDs and
   section references, not exported copies. For repository documents, pass
   their existing paths.
2. Scan the plan once for conflicts: tasks that touch the same files or
   interfaces, contradictions, and gaps. Decide each one and record it in the
   run log as `Ruling: <what> - <why> - <cost if wrong>`. A clean scan needs no
   comment.
3. Name the implementer, reviewer, and chore models with `model-choice`. Ask
   the user if the prompt and the approved plan do not name them.
4. Record the base commit and branch. Work in the current worktree unless the
   plan has parallel lanes.
5. Create the run directory, one per orchestrator session:

   ```text
   ~/.agents/runs/<YYYY-MM-DD>-<repo>-<plan slug>-<first 8 of your session ID>/
     log.md      run log: start time, session ID, plan, base, models, lanes, events
     brief.md    the run brief (section 2)
     tasks/      one task brief per task: <N>.md
     reports/    implementer and chore reports: <session>.md
     prompts/    dispatch prompts, when a platform needs them as files
     sessions/   Codex session files (codex-session.sh uses this as its run dir)
   ```

   `$RUN` below is this directory. Add one line to `log.md` for each event: a
   session started (with its ID and worktree), a task finished (with its
   commit), a review verdict, a ruling, a recovery. Update it before you do
   the next thing. It is how you, or a resumed you, find the state after a
   crash or a compaction. Never re-run a task that the log and git show as
   finished. The date prefix makes cleanup simple: delete a run directory 30
   days after its PRs merge.

## 2. Prepare the context

Most wasted subagent work is orientation: searching for files, guessing
commands, and meeting environment problems. Pay that cost once.

**Preflight** (once per run, on the base commit; a chore session may run it):

- Run the repository's environment status commands (for libxmtp: `just
  backend status`) and list its recipes or scripts.
- Run every verification command the plan names, once. Record which pass and
  which fail on the base commit. A later "this failure is pre-existing" claim
  must cite this baseline.
- Collect known failures: the repository's notes and your memory of flaky
  tests and environment traps.
- Start the run helpers now, not after the first failure: a disk guard that
  runs the repository's prune command and reports low free space, and any CI
  waiter. Record each helper and its start command in the run log.

**Brief** (`$RUN/brief.md`, shared by every session in the run):

- The repository path, worktrees, branches, base commit, and git rules: who
  commits, no stash, no branch switches, no force-push.
- A command table taken only from what preflight ran: the exact command, with
  its wrapper, for format, compile, lint, targeted tests, and services, with
  ports and URLs.
- The baseline results and known failures.
- The approved plan and design Ref IDs or repository paths. Include task and
  section references, the read time, and revision metadata when available.
- The report contract for implementers and chores: the full report goes to
  `$RUN/reports/<session>.md`; the final message is 1,500 characters or fewer.
  Reviewers are exempt: a review exists only as the reviewer's final message.

**Lane context.** Each implementer reads the full approved plan and design
once when its session starts, directly from Ref when hosted there. Include
dependencies and work assigned to other lanes. Full context does not grant
permission to edit another lane's files. A replacement implementer reads the same full context before its
handoff. The plan remains the source of requirements and proofs.

**Task brief** (`$RUN/tasks/<N>.md`, one per task). Point to the task and
requirement IDs in the plan. Keep the brief to deltas, rulings, and path lists:

- Notices of approved changes and rulings that affect this task. Point to
  their current sections in Ref, including changed requirements and proofs;
  do not maintain a second copy of the plan text in the brief.
- Starting paths and known affected callers or sibling implementations.
  Mark these as starting points, not an exhaustive list. Include paths owned
  by other lanes that this task must not edit.
- Changes to verification commands or completion conditions. Use the plan
  and run brief for unchanged instructions; do not copy a reduced task spec.

Put the path to this plugin's `audit-tests/SKILL.md` in the run brief. State
that vacuous tests will be rejected. A repeatable one-off verification can
satisfy a proof without a permanent test, subject to repository rules.

**Plan updates.** Update decisions in Ref and send every affected lane its
Ref ID and changed section references. Record the affected tasks in the run
log. Each lane reads those sections directly before continuing; it must not
keep working from a superseded ruling. If the change invalidates active work,
interrupt at a safe point and preserve uncommitted edits. On resume or
compaction, read the current task and governing decisions again. Read only
the needed sections after the initial full read; do not relay the full text
or keep local copies in sync. For repository plans, use their current files.

Start optimistically. Watch the first subagent's first calls closely. If it
is misconfigured (wrong directory, a command that fails, a sandbox that blocks
it), stop it, fix the brief, and start again.

## 3. Shape the sessions

- **Lanes.** Use the plan's lanes. With no lanes in the plan, use one lane. One
  implementer session runs a lane: every task in it, in order, across PRs.
  Each task starts a new turn in that session; its fixes and CI repairs add
  more turns. Batch small tasks of the same shape into one turn.
- **Parallel lanes** only when they share no files and no contract that is
  still changing, and can merge in any order. Each parallel lane gets its own
  worktree and branch, made with the repository's worktree method. Limit
  concurrent builds to what the machine can hold. For Rust on a 16-core
  machine that is about three builds with `CARGO_BUILD_JOBS=4` each.
- **Worktree location.** Make every worktree where the repository's method
  puts them. Never make one in a session scratchpad: nothing removes it, and
  each worktree keeps its own build directory. In one run, 7 scratchpad
  worktrees held 185 GiB and the disk filled twice.
- **Compaction is fine.** Let implementer sessions, and your own, compact when
  they fill. The run log and the briefs hold the state a compacted session
  needs.
- **New implementer session** for a lane, with a handoff, only when the next
  task is in an unrelated area, the session died and will not resume, or the
  fix loop moves to a stronger model (section 7). A handoff is: the run brief,
  approved plan and design Ref IDs or paths, the task delta,
  `git log --stat <base>..HEAD` for the lane, the uncommitted diff summary, and
  the run log lines for the lane.
- **Reviewer sessions (trial):** keep one active reviewer per lane, scoped to one PR.
  Reuse it for related task reviews, fix checks, and PR triage within that PR.
  Start a replacement before the next turn when any boundary is reached:
  a different PR, six completed review turns (including fix checks and PR
  triage), context compaction, or a move to an unrelated subsystem. Six is a
  starting limit; evaluate it with run results rather than assuming it is
  optimal. Never rotate during a proof or while temporary edits remain.
  Record the PR, reviewer ID, turn count, and replacement reason in the log.
  The replacement gets the standard review inputs, the prior candidate SHA,
  and a short list of open finding IDs, scenarios, and relevant rulings. It
  does not get the transcript or prior review reports. Resolved findings need
  only their disposition when it prevents repeated work. It verifies open
  findings against the code; it does not inherit a PASS verdict. Use task
  review mode for new behavior and fix-check mode for scoped fixes.

  These boundaries replace the reviewer, not the lane implementer.
  The implementer and reviewer share one lane worktree. Only one session owns
  that worktree at a time. Its agent may use fast-tier chore subagents for
  bounded exploration or procedural work. Do not delegate implementation,
  fixes, or review decisions to them. The lane implementer owns all lasting
  code and test changes. Finish or stop all child agents before the turn ends.
  Review and fix turns can alternate; start the next turn only after the
  previous turn and its child agents end. The reviewer may edit code and tests
  to check a claim, then restore the starting state before reporting. A new
  session starts with clean context. The final verification (section 8)
  uses a fresh reviewer.
- **Chore sessions** run long procedural work: preflight and full verification
  runs. A short-lived, read-only chore collects PR feedback for one stack
  round. Chores report short results, so noisy output stays out of your
  context.
- **No extra fixers.** A lane's review findings, PR comments, and CI failures
  go to that lane's reviewer and implementer. The PR collector gathers facts
  only. Do not start another agent to fix or triage findings. Replace a dead
  lane session only with a handoff. Planned reviewer replacement follows the
  boundaries above; it does not add a second active reviewer.
- **No relays.** Start the model you want directly. An agent whose only job is
  to drive another agent doubles the tokens and adds a failure point.

## 4. Task loop

For each task, in lane order:

1. **Write.** Send the implementer its task. It writes the code and useful
   tests or one-off verification steps. It applies `audit-tests` to test
   design. Vacuous tests will be rejected and cause another review cycle.
   It does not build, format, or run tests while it writes: other lanes share
   the CPU and the caches, and one build at the end costs less.
2. **Make it clean.** The same implementer runs the brief's format, compile,
   and lint commands for the code it changed, fixes every issue, and commits.
   The commit is the review subject.
3. **Review.** Apply the reviewer session boundaries in section 3, then send
   the task with `references/review-prompt.md`. Give it
   the run brief, the task brief, the requirement IDs, and the base and
   candidate commits. It runs the task's proofs itself, so it needs a sandbox
   that can build. Before review, record `HEAD` and `git status --porcelain` in
   the review worktree. `HEAD` must be the candidate commit and status must be
   empty. If either check fails, resolve the mismatch before review; do not
   include uncommitted work in a review of the commit. Keep the implementer
   idle until review and its proofs finish. The reviewer may make temporary
   edits for checks, but must restore its starting state.
   Check `HEAD` and status again after review. If they differ from the start,
   have the reviewer restore its changes before accepting the report. If the
   checkout changed unexpectedly during a plan proof, repeat the affected
   review and proof on the candidate commit. It returns its report to you only.
4. **Rule.** Decide each finding: valid, or rejected with a one-line reason in
   the run log. A silent discard is not allowed. Read the code yourself only
   when the report is unclear. Send the valid CRITICAL and MAJOR findings to
   the implementer in your message, as fix instructions. Do not save the
   review. Log MINOR findings in the run log for the final review. The
   implementer fixes, cleans, and commits. It searches related paths for the
   same specific cause and records other instances or the bounded search
   result. The active reviewer checks those fixes and regressions they could
   cause. A fix that adds unrelated behavior needs a task review of that
   scope. Apply section 3 before each reviewer turn. Fix rounds follow section 7.
5. **Prove.** Trust the reviewer's report of the checks it ran on the final
   commit of the task. Run only what it did not: the brief's format, compile,
   and lint commands (all features where the repository lints them) and the
   targeted tests for the directly impacted packages. Use a chore session when
   the run is long. Do not run full suites locally; CI runs them. An
   implementer's claim that a failure is pre-existing counts only when the
   baseline confirms it.
6. **Record.** Mark the task done in the run log with its final commit. Done
   is not ready: the task is ready only when its PR is ready (section 5).

The next task in the lane goes to the same implementer session.

The first message to a lane session, trimmed for later tasks:

```text
You implement lane <A>. Read <RUN>/brief.md, then read the full approved plan
and design named there once at session start. Read Ref documents directly
with the Plans tools; use section reads for later work.
Then read <RUN>/tasks/<N>.md for deltas, rulings, and starting paths. Later
tasks use the same plan context plus direct reads of the current task and
changed decisions. The brief points to the plan; it does not replace it.
Worktree: <path>. Branch: <name>. Task <N>: <title>.
Done means: the code and useful proofs for Task <N> are written, format, compile, and
lint are clean for the code you changed, and the work is committed on <branch>.
Read the audit-tests path in the run brief. New or changed vacuous tests will
be rejected and cause review cycles. Use existing coverage when it proves the
behavior. A repeatable one-off command or script is valid when a permanent
test adds no useful protection and repository rules allow it. Report its
steps, inputs, commit, expected result, and observed result; do not check in
the helper only to satisfy a proof row. For a bug fix, check related paths
for the same cause. Report the bounded search and any other instances.
Do the whole task in this turn. Do not stop at an acknowledgement or a plan.
Do not build or run tests until the code and tests are written. Do not end your
turn while a command you started or a subagent you started is still running.
You may use fast-tier chore subagents for bounded exploration or procedural
work. Do not delegate code or test writing, or fixes to them. You own the
task's code, tests, and decisions. Finish or stop all child agents before your
turn ends.
If you are blocked, stop and say what blocks you and what you tried.
Write the full report to <RUN>/reports/<session>.md. Final message, 1,500
characters or fewer: status (DONE | DONE_WITH_CONCERNS | BLOCKED), commits,
checks run with results, concerns.
```

Do not ask the implementer to stop for review part way or to send progress
updates. Both make some models stop early.

## 5. PRs

When every task in a PR is done:

1. Merge parallel lanes into the PR branch one at a time. After each merge,
   compile and run the targeted tests when the lanes share a contract.
2. Push and open the PR with the repository's stack tool. The description says
   what changed and why, the requirement IDs covered, the spec changes, how it
   was verified (commands and results), deviations from the plan, and known
   gaps. Do not paste review reports.
3. Start the next planned task before you end your turn. A milestone is not a
   stopping point.
4. Follow each PR with the one-round procedure in `babysit-pr`. Repeat on a
   new push or new feedback until its exit condition is met. In each round:
   - **Wait for the first signal.** Use a background check watch or platform
     notification. Start a round as soon as one check fails on a current head,
     a merge conflict appears, or one fresh review item arrives. Also wake
     when all required checks finish, to test readiness. The watch must
     surface the first failure; do not wait for the slowest check before you
     start work on a finding. Do not poll in your own context.
   - **Collect.** Send one cheap, read-only chore agent across the entire
     stack with `references/pr-collector.md`. It follows `babysit-pr` collection
     steps and checks every PR before it reports. Pending checks do not delay
     the report. It writes a short index plus raw evidence files. It does not
     judge findings or change the PR. Read its short index; keep raw logs and
     comment bodies out of your context.
   - **Review.** Apply section 3 to select or replace the reviewer for each
     lane and PR. Send its items and the report path with the PR triage prompt
     in `references/review-prompt.md`.
     Wait for the implementer's turn to end before starting the reviewer turn.
     It verifies each item and returns a verdict with evidence. Send no items
     to a reviewer when the collector found none for that lane. Send each
     round's triage to that lane reviewer. Do not start a new triage session
     for each round.
   - **Rule.** Before you rule on a triage item, read the MUST and MUST NOT
     rows of every requirement ID it names. A ruling must not contradict one.
     Before a reply says that a waiver covers something, find that exact ID in
     the repository's waiver file on that PR's head, and quote it. Write each
     owner decision into the owning spec's Known limitations, or the
     repository's equivalent, in the same turn. Review bots read the
     repository, not the run log or Ref.
   - **Fix.** Send valid findings to the owning lane's implementer as its next
     turn. If it is in a task, wait until that turn ends unless the PR blocks
     other work. It fixes, cleans, and commits. The active reviewer checks its
     fixes, subject to section 3. Take cross-lane conflicts, base-branch
     failures, and owner items yourself.
   - **Push once.** Apply all verified fixes bottom-up. Run targeted checks,
     restack PRs above changed branches, then push the affected stack once.
     Post `🤖 ` replies and resolve only fixed threads after the push, with
     `babysit-pr`'s `scripts/post-replies.py`. If there is no code change, do
     not push. Record the heads in the run log. A thread ID in the log does
     not mark the thread handled: its last comment does.
   - **Ready** means every required check is green on each PR's current head,
     feedback is addressed, required approvals are present, and no merge
     conflict remains. A green run on an earlier commit does not count. Do
     not report a PR or its tasks as ready before that.
   - After a rebase or a force-push, CI must pass again on the new head
     before you report the PR ready.
   - A re-run of failed jobs tests the same merge commit again. It does not
     pick up new commits on the base branch. When the fix is on the base,
     rebase the PR branch and push; do not re-run.
5. A stacked PR may start before the PR below it is green.

## 6. Session health

A session can die or hang without a signal. Silence is not progress, and no
notification is not proof that a session is alive.

- **Record** every session's ID in the run log when it starts.
- **Wait in bounded stretches** of five to ten minutes. After each stretch,
  check every live session's transcript or event log and its worktree, and
  chase any that finished without a report.
- **Check the disk** after each stretch: `df -h` on the worktrees' volume.
  Remove a worktree as soon as its PR merges, or its work is pushed and no
  task remains for it. First release its services with the repository's
  method, then run `git worktree remove <path>`. When less than 15% of the
  disk is free, remove every finished worktree before the next build starts.
  If none is finished, tell the user.
- **Never remove a worktree that a live session uses as its working
  directory.** Stop the session first, or keep the worktree. A Codex session
  cannot resume after its directory is gone: `codex-session.sh resume` exits
  3, and the lane needs a new session with a handoff.
- **Finished** means all three: the platform says the turn ended, the
  session's final message exists, and the commit it reports is in git. Check
  git, not the summary.
- **Dead** means the session ended without a completed turn, or with an error.
  A session that ends its turn while its own build is still running is not
  finished: send it back to wait.
- **Stalled** means no new event for 20 minutes and no command still running.
  A build or test that is still running is not a stall until it has run three
  times that long.
- **Usage limits.** When a model hits a session or usage limit, switch to the
  next model in its tier (`model-choice`) at once. Do not wait for the limit
  to reset. After the limit resets, move each role back to its planned model.
  Resume the lane's earlier reviewer session on that model, within the
  section 3 boundaries; do not start a new one.
- **Run helpers.** After a restart or a disk-full error, start again every
  helper that the run log lists (disk guard, CI waiter) before other work.
- **Waiters.** Every background waiter has a total timeout, and every `gh`
  call in it runs under `timeout 60`. Before you start a new waiter, stop the
  old one.
- **Transient errors.** When a tool call fails with a transient error (a
  classifier with no verdict, a rate limit, an HTTP 5xx), do not end your
  turn. Wait for the backoff time with a background wait that wakes you (in
  Claude Code, a background `sleep`). At your own usage limit, do the same
  until the reset time.
- **Recover** in this order:
  1. Stop what is left of the session. Resume the same session with:
     "Your session was interrupted. Run `git status` and `git log -3`, re-read
     Task N in the plan, and continue. Do not redo committed work."
  2. If two resumes fail, start a new session on the same model with a
     handoff.
  3. If that fails, escalate (section 7).
- Uncommitted work from a dead session stays in its worktree. Do not reset it.
  The next session starts from it.
- **Never poll for a person.** When you need a decision or an approval, post
  the request, record the state in the run log, and end your turn. Do not call
  a waiting tool in a loop.

## 7. Escalate and decide

- Fix rounds on the same finding: rounds 1-3 in the same implementer session;
  rounds 4-5 in a new session one step up (`model-choice`); after round 5, rule
  on it: take the task yourself, change the approach, or park the finding
  with a recorded ruling.
- A fix that needs files outside the lane or changes a shared contract: take
  the task yourself.
- Before you design a fix, read again the memory notes whose names match the
  problem (for example, `gh-stack-*` notes before a CI base fix). Notes
  written after your session started are not in your context.
- Make rulings instead of stopping. Stop and ask the user only for: an
  irreversible or destructive operation, a security decision, a side effect
  outside the worktree, or a plan too broken to follow. A requirement that
  cannot be met as written is the last case: record the evidence, continue
  with independent tasks, and ask. Do not weaken the requirement or the test.

## 8. Finish

1. **Final verification.** A fresh reviewer checks the whole change and every
   requirement ID on the final commit of the top PR: one row per ID with the
   commit, the test or command, and its result. Give it the logged MINOR
   findings to triage. The implementer's claims do not count. This may run
   while CI runs. Send all valid findings to the owning lane's implementer in
   one message, then one scoped re-check; findings still open after that go to the user.
   Any later push invalidates the rows its diff can affect; run them again on
   the new commit. The run is complete only when every row is PASS and CI is
   green, both on the same final commit. An UNVERIFIED row is a failure.
2. **Execution notes.** Append to the plan's `Execution notes` section, in
   short bullets:
   - Deviations: what changed from the plan, and why.
   - Issues found: defects, flaky tests, and review findings that matter later.
   - Repository stumbling blocks: commands, tools, and environment problems
     that cost time, with the fix.
   Update `Spec changes` if it changed.
3. **Clean up.** Stop live sessions. Then remove the worktrees you made
   that section 6 did not remove yet, the same way. Delete temporary files.
4. **Report** to the user: PRs and their state, the requirement matrix (counts,
   and every failure), deviations, model substitutions, and open items.
5. **No automatic retro.** Do not start `session-retro`. The user runs it
   when they want one. Keep the run directory, which it reads.

## Token discipline

Your own context is the largest cost in a long run: every turn re-reads it.

- Pass Ref IDs, section references, paths, and commit IDs, not document
  contents. Subagents read Ref sections and the briefs directly.
- Reports go to files. Final messages stay under 1,500 characters. Read a full
  report only when the short one leaves a decision open.
- Read `git log --stat` and `git diff --stat`, not whole diffs and logs. Read
  code only to rule on a finding you cannot judge from the report.
- Read the full approved plan and design once per implementer session.
  For Ref documents, use direct section reads thereafter. Send references
  to changed sections, not document copies.
- Keep implementers alive across tasks. Reuse reviewers only within the
  boundaries in section 3.
- Run short, known commands yourself. Send long or noisy ones, and test runs,
  to a chore session.
- Let your context compact when it fills. Write the state to the run log first
  at a phase boundary, so a compacted you continues from the log.
