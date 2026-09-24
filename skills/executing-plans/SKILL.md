---
name: executing-plans
description: Use when running an approved plan, or any change of several tasks, as an orchestrator - prepares a verified context brief, runs long-lived implementer sessions per lane, a clean-context adversarial review per task, PRs that may span tasks, CI follow-up, and recovery from dead or stalled agent sessions. Has a Claude Code variant and a Codex variant. Replaces code-factory:execute-dynamic-workflow
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
- **Compaction is fine.** Let implementer sessions, and your own, compact when
  they fill. The run log and the briefs hold the state a compacted session
  needs.
- **New implementer session** for a lane, with a handoff, only when the next
  task is in an unrelated area, the session died and will not resume, or the
  fix loop moves to a stronger model (section 7). A handoff is: the run brief,
  the task brief, `git log --stat <base>..HEAD` for the lane, the uncommitted
  diff summary, and the run log lines for the lane.
- **Reviewer sessions** are fresh for each review subject. Send fixes back to
  the same reviewer only to check its own findings.
- **Chore sessions** run long procedural work: preflight, full verification
  runs, CI follow-up, log triage, rebases. They report short results, so their
  output stays out of your context.
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
3. **Review.** Start a fresh reviewer with `references/review-prompt.md`. Give
   it the run brief, the task brief, the requirement IDs, and the base and
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
6. **Record.** Mark the task done in the run log with its final commit.

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
   conflicts. A chore session can do this; use `babysit-pr` when it exists.
   Read the failure log, and check the known failures, before you call a
   failure flaky. Send code fixes to the lane's implementer when its session
   is alive, otherwise to a new session with a handoff. Push follow-up commits.
5. A stacked PR may start before the PR below it is green.

## 6. Session health

A session can die or hang without a signal. Silence is not progress, and no
notification is not proof that a session is alive.

- **Record** every session's ID in the run log when it starts.
- **Wait in bounded stretches** of five to ten minutes. After each stretch,
  check every live session's transcript or event log and its worktree, and
  chase any that finished without a report.
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
   while CI runs. Send all valid findings to one fix session in one message,
   then one scoped re-check; findings still open after that go to the user.
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
3. **Clean up.** Remove worktrees you made after their work is merged or
   pushed. Stop live sessions. Delete temporary files.
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
