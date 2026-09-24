---
name: model-choice
description: Use before an orchestrator dispatches its first subagent, or when the user asks which model to use for a task - names the implementer, reviewer, and chore models and efforts, asks the user when the prompt does not name them, and says when to escalate
---

# Model choice

An orchestrated run has three roles. Name a model and an effort for each role
before the first dispatch. Record them where the run records its state.

| Role | Does | Session length |
| --- | --- | --- |
| Implementer | Writes code and tests. Fixes build errors and review findings. | Long: one session per lane, across tasks and PRs |
| Reviewer | Reviews a plan or a frozen diff. Runs the verifications. Triages the lane's PR comments and CI failures. Never edits. | Long: one session per lane; a fresh one for a plan review and the final verification |
| Chore | Procedural work: preflight, long verification runs, mechanical edits. | As long as the chore |

## Defaults

| Orchestrator | Implementer | Reviewer | Chore |
| --- | --- | --- | --- |
| Claude Code | `gpt-6-sol`, high | Opus 5.5 (`opus`) | `gpt-6-luna`, high |
| Codex | `gpt-6-sol`, medium | `gpt-6-sol`, xhigh | `gpt-6-luna`, high |

The planner is the session that runs `writing-plans`, usually the orchestrator
itself. Default planner: Opus 5.5 in Claude Code; the session's own model in
Codex.

## Catalogue

Checked on 2026-09-23. When a name fails, run `codex debug models`. A wrong
Codex model name fails at once with HTTP 400; nothing else is wrong.

| Tier | Codex | Claude | Use for |
| --- | --- | --- | --- |
| Frontier | `gpt-6-astra` | `opus` (Opus 5.5), `fable` (Fable 5.1) | Security, concurrency, protocol state, data migration, subtle bugs, and review |
| Workhorse | `gpt-6-sol` | `sonnet` (Sonnet 5) | Most implementation |
| Fast | `gpt-6-luna` | `haiku` (Haiku 4.5) | Chores and mechanical edits |

Effort, from least to most: `low`, `medium`, `high`, `xhigh`, `max`, `ultra`.
Luna stops at `max`. Use `high` for implementation and review of real code.
Use `low` or `medium` for mechanical work. Use `xhigh` or more only when the
plan names the risk that needs it.

Codex takes effort per session (`-c model_reasoning_effort=<e>` or the
`reasoning_effort` field of `spawn_agent`). A Claude Code subagent takes its
effort from its agent definition; the `Agent` tool chooses only the model.

## Rules

1. A Codex orchestrator uses Codex models only. A Claude Code orchestrator may
   use Claude or Codex models for any role.
2. The reviewer may be the same model as the author of what it reviews. When
   it is, give the reviewer a higher effort than the author. Its clean context
   is what makes the review independent. A different model family adds a
   second view on high-risk work; use one when the orchestrator can reach it.
3. Models the user names win. A Models section in a plan the user approved
   counts as named.
4. Pick the tier for the task, not for the plan. A task the plan marks as
   frontier gets its own implementer session at that tier.
5. Do not use the fast tier as a reviewer, or as an implementer that works
   from prose. Cheap models take two to three times the turns on multi-step
   work, so they cost more in total.
6. When a model is not available or hits a usage limit, use the next model in
   the same tier at once, then the tier below. Do not wait for a limit to
   reset. Record each substitution.
7. When a model has a tight session limit, keep it for review, where it adds
   the most, and not for long implementation sessions.

## Ask when the prompt does not name the models

If the user's prompt or an approved plan does not name all three roles, ask
before the first dispatch. Ask only about the roles that are not named. Give
the default first, marked "(Recommended)", and two alternatives with a
one-line reason each.

- Claude Code: one `AskUserQuestion` call with one question per role.
- Codex: one short message that lists each role, its default, and the
  alternatives. Then end the turn and wait.
- No user present (a scheduled or headless run): use models the user approved
  earlier for this work (the plan's Models section, or the prompt that
  scheduled the run). If there are none, post the question and stop.

## Escalate

Fix rounds on the same finding or failure:

1. Rounds 1-3: the same implementer session, with the findings as written.
2. Rounds 4-5: a new session one step up, with a handoff: a higher effort
   first, then the frontier tier. In Codex a higher effort needs a new session
   or a resume with the new `-c model_reasoning_effort`.
3. After round 5 the orchestrator rules: it takes the task itself, changes the
   approach, or parks the finding with a recorded ruling.

Record each step in the run log.

## How each orchestrator starts each model

| Orchestrator | Claude model | Codex model |
| --- | --- | --- |
| Claude Code | `Agent` tool with `model` | `codex exec` in a background shell (see `executing-plans`, Claude Code variant) |
| Codex | Not available | `spawn_agent` with `model` and `reasoning_effort` |
