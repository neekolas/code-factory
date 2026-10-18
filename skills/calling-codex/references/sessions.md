# Sessions

## Exit codes and states

- `start` and `resume` print `turn <n>`, then the turn's state. Exit 0:
  `done`. Exit 1: any other state. Exit 2: bad input, no codex binary, or a
  busy session, with nothing written; a `resume` while a turn runs exits 2.
  Exit 3: the session's directory is gone; start a new name with a handoff.
- `status` and `watch` print one state for the latest turn, or for `<turn>`:
  `starting`, `running`, or `busy` while it runs; `done`, `incomplete`,
  `failed`, `died`, `stalled`, or `none` after. The reason is on stderr.

## Recovery

- `resume` reuses the model and sandbox. An effort given to `resume` stays
  for later resumes. A `failed` turn whose error names the model needs a new
  session; `resume` would reuse the bad model.
- `resume` first ends every process left by the earlier turn. For `stalled`,
  run `stop` first; `stop` ends every process of the turn, including
  commands that outlived Codex.
- `died` with no thread id, or two failed resumes: start a new name with a
  handoff.

## Sandbox

- `write` can write the worktree, its git dirs (so commits from linked
  worktrees work), `~/.cargo`, `~/.cache`, and the network. It cannot write
  the run dir.
- Every mode sets `approval_policy="never"`: a command that needs approval
  fails instead of stalling the lane.
- Claude Code auto mode can soft-deny a `full` launch. The user can allow it
  once by naming the command.

## Liveness

`codex exec --json` can be silent for about 300 s while the model reasons or
polls a command, so `status` also counts Codex's rollout file as activity. A
live turn is `running` within the stall limit (default 1200 s), `busy` up to
three times that while a command is open, then `stalled`. A stderr warning
means no rollout file was found.

Do not use `--ephemeral` (it cannot be resumed) or `codex-companion task`
(it resumes only the latest thread of a workspace).
