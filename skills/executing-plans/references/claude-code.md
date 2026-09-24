# Claude Code orchestrator

## Run directory

`$RUN` is the run directory from the main skill (section 1). Your session ID is
`$CLAUDE_CODE_SESSION_ID`; use its first 8 characters in the directory name.
Codex session files go in `$RUN/sessions`, and prompts in `$RUN/prompts`.

When the plan is in Ref, export it to `$RUN/plan.md` and give subagents that
path. A session that opens Ref first reads Ref's own guidance, which cost 57 of
115 audited Codex sessions their first calls. Export again after every plan
edit.

## Claude model sessions

- Start with the `Agent` tool: `subagent_type: "general-purpose"`, the role's
  `model`, and a background run. Record the agent ID in the run log.
- Continue a lane with `SendMessage` to that agent ID. The session keeps its
  history. This holds for the lane's reviewer too: send each later review, fix
  check, and PR triage to the same reviewer agent ID. Explore and Plan agents
  cannot be resumed and cannot write files, so never use them as implementers
  or ask them to write a report file.
- For one PR feedback round, start one short-lived, read-only general-purpose
  agent on the cheap chore model. Give it `references/pr-collector.md` and the
  entire stack. It writes the report and does not triage or fix findings.
- Claude Code runs at most 20 subagents at once. Count Codex background shells
  separately; the machine's build capacity is the tighter limit.
- The effort comes from the agent definition. The `Agent` tool sets only the
  model.
- A failed Claude subagent returns its last output. Resume it with
  `SendMessage` once. Then start a new agent with a handoff.
- If no notification arrives within a bounded wait, check the lane's worktree
  (`git log -1`, `git status --porcelain`). If nothing changed for 20 minutes,
  stop the agent with `TaskStop` and start a new one with a handoff.
- For a lane in its own worktree, make the worktree with the repository's
  method (in libxmtp, the `working-with-worktrees` skill). Use `isolation:
  "worktree"` only when the repository needs no per-worktree setup.

## Codex model sessions

Use `scripts/codex-session.sh` from this skill. It stores the thread ID, the
model, the event log, and the final message for each session, so a session can
be resumed after any failure.

Do not use these for lane sessions:

- The Codex MCP server. Its calls abort after 30 minutes of silence while the
  session keeps working.
- `codex-companion task` (`/codex:rescue`). It resumes only the most recent
  thread, so two lanes cannot each resume their own.
- `--ephemeral`. It stores no session, so it cannot be resumed.

Write each prompt to a file with the `Write` tool, for example
`$RUN/prompts/lane-a.3.md`. Then:

```bash
S="<skill dir>/scripts/codex-session.sh"   # <skill dir>: see the main SKILL.md

# Start a lane session (Bash with run_in_background: true).
$S start "$RUN/sessions" lane-a <worktree> gpt-6-sol high write "$RUN/prompts/lane-a.1.md"

# Watchdog for the same session (a second background Bash). It exits and
# notifies you with done, failed, died, or stalled.
$S watch "$RUN/sessions" lane-a 1200

# Next task, or fixes, in the same session (background).
$S resume "$RUN/sessions" lane-a "$RUN/prompts/lane-a.2.md"

# A Codex reviewer, when the run uses one: one name per lane, started at the
# lane's first review and resumed for each later task, fix check, and PR triage.
# It builds and runs the proofs, so it uses the implementer's sandbox; check
# `git status --porcelain` before and after.
$S start "$RUN/sessions" review-a <worktree> gpt-6-sol xhigh write "$RUN/prompts/review-a.3.md"
$S resume "$RUN/sessions" review-a "$RUN/prompts/review-a.pr.md"

# State at any time, and stopping a stalled session.
$S status "$RUN/sessions" lane-a
$S stop "$RUN/sessions" lane-a
```

- Wait on the background `watch` command, not on a `Monitor` with a time
  limit: a 30-minute Monitor expires and must be re-armed, which wakes you for
  nothing.
- In auto mode, the permission classifier can refuse `codex exec`. If it
  does, ask the user to allow the command once; do not switch to a relay.
- `start` and `resume` end when the turn ends and print the state. Read
  `$RUN/sessions/<name>.last.md` for the session's report.
- Sandbox modes: `write` allows the worktree, the common git directory,
  `~/.cargo`, `~/.cache`, and the network. `read` suits a plan review that
  runs no build. `full` has no sandbox; use it only when preflight showed that
  the repository's commands need it (Docker, the Nix daemon socket).
- After Claude Code restarts, its background shells are gone but `codex exec`
  usually keeps running. Run `status` for every session in the run log first.
  `running` or `busy`: re-arm `watch` only; a `resume` would start a second
  turn on the same thread. `done`: read `last.md`.
- On `stalled`: run `stop`, then `resume` with the interruption message from
  the main skill. On `died` or `failed`: `resume` the same way. After two
  failed resumes, `start` a new name with a handoff.
- `resume` exits 3 at once when the session's directory is gone. Do not retry:
  `start` a new name with a handoff, in an existing worktree.
- `resume` reuses the session's model; without it, Codex falls back to the
  configured default. To raise the effort of a live lane, pass it as the last
  argument: `$S resume "$RUN/sessions" lane-a "$RUN/prompts/fix.md" xhigh`.
- A reviewer's report reaches you in `last.md`. It is a transport file, not a
  saved review: read it, then delete it. Deleting it does not change the
  session's `done` state.

## Asking the user

Use `AskUserQuestion` for the model choice and for rulings that change scope
or a contract. Put the recommended option first.

## Optional tools

- Murmur, when its MCP server is connected: it can host long Codex sessions
  (`spawn` with `backend: "codex"`, `model`, `reasoning_effort`) and push CI
  results and PR comments as events. Record its agent slug in the run log.
- The `Workflow` tool: only when the user asks for it. It fixes the task graph
  before the work starts.
