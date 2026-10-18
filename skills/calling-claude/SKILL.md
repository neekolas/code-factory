---
name: calling-claude
description: Run Claude models from a non-Claude agent such as Codex. Claude Code sessions use native subagents instead.
---

# Calling Claude

Run an installed, logged-in `claude -p` for one bounded job: a review, a plan review, or a task whose feedback arrives between runs. Use it only from a host that is not Claude Code. Choose the model and effort with `model-choice`. Keep the brief and every file the session reads in a run dir. Read mode:

```sh
cd <cwd> && BASH_DEFAULT_TIMEOUT_MS=3600000 BASH_MAX_TIMEOUT_MS=3600000 \
  claude -p --model <model> --effort <effort> --session-id <uuid> \
  --output-format stream-json --verbose --add-dir <run-dir> \
  --permission-mode dontAsk --allowedTools Read Grep Glob \
  'Bash(git diff:*)' 'Bash(git show:*)' 'Bash(git log:*)' 'Bash(rg:*)' \
  < <run-dir>/<name>.1.md > <run-dir>/<name>.1.jsonl 2> <run-dir>/<name>.1.err
```

- Write mode uses `--permission-mode bypassPermissions` and no allow list. Only the OS sandbox limits it.
- Pass the prompt on stdin. `--allowedTools` and `--add-dir` take every word that follows, so a prompt argument after them is read as a tool or a dir. `--session-id` needs a lowercase UUID: `uuidgen | tr A-Z a-z`.
- End the brief with: you run headless and nobody answers questions; run long commands in the foreground; do not use `&`, nohup, or disown for work your reply depends on; stop every background process before your final reply.
- After each run, read the last `result` event (`jq -c 'select(.type=="result")' <file> | tail -n 1`): `.result`, `.is_error`, `.permission_denials`. Then check the task's evidence: the expected file, commit, test output, or findings. Exit 0 alone proves nothing.
- If a `result` event has arrived and `claude` still runs, kill it: `pkill -f <uuid>`. A background task keeps `claude -p` alive.
- To resume, use the same cwd, `CLAUDE_CONFIG_DIR`, and flags, with `--resume <id>` in place of `--session-id`, and write the prompt and output to the next numbered files. There is no live input: to redirect, kill the run and resume with "Your parent stopped this task. Do not finish or retry it. New task: ...". When Claude saved no transcript under `<config dir>/projects/`, resume fails; start a new session with a handoff.
- `Not logged in` in the result or stderr means no login, or no network.
- Hooks stay on. Add `--settings '{"disableAllHooks":true}'` to turn them off.

From Codex:

- Keep polling the command until it exits. Do not end your turn while it runs: an ended turn kills it.
- The parent needs network access and the absolute Claude config dir (`$CLAUDE_CONFIG_DIR`, else `$HOME/.claude`, written out in full: Codex does not expand `~` or `$HOME`) in `writable_roots`, for example `codex exec -s workspace-write -c sandbox_workspace_write.network_access=true -c 'sandbox_workspace_write.writable_roots=["/Users/me/.claude"]'`. Without the config dir, Claude replies but saves no transcript, so resume fails. The cwd and the run dir must be writable too.
- `danger-full-access` or an escalated call runs Claude with no OS sandbox. Start such a run only when the user approved it for that session, and record the approval in the run log. An automatic approval reviewer is not user approval.
