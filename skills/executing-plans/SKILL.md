---
name: executing-plans
description: Use when running an approved plan, or any change of several tasks, as an orchestrator - prepares a verified context brief, runs one long-lived implementer and one long-lived reviewer per lane (the reviewer reviews each task and triages PR comments and CI failures; the implementer fixes them), PRs that may span tasks, CI follow-up by the orchestrator, and recovery from dead or stalled agent sessions. Has a Claude Code variant and a Codex variant. Replaces code-factory:execute-dynamic-workflow
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
   the plan is in Ref, read it once and write it to `$RUN/plan.md`; work from
   that file.
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
     plan.md     local copy of the plan
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

**Brief** (`$RUN/brief.md`, shared by every session in the run):

- The repository path, worktrees, branches, base commit, and git rules: who
  commits, no stash, no branch switches, no force-push.
- A command table taken only from what preflight ran: the exact command, with
  its wrapper, for format, compile, lint, targeted tests, and services, with
  ports and URLs.
- The baseline results and known failures.
- The report contract for implementers and chores: the full report goes to
  `$RUN/reports/<session>.md`; the final message is 1,500 characters or fewer.
  Reviewers are exempt: a review exists only as the reviewer's final message.

**Task brief** (`$RUN/tasks/<N>.md`, one per task). Copy the task from the
plan with what it needs, so the subagent reads this file and the run brief,
not the whole plan:

- The task, its requirement rows, and the decisions and code the plan gives
  for it.
- The files and line ranges to start from, and the files other lanes own,
  which this task must not change.
- The proofs that must pass and what "done" means.

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
  the task brief, `git log --stat <base>..HEAD` for the lane, the uncommitted
  diff summary, and the run log lines for the lane.
- **Reviewer sessions:** one per lane. Start it at the lane's first review, and
  keep it for every later task and PR of that lane. It reviews each task
  commit, checks the fixes for its own findings, and triages the lane's PR
  review comments and CI failures (section 5). It never writes code, so it
  stays independent of the implementer. The final verification (section 8)
  uses a fresh reviewer.
- **Chore sessions** run long procedural work: preflight and full verification
  runs. They report short results, so their output stays out of your context.
- **No extra fixers.** A lane's review findings, PR comments, and CI failures
  go to that lane's reviewer and implementer. Do not start a new agent to fix
  or triage them. A new session is only for a dead one, with a handoff.
- **No relays.** Start the model you want directly. An agent whose only job is
  to drive another agent doubles the tokens and adds a failure point.

## 4. Task loop

For each task, in lane order:

1. **Write.** Send the implementer its task. It writes the code and the tests.
   It does not build, format, or run tests while it writes: other lanes share
   the CPU and the caches, and one build at the end costs less.
2. **Make it clean.** The same implementer runs the brief's format, compile,
   and lint commands for the code it changed, fixes every issue, and commits.
   The commit is the review subject.
3. **Review.** Send the task to the lane's reviewer. On the lane's first
   review, start it with `references/review-prompt.md`. Give it
   the run brief, the task brief, the requirement IDs, and the base and
   candidate commits. It runs the task's proofs itself, so it needs a sandbox
   that can build (the same one as the implementer). Record `git status
   --porcelain` before and after: a review must leave tracked files unchanged.
   It returns its report to you only.
4. **Rule.** Decide each finding: valid, or rejected with a one-line reason in
   the run log. A silent discard is not allowed. Read the code yourself only
   when the report is unclear. Send the valid CRITICAL and MAJOR findings to
   the implementer in your message, as fix instructions. Do not save the
   review. Log MINOR findings in the run log for the final review. The
   implementer fixes, cleans, and commits. The same reviewer checks only those
   fixes. Fix rounds follow section 7.
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
You implement lane <A>. Read <RUN>/brief.md, then <RUN>/tasks/<N>.md; they
have the task, the commands, the git rules, and the known failures.
Worktree: <path>. Branch: <name>. Task <N>: <title>.
Done means: the code and tests for Task <N> are written, format, compile, and
lint are clean for the code you changed, and the work is committed on <branch>.
Do the whole task in this turn. Do not stop at an acknowledgement or a plan.
Do not build or run tests until the code and tests are written. Do not end your
turn while a command you started is still running. Do not start subagents.
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
4. Follow the PR until it is ready: failed checks, review comments, merge
   conflicts. You do this yourself, with `babysit-pr` when it exists. The
   lane's sessions do the rest; start no other agent.
   - **You check.** Take the CI status, the failed-job summaries, and the new
     comments with the repository's commands. Read the failure log, and check
     the known failures, before you call a failure flaky. Resolve merge
     conflicts and rebases yourself.
   - **The reviewer triages.** Send the new comments and failure summaries to
     the lane's reviewer in one message. It verifies each one adversarially
     against the code and returns a verdict with evidence: real defect, not a
     defect, or out of scope (a design or scope question for the owner).
   - **The implementer fixes.** Send the real defects to the lane's
     implementer as its next turn. If it is in the middle of a task, the fixes
     go after that turn ends, unless the PR blocks other work. It fixes,
     cleans, and commits. The reviewer checks only those fixes.
   - **You prove and push.** Run the brief's targeted checks on the fix
     commit, push once, and answer each thread: "Fixed in <commit>" and
     resolve, or the reviewer's evidence and leave open. Flag out-of-scope
     items to the owner.
   - **Ready** means every required check is green on the PR's current head
     commit. A red or pending check is not ready, and neither is a green run
     on an earlier commit. Do not report a PR or its tasks as ready or
     mergeable before that.
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
  to reset.
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

- Pass paths and commit IDs, not file contents. Subagents read the briefs.
- Reports go to files. Final messages stay under 1,500 characters. Read a full
  report only when the short one leaves a decision open.
- Read `git log --stat` and `git diff --stat`, not whole diffs and logs. Read
  code only to rule on a finding you cannot judge from the report.
- Read a Ref or other remote plan once. Work from the local copy.
- Keep sessions alive across tasks so their caches stay warm.
- Run short, known commands yourself. Send long or noisy ones, and test runs,
  to a chore session.
- Let your context compact when it fills. Write the state to the run log first
  at a phase boundary, so a compacted you continues from the log.
