---
name: calling-codex
description: Run Codex models from a non-Codex agent such as Claude Code. Codex sessions use native subagents instead.
---

# Calling Codex

Run a Codex model as a session you can wait on, resume, and stop, with
`scripts/codex-session.sh`. Use it only from a host that is not Codex. Each
session keeps its thread, model, effort, sandbox, and events in a run
directory, so a later parent can recover it. Exit codes, states, and recovery
are in [sessions.md](references/sessions.md).

```bash
S=<this skill's directory>/scripts/codex-session.sh
$S start  <run-dir> <name> <worktree> <model> <effort> <read|write|full> <prompt-file>
$S resume <run-dir> <name> <prompt-file> [effort]
$S status <run-dir> <name> [stall-seconds]
$S watch  <run-dir> <name> [stall-seconds] [max-seconds] [turn]
$S stop   <run-dir> <name>
```

- `start` and `resume` block until the turn ends. A main session runs them in
  the background and waits for the notification. A subagent runs them in the
  background, then repeats a foreground `watch <run-dir> <name> 1200 540 <turn>`,
  with a 600000 ms Bash timeout, until an end state.
- After each turn, read and delete `<name>.last.md`. Check its claims against
  git; models misreport steps.
- Feedback reaches a lane when its turn ends: resume with it. For a change of
  direction, `stop`, then `resume` with the new instructions. Never use
  `codex queue`: it drops the message and still exits 0.
- `read` for reviews, `write` for implementer lanes. `full` has no sandbox: use
  it only for a lane the user approved, and record the approval in the run log.
- After a restart, run `status` for every session in the run log before
  acting. Codex keeps running without your shell.
