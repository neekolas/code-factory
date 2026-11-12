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
- Give each PR one primary worktree. Its implementer may use temporary worktrees for independent helper work, integrate with merges before review, and delete them when finished. The orchestrator never cherry-picks.
- Give each PR one implementer agent. Reuse it for implementation, review fixes, CI failures, and PR feedback, review-bot comments included. Do not start a new fix agent per finding.
- Implementers enter their worktree, with `EnterWorktree` where the host has it, and edit with the host's edit tools so edit hooks apply. They never write repository files through the shell. An orchestrator pinned to one worktree cannot edit another; send small follow-up fixes to that lane's implementer.
- Claude Code runs Claude models, and Codex runs Codex models, as native subagents. Run an approved model from the other provider through [calling-codex](../calling-codex/SKILL.md) from Claude Code or [calling-claude](../calling-claude/SKILL.md) from Codex. A `calling-codex` or `calling-claude` lane gets feedback only between turns; stop and resume it to change direction.
- Use fast local checks and targeted tests that prove the changed behavior. Leave slow checks to CI unless repository rules require them locally. When CI has an API-contract compatibility check and the change touches the contract, the final checks run it locally (for example, `pnpm check:contract-compat`).
- The orchestrator owns all pushes and runs [babysit-pr](../babysit-pr/SKILL.md) after each push. For stacks, address all feedback from a round before pushing again.

## Review

Run [adversarial-review](../adversarial-review/SKILL.md) passes. Give each pass a directory under `reviews/`. A pass is small: at most five finders, a test-audit finder among them on every code PR, one verifier, and no fix agent but the owning implementer, which has the context. Tell the user before a run will use more agents. Finders get the plan requirements, the spec or ADR, and the diff, plus an optional "don't report" list; never implementer reports or fix accounts.

- Run one pass on each PR before its first push. MINOR findings do not hold the push; they go to the first babysit-pr round.
- Do not re-review fix rounds before the first push unless a fix is a new design. Then run one pass on that fix, with the commit before it as the prior commit.
- Push once the first pass's CRITICAL and MAJOR findings are closed, and every new-design fix has had a pass with none.
- When several lanes land in the same round, review them in one pass, with an area for each lane.
- After the push, run one more pass for each major or architectural change, with the last reviewed commit as the prior commit.
- A BLOCKED pass has not run: fix the cause and run it again before the push.

## Triage

Send review findings, CI failures, and PR feedback to the implementer that owns the code.

- Before routing a pass's findings, group them by the invariant they break, and write the groups at the top of the pass's `triage.md`.
- When three or more findings share a cause, or one needs a design decision, first ask a read-only advisor on the strongest approved model for one design, its risks, and the tests that prove it. Then route one fix for the group. Patches made one finding at a time interact and create the next pass's findings.
- The implementer reproduces a bug before fixing it, and fixes each finding or refutes it with evidence. It fixes small MINOR findings with the round's other fixes: no new design, and about one function. It defers the rest only with a stated reason, recorded in `log.md`.
- Each fix report names the cases its fix does not cover.
- Escalate unresolved requirements and decisions.

## End-to-end checks with real agents

When the change alters what an agent reads or does, such as prompts, guides, or sign-in flows, check it with real agents before calling it done. Automated tests usually script the agent; only a real model following the prompts shows that an agent can finish the flow.

- Run the checks after the push, on the deployed preview, batched in one run. The chore model from model-choice drives and checks the runs. Record each flow's outcome with evidence for the PR description.
- Wait for the deploy only, with a bounded wait. Do not poll CI. Before running, check that the deployed build header names the pushed commit.
- After any prompt fix, rerun the flow that failed.

Agent-facing prompts need two things that tests do not catch:

- On recent Claude models, a message longer than a line or two sent between tool calls can arrive as a hidden progress note, not visible text. When a prompt needs the agent to show the person something mid-task, such as a link and a code, ask for one short line from a template, sent before the long-running step, and have the agent start that step in the same reply. Before this change, 0 of 21 runs showed the link; after it, 6 of 6 did.
- When a prompt asks the agent to rerun or wait, say that it goes on until a terminal answer, and how long that can take. An agent told only to run it again gave up after about 10 minutes.

## Run state

- Keep one run directory, `<run root>/<YYYY-MM-DD>-<repo>-<slug>-<id>/`, with `log.md`, `reviews/`, `sessions/`, and `prompts/`. The run root is `~/.agents/runs/` when you and your native agents can write there, else `$TMPDIR/agents-runs/`, and never inside a worktree.
- `log.md` records your session ID and CLI, the start time, worktrees, the PR map, agent sessions, sandbox approvals, and review passes. Before a Cloud task ends, preserve `log.md` and `reviews/` as task artifacts.
- Share paths, commits, and requirement references instead of copied context. Keep enough state to resume without repeating completed work.
- Declare completion only when required checks pass on the current commits, requirements have proof, the required review passes and any required end-to-end checks have run, and blocking findings and feedback are closed. Report remaining gaps clearly.
