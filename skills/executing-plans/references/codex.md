# Codex orchestrator

## Limits

- Codex models only. The defaults are `gpt-6-sol` for both roles: medium
  effort to implement, xhigh to review.
- Codex can read Ref through the `Plans` MCP server. Read a Ref plan once,
  write it to `$RUN/plan.md`, and give subagents the file: a session that
  opens Ref first spends its first calls on Ref's own guidance.
- `~/.codex/config.toml` sets `[agents] max_threads` (12 here) for all live
  subagents and `max_depth` (2 here). Keep at most three implementers and
  their reviewers alive at once. Implementers and reviewers may start fast-tier
  chore agents for bounded exploration or procedural work within that limit.
  Use the run's chore model, normally `gpt-6-luna`, at an effort suited to the
  task. Do not start child implementers or reviewers to divide the lane's
  work. Each parent must finish or stop its children before its turn ends.

## Sessions

Every role uses `spawn_agent` with `fork_turns: "none"`. The message carries
the task, so the session does not need your history. A reviewer must not see
it.

```text
spawn_agent  task_name: "lane-a"      model: "gpt-6-sol"   reasoning_effort: "medium" fork_turns: "none"  message: <implementer message>
spawn_agent  task_name: "review-a"     model: "gpt-6-sol"   reasoning_effort: "xhigh"  fork_turns: "none"  message: <review prompt>
spawn_agent  task_name: "chore-ci"    model: "gpt-6-luna"  reasoning_effort: "high"  fork_turns: "none"  message: <chore>
spawn_agent  task_name: "pr-round-1"  model: "gpt-6-luna"  reasoning_effort: "medium" fork_turns: "none"  message: <PR collector prompt>
followup_task  target: "lane-a"  message: <next task, or the findings to fix>
wait_agent     timeout_ms: 600000
list_agents
send_message   target: "lane-a"  message: "One line: what are you doing now?"
interrupt_agent target: "lane-a"
```

- A lane's next task, its fixes, and its CI fixes go to the same `task_name`
  with `followup_task`.
- A lane has one reviewer `task_name` (for example `review-a`). Send each later
  task review, fix check, and PR triage to it with `followup_task`. A fresh
  reviewer is only for a plan review and the final verification.
- Start a reviewer turn only after the implementer turn ends. Both sessions
  use the lane worktree. Check that the prior turn's child agents have ended.
  Resume the implementer only after the reviewer turn ends, its child agents
  have ended, and the worktree is restored.
- Start one short-lived PR collector for the entire stack in each feedback
  round. Give it `references/pr-collector.md` and the run paths. It reports to
  files and does not replace the lane reviewers.
- Record each `task_name`, model, worktree, and state in the run log.

## Waiting and stalls

You cannot see a subagent's events, so watch its worktree.

1. Wait with `wait_agent` for at most 10 minutes at a time.
2. After each wait, run `list_agents` and, for each live lane, `git -C
   <worktree> log -1 --format=%h` and `git -C <worktree> status --porcelain |
   shasum`. Record them in the run log.
3. If a lane is still running and neither value changed for 20 minutes, ask it
   for one line with `send_message`. A long build or test run is a normal
   answer; wait up to three times as long before you act.
4. If it does not answer by the next wait, `interrupt_agent`, then
   `followup_task` with the interruption message from the main skill.
5. If the agent is gone or fails again, `spawn_agent` a new session under a
   new `task_name` with a handoff.

## Your own session

Your session can also die. The run log and git are how you continue. After
`codex resume`, read the run log, run `list_agents`, and check git in each
lane's worktree before you do anything. Agents from the old session may be
gone; start new ones with handoffs. Never re-run a task that the log and git
show as finished.

## Asking the user

Ask in a short message and end the turn. For models, list each role with its
default and two alternatives. Do not ask more than once for the same thing.

## Prompts for Codex models

- State what "done" means for the task before the work starts.
- Do not ask for progress updates or for a stop to review part way. Codex
  models can stop early when a prompt asks for either.
- Tell the implementer to stop and report when it re-reads or re-edits the
  same files without progress.
