---
name: model-choice
description: Default models and effort levels for implementation, review, chores, code scanning, and research. Use when selecting models for agent work.
---

# Model choice

## Claude Code

| Work | Model | Effort |
| --- | --- | --- |
| Implementer (standard) | Claude Opus 5.5 (`opus`) | `high` |
| Implementer (frontier) | Claude Opus 5.5 (`opus`) | `xhigh` |
| Reviewer (standard) | `gpt-6.2-astra` | `high` |
| Reviewer (frontier) | `gpt-6.2-astra` | `xhigh` |
| Review finder | Opus 5.5 (`opus`) | `high` |
| Chore | Sonnet 5.5 (`sonnet`) | `medium` |
| Fast (code scanning and research) | Haiku (`haiku`) | Default |

Run Astra reviews in `read` mode with [calling-codex](../calling-codex/SKILL.md).

## Codex

| Work | Agent | Model | Effort |
| --- | --- | --- | --- |
| Implementer (standard) | [implementer_standard](agents/implementer_standard.toml) | `gpt-6.2-sol` | `high` |
| Implementer (frontier) | [implementer_frontier](agents/implementer_frontier.toml) | `gpt-6.2-astra` | `high` |
| Reviewer (standard) | [reviewer_standard](agents/reviewer_standard.toml) | `gpt-6.2-astra` | `xhigh` |
| Reviewer (frontier) | [reviewer_frontier](agents/reviewer_frontier.toml) | `gpt-6.2-astra` | `max` |
| Review finder | None; spawned directly | `gpt-6.2-astra` | `high` |
| Chore | [chore](agents/chore.toml) | `gpt-6-luna` | `high` |
| Fast (code scanning and research) | [fast](agents/fast.toml) | `gpt-6-luna` | `medium` |

The linked files define the named agents. To install them for a project,
run from this skill's directory and replace `/path/to/project`:

```sh
mkdir -p /path/to/project/.codex/agents
cp -n agents/*.toml /path/to/project/.codex/agents/
```

For personal agents, use `~/.codex/agents/` instead. These are the
[Codex agent locations](https://learn.chatgpt.com/docs/agent-configuration/subagents#custom-agents).

## Review passes

In an `adversarial-review` pass, finders run at the review finder row. The
one verifier runs at the standard reviewer row, or the frontier row when any
finding is CRITICAL or MAJOR.

## Effort levels

- Claude: `low`, `medium`, `high`, `xhigh`, `max`.
- Codex: `low`, `medium`, `high`, `xhigh`, `max`, `ultra`. `gpt-6-luna` stops at `max`.
