#!/usr/bin/env bash
# Start, watch, resume, and stop one Codex session for executing-plans.
#
#   codex-session.sh start  <run-dir> <name> <worktree> <model> <effort> <read|write|full> <prompt-file>
#   codex-session.sh resume <run-dir> <name> <prompt-file> [effort]
#   codex-session.sh status <run-dir> <name> [stall-seconds]
#   codex-session.sh watch  <run-dir> <name> [stall-seconds]
#   codex-session.sh stop   <run-dir> <name>
#
# start and resume block until the turn ends; run them in the background.
# Files per session in <run-dir>: <name>.{thread,cwd,model,sandbox,pid,offset,exit,events.jsonl,last.md,stderr}.
# status prints one word for the latest turn only: starting, running, busy,
# done, failed, died, stalled, or none.
set -euo pipefail

cmd=${1:?command}; run=${2:?run-dir}; name=${3:?name}; shift 3
mkdir -p "$run"
base="$run/$name"
STARTUP_S=${CODEX_SESSION_STARTUP_S:-120}   # a turn with no event yet counts as starting for this long
STOP_S=${CODEX_SESSION_STOP_S:-30}       # SIGTERM grace period before SIGKILL

sandbox_args() {
  case "$1" in
    read) sbx=(-c 'sandbox_mode="read-only"') ;;
    full) sbx=(--dangerously-bypass-approvals-and-sandbox) ;;
    write)
      # Commits in a worktree write to the common git dir; builds write caches.
      local common
      common=$(cd "$(cat "$base.cwd")" && git rev-parse --path-format=absolute --git-common-dir)
      sbx=(-c 'sandbox_mode="workspace-write"'
        -c 'sandbox_workspace_write.network_access=true'
        -c "sandbox_workspace_write.writable_roots=[\"$common\",\"$HOME/.cargo\",\"$HOME/.cache\"]")
      ;;
    *) echo "unknown sandbox: $1" >&2; exit 2 ;;
  esac
}

mtime() {
  local value
  value=$(stat -f %m "$1" 2>/dev/null) || value=
  if [[ $value =~ ^[0-9]+$ ]]; then
    printf '%s\n' "$value"
  else
    stat -c %Y "$1"
  fi
}

# Events of the latest turn only: lines after the offset recorded at its start.
turn_events() {
  local off; off=$(cat "$base.offset" 2>/dev/null || echo 0)
  tail -n +"$((off + 1))" "$base.events.jsonl" 2>/dev/null || true
}

run_codex() {
  # The prompt file is stdin. It must be on the background command itself:
  # bash gives a background job /dev/null. Never use an open pipe; codex exec
  # can hang on a pipe that nobody writes to.
  local prompt=$1; shift
  touch "$base.events.jsonl"
  wc -l <"$base.events.jsonl" | tr -d ' ' >"$base.offset"
  rm -f "$base.last.md" "$base.exit"
  date +%s >"$base.started"
  "$@" <"$prompt" >>"$base.events.jsonl" 2>>"$base.stderr" &
  local pid=$! rc=0
  echo "$pid" >"$base.pid"
  wait "$pid" || rc=$?
  echo "$rc" >"$base.exit"
  if [ ! -s "$base.thread" ]; then
    turn_events | jq -r 'select(.type=="thread.started") | .thread_id' | head -n 1 >"$base.thread"
  fi
  status
}

alive() { [ -s "$base.pid" ] && [ ! -e "$base.exit" ] && kill -0 "$(cat "$base.pid")" 2>/dev/null; }

kill_tree() {
  local child
  for child in $(pgrep -P "$1"); do kill_tree "$child" "$2"; done
  kill "-$2" "$1" 2>/dev/null || true
}

# Commands started in the latest turn that have not completed. Codex keeps
# helper processes alive, so child processes cannot show a running build.
open_commands() {
  turn_events | jq -s '(map(.type) | rindex("turn.started")) as $t | .[($t // 0):]
    | map(select(.item.type? == "command_execution"))
    | group_by(.item.id) | map(select(all(.type == "item.started"))) | length' 2>/dev/null || echo 0
}

status() {
  local stall=${1:-1200} last age now
  [ -e "$base.offset" ] || { echo none; return; }
  now=$(date +%s)
  last=$(turn_events | jq -r 'select(.type|test("^(turn\\.|error$)")) | .type' 2>/dev/null | tail -n 1)
  if alive; then
    if [ -z "$(turn_events | head -c 1)" ]; then
      age=$(( now - $(cat "$base.started" 2>/dev/null || echo "$now") ))
      if [ "$age" -lt "$STARTUP_S" ]; then echo starting; else echo stalled; fi
      return
    fi
    age=$(( now - $(mtime "$base.events.jsonl") ))
    if [ "$age" -lt "$stall" ]; then echo running
    elif [ "$(open_commands)" -gt 0 ] && [ "$age" -lt $(( stall * 3 )) ]; then echo busy
    else echo stalled; fi
  elif [ -e "$base.started" ] && [ ! -e "$base.exit" ] && [ ! -s "$base.pid" ]; then
    # start or resume has not launched codex yet; the launcher may have died.
    age=$(( now - $(cat "$base.started") ))
    if [ "$age" -lt "$STARTUP_S" ]; then echo starting; else echo died; fi
  else
    case "$last" in
      turn.completed) echo "done" ;;   # reading and deleting last.md must not change this
      turn.failed|error) echo failed ;;
      *) echo died ;;
    esac
  fi
}

case "$cmd" in
  start)
    worktree=${1:?worktree}; model=${2:?model}; effort=${3:?effort}; mode=${4:?sandbox}; prompt=${5:?prompt-file}
    [ -e "$base.cwd" ] && { echo "session $name exists; use resume" >&2; exit 2; }
    date +%s >"$base.started"
    (cd "$worktree" && pwd) >"$base.cwd"; echo "$mode" >"$base.sandbox"; echo "$model" >"$base.model"
    cd "$(cat "$base.cwd")"
    sandbox_args "$mode"
    run_codex "$prompt" codex exec --json -m "$model" -c model_reasoning_effort="$effort" \
      "${sbx[@]}" -o "$base.last.md" -
    ;;
  resume)
    prompt=${1:?prompt-file}; effort=${2:-}
    alive && { echo "session $name is still running" >&2; exit 2; }
    # The .thread file is written when a turn ends; after a crash, read the log.
    thread=$(cat "$base.thread" 2>/dev/null || true)
    [ -n "$thread" ] || thread=$(jq -r 'select(.type=="thread.started") | .thread_id' "$base.events.jsonl" 2>/dev/null | head -n 1)
    [ -n "$thread" ] || { echo "no thread id for $name" >&2; exit 2; }
    cd "$(cat "$base.cwd")"   # resume has no --cd; it must run from the original directory
    # Without -m, resume falls back to the configured default model.
    extra=(); [ -s "$base.model" ] && extra=(-m "$(cat "$base.model")")
    [ -n "$effort" ] && extra+=(-c model_reasoning_effort="$effort")
    sandbox_args "$(cat "$base.sandbox")"
    rm -f "$base.pid"
    run_codex "$prompt" codex exec resume "$thread" --json ${extra[@]+"${extra[@]}"} \
      "${sbx[@]}" -o "$base.last.md" -
    ;;
  status) status "${1:-1200}" ;;
  watch)
    stall=${1:-1200}; waited=0
    while :; do
      s=$(status "$stall")
      case "$s" in
        running|busy|starting) sleep 30 ;;
        none)   # the watcher can start before `start` writes anything
          [ "$waited" -ge "$STARTUP_S" ] && { echo none; exit 0; }
          sleep 5; waited=$((waited + 5)) ;;
        *) echo "$s"; exit 0 ;;
      esac
    done
    ;;
  stop)
    if alive; then
      pid=$(cat "$base.pid")
      kill_tree "$pid" TERM
      for _ in $(seq "$STOP_S"); do alive || break; sleep 1; done
      if alive; then kill_tree "$pid" KILL; sleep 1; fi
      if kill -0 "$pid" 2>/dev/null; then echo "could not stop $name (pid $pid)" >&2; exit 1; fi
      [ -e "$base.exit" ] || echo 143 >"$base.exit"
    fi
    status
    ;;
  *) echo "unknown command: $cmd" >&2; exit 2 ;;
esac
