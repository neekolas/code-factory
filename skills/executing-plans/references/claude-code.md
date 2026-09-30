# Claude Code orchestrator

## Run directory

`$RUN` is the run directory from the main skill (section 1). Your session ID is
`$CLAUDE_CODE_SESSION_ID`; use its first 8 characters in the directory name.
Codex session files go in `$RUN/sessions`, and prompts in `$RUN/prompts`.

Claude and Codex sessions read Ref directly through the Plans tools. Give
them Ref IDs and section references. Each implementer reads the full approved
plan and design once, then uses section reads for tasks and updates. Follow
`working-with-ref`; do not export local mirrors or load Ref's separate
workflow guidance. Check that the selected session has `Read` access before
dispatch, including when starting a Codex CLI session.

## Claude model sessions

- Start implementers and chores with `Agent`,
  `subagent_type: "general-purpose"`, and the selected model. For a Claude code reviewer,
  dispatch `subagent_type: "code-factory:adversarial-reviewer"`, using the
  installed agent name exposed by the host. Its definition sets `model: opus`
  and `effort: xhigh`. Record the actual agent type, model, effort, and ID.
  For plan review, use a suitable custom reviewer with supported effort or
  verify the general-purpose agent's inherited effort before dispatch.
- Continue a lane with `SendMessage` to that agent ID. The session keeps its
  history. Send all CI feedback directly to the same implementer. The first
  fresh broad review finishes before PR submission. A later
  review is conditional after successful current-head CI and handled
  feedback. Do not dispatch reviewer triage or mid-loop repair reviews.
  Reuse the reviewer only for related scope while its context remains intact.
  Use a fresh reviewer for another PR or after compaction. Explore and Plan agents
  cannot be resumed and cannot write files, so never use them as implementers
  or ask them to write a report file.
- Prefer scripts for PR collection. For large collections, use one optional
  read-only general-purpose agent on the chore model. Give it `references/pr-collector.md` and the
  entire stack. It writes the report and does not triage or fix findings.
- Claude Code runs at most 20 subagents at once. Count Codex background shells
  separately; the machine's build capacity is the tighter limit.
- Lane implementers and reviewers may use the run's fast-tier chore model for
  bounded exploration or procedural work. They keep code and test edits,
  fixes, and review decisions in the lane session. All child agents must end
  before that lane turn ends.
- A lane may start a long build or test with `run_in_background: true` and end
  its turn. Claude Code resumes the lane when the command ends. The lane must
  not poll with `Monitor` or `sleep`, and must not send its final report while
  background work runs. Stop leftover watchers before the final report. Only
  the orchestrator may use `Monitor` for its own external waits.
- Verify the applied effort. Custom frontmatter can override session effort,
  but environment settings and host caps can change it. `xhigh` is supported
  for Opus 5.5 in the primary docs checked on 2026-09-30. Do not claim it ran
  when the host applied a lower level. See [subagent frontmatter](https://code.claude.com/docs/en/sub-agents#supported-frontmatter-fields)
  and [model effort](https://code.claude.com/docs/en/model-config#adjust-effort-level).
- A failed Claude subagent returns its last output. Resume it with
  `SendMessage` once. Then start a new agent with a handoff.
- If no notification arrives within a bounded wait, check the lane's event log,
  background command, and worktree (`git log -1`, `git status --porcelain`). A
  live build or test follows the main skill's longer stall limit. Do not stop
  the lane only because git has not changed. If it is stalled, stop the agent
  with `TaskStop` and start a new one with a handoff.
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
$S start "$RUN/sessions" lane-a <worktree> gpt-6.1-sol high write "$RUN/prompts/lane-a.1.md"

# Watchdog for the same session (a second background Bash). It exits and
# notifies you with done, failed, died, or stalled.
$S watch "$RUN/sessions" lane-a 1200

# Next task, or fixes, in the same session (background).
$S resume "$RUN/sessions" lane-a "$RUN/prompts/lane-a.2.md"

# A Codex reviewer: fresh broad review before first submission. Resume only for a required
# related scoped recheck. It runs focused checks, so it needs a build-capable
# sandbox. A later review waits for successful current-head CI and handled
# feedback. Use the lane worktree after the implementer's turn ends. Check HEAD and
# `git status --porcelain` before and after review. Resume the implementer
# only after the reviewer restores the worktree and ends its turn.
$S start "$RUN/sessions" review-a-pr1-1 <worktree> gpt-6-astra xhigh write "$RUN/prompts/review-a-pr1-1.3.md"
$S resume "$RUN/sessions" review-a-pr1-1 "$RUN/prompts/review-a-pr1-1.pr.md"

# State at any time, and stopping a stalled session.
$S status "$RUN/sessions" lane-a
$S stop "$RUN/sessions" lane-a
```

- Active CLI sessions receive new feedback through the durable run-directory
  inbox in `references/feedback-inbox.md`, not `SendMessage`. Write atomic
  immutable item versions as evidence arrives. The implementer reads them
  at safe checkpoints and before commit, push, and final report. Resume an
  idle session with the inbox path. Do not start a concurrent resume or
  interrupt useful work to deliver feedback. Native Claude agents continue
  to receive native messages.
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

Use existing model choices or configured defaults. Use `AskUserQuestion`
only for a decision outside existing authorization or the approved contract. Put the recommended option first.

## Optional tools

- Murmur, when its MCP server is connected: it can host long Codex sessions
  (`spawn` with `backend: "codex"`, `model`, `reasoning_effort`) and push CI
  results and PR comments as events. Record its agent slug in the run log.
- The `Workflow` tool: only when the user asks for it. It fixes the task graph
  before the work starts.
