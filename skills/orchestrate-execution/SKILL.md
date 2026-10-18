---
name: orchestrate-execution
description: Guide native orchestration of implementation, code review, and PR feedback with a few rules. Use only when the user explicitly invokes orchestrate-execution.
disable-model-invocation: true
---

# Orchestrate execution

Use this skill only when the user explicitly invokes it. Plan approval alone
does not invoke this skill.

Use [model-choice](../model-choice/SKILL.md) for defaults. Before dispatch,
get user approval for models and effort levels through the approved plan or
`AskUserQuestion` (or the host's equivalent). Repeated failed implementation
attempts can move standard work to the approved frontier model.

- Use native orchestration tools. Let the agent choose task order and parallel work within the approved plan.
- Give each PR one primary worktree. Use temporary worktrees for independent work, integrate before review, and delete them when finished.
- Give each PR one implementer agent. Reuse it for implementation, review fixes, and CI feedback.
- Claude Code runs Claude models, and Codex runs Codex models, as native subagents. Run an approved model from the other provider through [calling-codex](../calling-codex/SKILL.md) from Claude Code or [calling-claude](../calling-claude/SKILL.md) from Codex. A `calling-codex` or `calling-claude` lane gets feedback only between turns; stop and resume it to change direction.
- Use fast local checks and targeted tests that prove the changed behavior. Leave slow checks to CI unless repository rules require them locally.
- The orchestrator owns all pushes and runs [babysit-pr](../babysit-pr/SKILL.md) after each push. For stacks, address all feedback from a round before pushing again.
- Send review findings, CI failures, and PR feedback directly to the owning implementer. It reproduces a bug before fixing it. It fixes each finding in the same repair, MINOR ones too when the fix is small, or refutes it with evidence. It may defer a MINOR finding only with a stated reason. Only CRITICAL and MAJOR findings hold the push. Escalate unresolved requirements and decisions.

## Review

Run one [adversarial-review](../adversarial-review/SKILL.md) pass on each PR before its first push, and close its CRITICAL and MAJOR findings before that push. Run one more for each major or architectural change after that push, with the last reviewed commit as the prior commit. Give each pass a directory under `reviews/`. A BLOCKED pass has not run: fix the cause and run it again before the push.

## Run state

- Keep one run directory, `<run root>/<YYYY-MM-DD>-<repo>-<slug>-<id>/`, with `log.md`, `reviews/`, `sessions/`, and `prompts/`. The run root is `~/.agents/runs/` when you and your native agents can write there, else `$TMPDIR/agents-runs/`, and never inside a worktree.
- `log.md` records your session ID and CLI, the start time, worktrees, the PR map, agent sessions, sandbox approvals, and review passes. Before a Cloud task ends, preserve `log.md` and `reviews/` as task artifacts.
- Share paths, commits, and requirement references instead of copied context. Keep enough state to resume without repeating completed work.
- Declare completion only when required checks pass on the current commits, requirements have proof, the required review passes have run, and blocking findings and feedback are closed. Report remaining gaps clearly.
