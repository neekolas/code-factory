---
name: model-choice
description: Default models and effort levels for implementation, review, chores, code scanning, and research. Use when selecting models for agent work.
---

# Model choice

## Claude Code

| Work | Model | Effort |
| --- | --- | --- |
| Implementer (standard) | `gpt-6.1-sol` | `high` |
| Implementer (frontier) | `gpt-6-astra` | `high` |
| Reviewer (standard) | Opus 5.5 (`opus`) | `xhigh` |
| Reviewer (frontier) | Opus 5.5 (`opus`) | `max` |
| Chore | Sonnet 5.5 (`sonnet`) | `medium` |
| Fast (code scanning and research) | Haiku (`haiku`) | Default |

## Codex

| Work | Agent | Model | Effort |
| --- | --- | --- | --- |
| Implementer (standard) | [implementer_standard](agents/implementer_standard.toml) | `gpt-6.1-sol` | `high` |
| Implementer (frontier) | [implementer_frontier](agents/implementer_frontier.toml) | `gpt-6-astra` | `high` |
| Reviewer (standard) | [reviewer_standard](agents/reviewer_standard.toml) | `gpt-6.1-sol` | `xhigh` |
| Reviewer (frontier) | [reviewer_frontier](agents/reviewer_frontier.toml) | `gpt-6.1-sol` | `max` |
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

## Effort levels

- Claude: `low`, `medium`, `high`, `xhigh`, `max`.
- Codex: `low`, `medium`, `high`, `xhigh`, `max`, `ultra`. `gpt-6-luna` stops at `max`.
