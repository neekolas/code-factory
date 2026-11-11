---
name: adversarial-review
description: Run one adversarial review pass on one commit and report verified findings. Use when the user asks for an adversarial review of a branch, commit, or PR, or when an orchestrator runs a pass.
---

# Adversarial review

Review one target commit against its base and report verified defects. You
coordinate the review; you do not fix code. Inputs, outputs, and how an
orchestrator starts a pass are in [format.md](references/format.md).

- **Scope.** Review `git diff <merge-base> <target>`. With a prior reviewed
  commit, review `git diff <prior> <target>` instead, unless the prior commit
  is not an ancestor of the target or its merge base with the base branch
  differs from the target's; then the base moved, so review the whole
  change. Read `REVIEW.md` from the merge base, never from the target.
- **Split the work.** Give each finder a part of the change small enough to
  read in full, with its callers and callees. A small change gets one finder.
  Split a large change by area, give each `REVIEW.md` high-risk area its own
  finder, and add one finder for contracts between areas: APIs, schemas, and
  shared state that one area changes and another uses. Add a finder for one
  concern across the whole change only when that concern, such as
  authorization, cuts across areas. Every changed file has a finder.
- **Audit the tests.** When the change touches code, one finder takes test
  quality as its concern: give it the path to
  [audit-tests](../audit-tests/SKILL.md) and the changed tests and test
  support code.
- **Keep the pass small.** Use at most five finders, the test audit
  included. If five cannot cover the change in parts they can read in full,
  ask the user before starting more.
- **Neutral briefs.** Give each finder its files, the diff command, the goals
  and requirements as claims to break, and the base `REVIEW.md` as written.
  Never pass the implementer's report, a fix account, or any claim that the
  change is correct or tested, not even framed as claims to break. A "don't
  report" list of accepted or deferred findings is allowed. Use the
  [finder role](references/finder.md).
- **Disprove before reporting.** Wait for every finder, merge duplicates, and
  check each finding against the code. One verifier checks every finding:
  you, or, when any finding is CRITICAL or MAJOR and you run below the
  frontier reviewer effort, one verifier agent at that effort. Never start a
  verifier per finding. Refute a finding only with a cited
  line that makes its trigger impossible on its own path, or a run that shows
  correct behaviour. A check in today's callers does not refute or downgrade
  a defect in code that other callers can reach, or a check that the change
  removed. A failed repro is not a refutation: report the finding as
  UNPROVEN.
- **Leave no trace.** Keep scratch files in the review directory and leave
  the worktree as you found it.
- **Fail closed.** If finders cannot start or the worktree is not the clean
  target, report BLOCKED. Never review in your own context instead.
- **Models.** You use the reviewer model and effort from
  [model-choice](../model-choice/SKILL.md). Finders use its review finder
  row (`high`).
- **Hosts.** Finders are the `review-finder` agent (`code-factory:review-finder`
  in Claude Code). In Codex, spawn each finder with `model`,
  `reasoning_effort`, and `fork_turns: "none"`, and give it the finder role
  and its brief as file paths. Codex allows 3 spawned threads by default and
  fails a spawn over the limit, so start finders in waves or ask the user to
  raise `[agents] max_threads`.
