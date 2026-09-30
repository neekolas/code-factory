# Codex orchestrator

Use this variant in the Codex app, CLI, and Cloud. Check the tools exposed
in this session. Platform names do not guarantee a tool is available.
User instructions take precedence over the skill.

## Check capabilities

Record writable workspace and artifact paths, agent tools and limits,
available models, Ref access, GitHub access, and required build services.
Do not require `codex exec`, `~/.codex/config.toml`, a local transcript,
a desktop app, or a background shell. Use the current host's tools.

Read Ref through the connected Plans MCP tools. Plugin installation can
change their namespace. Discover by server identity and operation, not by
one hard-coded tool prefix. Give agents IDs and section references. Check
that each selected agent can read Ref before dispatch. Follow
`working-with-ref`. Do not make a local mirror to bypass missing access.

Choose models with `model-choice`. Use advertised limits rather than a fixed
thread count or depth. Reserve capacity for review and long checks. Start
parallel lanes only when the host supports them and each has its own
writable checkout. Otherwise execute lanes in order.

## Native agent sessions

When agent tools are available, use them for lane implementers and fresh
reviewers. Start with clean context (`fork_turns: "none"` when supported).
Pass the task, absolute paths, plan references, and selected model settings.
Do not pass the orchestrator's conversation to a reviewer.

The host may expose `spawn_agent`, `followup_task`, `wait_agent`,
`list_agents`, `send_message`, and `interrupt_agent`, or equivalent tools.
Call only tools that exist. Continue tasks and all CI feedback in the same
implementer session. Always finish a fresh broad review before first PR submission. Assess
a conditional second review only after current-head CI and Macroscope
succeed and feedback is handled. Do not start reviewer triage or a mid-loop
repair review. Collection scripts normally need no agent. Deliver feedback
through native messages while the implementer is active; resume its same
session when idle. Preserve item IDs, versions, and acknowledgement state.

Keep one writer per worktree. The implementer stays idle while a reviewer
uses that checkout. Before resuming implementation, confirm that the
reviewer and its chores ended and restored their temporary edits. The first review runs before submission. A later review waits for
successful current-head CI and handled feedback.

Wait through host events in calls of at most 60 seconds, or the lower host
limit. New input can change the work. Use compact status results. Do not
repeat full transcript reads or send progress requests on every wait.
After a stall, check the running command, git status, and recent commits
before interrupting. Recover from the run log without repeating completed
work. Finish or stop child agents before returning.

## When agent tools are absent

The current session can implement the tasks and validate CI findings. Keep
one implementer and use the same reports and proof records. Do not simulate
an independent reviewer by switching roles in the same conversation.

Use a connected external independent reviewer when it is authorized and
meets the plan's review scope. The first independent review must finish before submission. A PR bot
that needs an open PR cannot supply that gate. A connected independent
reviewer must meet the required scope before submission. Otherwise finish the code
and checks, report the review gap, and preserve a handoff. Do not install a
second CLI, create a user-owned chat, or launch a local daemon as a workaround.

## App and Cloud boundaries

In the app, use managed worktree tools when available and needed. Reuse a
suitable attached worktree. Attach a created PR with the app's artifact tool
when that tool is available. Open the source or review panel when it helps
the user inspect the result. Do not create separate sidebar chats for lanes.

In Cloud, use the task checkout and available services. Keep run state in a
writable host artifact or scratch path outside tracked source. Preserve the
run log, proof records, and feedback index as supported artifacts before the
task ends. Do not assume that home files, transcript files, services, or
background processes will persist in another task.

Use a connected GitHub tool if `gh` is absent. If push, comments, CI logs,
or Ref are unavailable, complete independent local work and name the
remaining action. Never label missing remote evidence PASS. If remote CI
cannot finish in the current task, report PENDING and the exact PR/head to
resume. Do not promise a later wake-up unless the user requested one and the
host supports it.

## Prompts

State completion criteria before dispatch. Do not require intermediate
acknowledgements or per-task review stops. Pass feedback directly to the
implementer with `implementer-prompt.md`. Ask for a user decision only when
existing authorization and the approved plan do not settle it.
