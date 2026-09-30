---
name: model-choice
description: Use before an orchestrator dispatches its first subagent, or when the user asks which model to use for a task - names the implementer, reviewer, and chore models and efforts, uses existing choices or host models, asks only when needed, and says when to escalate
---

# Model choice

An orchestrated run has three roles. Name a model and an effort for each role
before the first dispatch. Record them where the run records its state.

| Role | Does | Session length |
| --- | --- | --- |
| Implementer | Writes code and tests. Validates all CI and review findings, fixes defects, and records proofs. | Long: one session per lane, across tasks and PRs |
| Reviewer | Reviews a plan or a frozen PR diff. Runs focused checks. May make temporary edits, then restores them. | Fresh for a plan or first pre-submission PR review; conditional later review after successful CI; reuse only for related scope. |
| Chore | Optional help with preflight, long checks, or large feedback collection. Prefer scripts for mechanical work. | As long as the chore |

## Defaults

| Orchestrator | Implementer | Reviewer | Chore |
| --- | --- | --- | --- |
| Claude Code | `gpt-6.1-sol`, high | Opus 5.5 (`opus`) xhigh | Sonnet 5.5, high |
| Codex | `gpt-6.1-sol`, high | `gpt-6.1-sol`, xhigh | `gpt-6-luna`, high |

The planner is the session that runs `writing-plans`, usually the orchestrator
itself. Default planner: Opus 5.5 in Claude Code; the session's own model in
Codex.

## Catalogue

These names are examples checked on 2026-09-29. Use the host's advertised
models and efforts. In a local CLI, `codex debug models` can check names.
Do not assume that the app or Cloud has that CLI or the same model list.

| Tier | Codex | Claude | Use for |
| --- | --- | --- | --- |
| Frontier | `gpt-6-astra` | `opus` (Opus 5.5), `fable` (Fable 5.1) | Security, concurrency, protocol state, data migration, subtle bugs, and review |
| Workhorse | `gpt-6.1-sol` | `sonnet` (Sonnet 5.5) | Most implementation |
| Fast | `gpt-6-luna` | `haiku` (Haiku 4.5) | Chores and mechanical edits |

Codex effort, from least to most: `low`, `medium`, `high`, `xhigh`, `max`, `ultra`.
Luna stops at `max`. Use `high` for implementation and review of real code.

Codex takes effort per session (`-c model_reasoning_effort=<e>` or the
`reasoning_effort` field of `spawn_agent`). For Claude Code, use supported model effort levels. The custom
`code-factory:adversarial-reviewer` definition sets `opus` and `xhigh`. Dispatch
that agent for code review. For another agent, verify its explicit or inherited
effort. Record the applied effort and any cap; a requested value is not proof
that it ran. See [Claude frontmatter](https://code.claude.com/docs/en/sub-agents#supported-frontmatter-fields)
and [effort support](https://code.claude.com/docs/en/model-config#adjust-effort-level).

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
   from prose. Use the fast tier for bounded mechanical work. Do not assume that a
   lower price per turn reduces the total cost of multi-step work.
6. When a model is unavailable or hits a usage limit, substitute only within
   existing user authorization. Explicit user model requirements take
   precedence. If the required model has no approved fallback, report the
   gap and stop dependent work. Otherwise use an available model in the
   same tier, then a permitted lower tier. Never use a fast reviewer or a
   fast implementer that works from prose. Record substitutions and actual
   effort; do not wait for a limit to reset.
7. When a model has a tight session limit, keep it for review, where it adds
   the most, and not for long implementation sessions.

## Ask only for a new decision

Use explicit user choices, approved plan choices, or the host's configured
defaults first. Do not ask again for an existing choice. Select an available
model at the needed tier when no explicit choice exists. Ask only when the
choice needs a user decision, such as a new paid provider or an unavailable
required model. Ask only about those roles. Give
the default first, marked "(Recommended)", and two alternatives with a
one-line reason each.

- Claude Code: one `AskUserQuestion` call with one question per role.
- Codex: one short message that lists each role, its default, and the
  alternatives. Then end the turn and wait.
- No user present: use existing authorization and configured host models.
  If a required choice is outside that authorization, report it and stop
  dependent work. Do not poll for a person.

## Escalate

Count failed repair attempts on the same cause, using check results. Do
not count reviewer turns or routine feedback batches as failed attempts:

1. Attempts 1-3: the same implementer session, with the findings as written.
2. Attempts 4-5: a new session one step up, with a handoff: a higher effort
   first, then the frontier tier. In Codex a higher effort needs a new session
   or a resume with the new `-c model_reasoning_effort`.
3. After attempt 5 the orchestrator rules: it takes the task itself, changes the
   approach, or requests an owner decision. A deferred blocking finding stays
   open and prevents readiness.

Record each step in the run log.

## How each orchestrator starts each model

| Orchestrator | Claude model | Codex model |
| --- | --- | --- |
| Claude Code | `Agent` with the custom code reviewer or verified inherited effort; record the applied model and effort | `codex exec` in a background shell (see `executing-plans`, Claude Code variant) |
| Codex | Not available | Native agent tools when exposed, with supported model settings |
