#!/usr/bin/env bash
# Run Codex CLI sessions that can be watched, resumed, and stopped.
#
#   codex-session.sh start  <run-dir> <name> <worktree> <model> <effort> <read|write|full> <prompt-file>
#   codex-session.sh resume <run-dir> <name> <prompt-file> [effort]
#   codex-session.sh status <run-dir> <name> [stall-seconds]
#   codex-session.sh watch  <run-dir> <name> [stall-seconds] [max-seconds] [turn]
#   codex-session.sh stop   <run-dir> <name>
#
# start and resume exit 0 on done and 1 on any other state; status and watch
# exit 0. Any command exits 2 on bad input, a busy session, or no
# codex binary; 3 resume found the session's directory gone.
set -euo pipefail

STARTUP_S=${CODEX_SESSION_STARTUP_S:-120}  # a live turn with no event counts as starting this long
STOP_S=${CODEX_SESSION_STOP_S:-30}         # SIGTERM grace period before SIGKILL
POLL_S=${CODEX_SESSION_POLL_S:-30}         # how often watch, start, and resume check the turn
TRACK_S=${CODEX_SESSION_TRACK_S:-2}        # how often the runner records codex's processes
STALL_S=1200                               # default stall limit in seconds
CODEX_DIR=${CODEX_HOME:-$HOME/.codex}
MARK_VAR=CODEX_SESSION_MARK                # every process codex starts inherits it

die2() { printf 'codex-session: %s\n' "$*" >&2; exit 2; }
usage() { sed -n '4,8p' "$0" | sed 's/^# *//' >&2; exit 2; }
is_num() { case $1 in '' | *[!0-9]*) return 1 ;; esac; }

cmd=${1:-}; run=${2:-}; name=${3:-}
[ -n "$cmd" ] && [ -n "$run" ] && [ -n "$name" ] || usage
shift 3
case $run in /*) ;; *) die2 "run dir must be an absolute path: $run" ;; esac
case $name in .* | *[!A-Za-z0-9._-]*) die2 "session name may use only letters, digits, '.', '_', and '-': $name" ;; esac
base=$run/$name
lock=$base.lock
self=$(CDPATH='' cd "$(dirname "$0")" && pwd)/$(basename "$0")

find_codex() {
  local app=${CODEX_APP_BIN:-/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex} c=
  if [ -n "${CODEX_BIN:-}" ]; then
    [ -f "$CODEX_BIN" ] && [ -x "$CODEX_BIN" ] && c=$CODEX_BIN
  elif c=$(command -v codex 2>/dev/null) && [ -x "$c" ]; then :
  elif [ -f "$app" ] && [ -x "$app" ]; then c=$app
  else c=
  fi
  [ -n "$c" ] || die2 "no runnable codex binary. Checked CODEX_BIN (${CODEX_BIN:-unset}), codex on PATH, and CODEX_APP_BIN ($app)"
  case $c in /*) ;; *) c=$PWD/$c ;; esac
  printf '%s\n' "$c"
}

check_prompt() {
  case $1 in /*) ;; *) die2 "prompt path must be absolute: $1" ;; esac
  [ -f "$1" ] && [ -r "$1" ] || die2 "prompt file is not readable: $1"
}

toml_str() { local s=${1//\\/\\\\}; printf '"%s"' "${s//\"/\\\"}"; }

sandbox_args() {  # <mode> <cwd>: sets sbx
  case $1 in
    read) sbx=(-c 'sandbox_mode="read-only"' -c 'approval_policy="never"') ;;
    full) sbx=(--dangerously-bypass-approvals-and-sandbox -c 'approval_policy="never"') ;;
    write)
      # A commit in a linked worktree writes to the common git dir and to the
      # worktree's own git dir; Codex makes both read-only unless listed.
      # Builds write caches.
      local common gitdir roots
      common=$(git -C "$2" rev-parse --path-format=absolute --git-common-dir 2>/dev/null) &&
        gitdir=$(git -C "$2" rev-parse --absolute-git-dir 2>/dev/null) ||
        die2 "write mode needs a git worktree: $2"
      roots=$(toml_str "$common")
      [ "$gitdir" = "$common" ] || roots="$roots,$(toml_str "$gitdir")"
      sbx=(-c 'sandbox_mode="workspace-write"' -c 'approval_policy="never"'
        -c 'sandbox_workspace_write.network_access=true'
        -c "sandbox_workspace_write.writable_roots=[$roots,$(toml_str "$HOME/.cargo"),$(toml_str "$HOME/.cache")]")
      ;;
    *) die2 "unknown sandbox mode: $1 (use read, write, or full)" ;;
  esac
}

footer() {
  cat <<EOF

---
Rules from codex-session.sh, which runs this session:
- Wait until each command you start exits and you have seen its exit code. If a tool call returns while the command still runs, keep polling that command. Never end your turn while a command you started is still running.
EOF
}

mtime() {
  local v
  v=$(stat -f %m "$1" 2>/dev/null) || v=
  case $v in '' | *[!0-9]*) v=$(stat -c %Y "$1" 2>/dev/null) || v=0 ;; esac
  printf '%s\n' "$v"
}

# A PID names the same process only while its start time and command line
# still match; PIDs are reused.
proc_start() { LC_ALL=C ps -o lstart= -p "$1" 2>/dev/null | awk '{ $1 = $1; print }' || true; }
proc_cmd() { ps -ww -o command= -p "$1" 2>/dev/null || true; }
same_proc() {  # <pid> <start time> <text in its command line>
  [ -n "$1" ] && [ -n "$2" ] && [ "$(proc_start "$1")" = "$2" ] || return 1
  case $(proc_cmd "$1") in *"$3"*) return 0 ;; esac
  return 1
}
ident() { printf '%s\n%s\n' "$1" "$(proc_start "$1")"; }
ident_alive() {  # <file holding pid and start time> <text in the command line>
  local pid='' start=''
  { IFS= read -r pid && IFS= read -r start; } 2>/dev/null <"$1" || return 1
  same_proc "$pid" "$start" "$2"
}
codex_alive() { ident_alive "$base.pid" "$base.last.md"; }
runner_alive() { ident_alive "$lock/owner" " _run "; }

take_lock() {  # atomic mkdir; a lock whose holder is gone is moved aside first
  local seen _
  mkdir -p "$run"
  for _ in 1 2 3; do
    if mkdir "$lock" 2>/dev/null; then
      ident $$ >"$lock/owner.tmp" && mv "$lock/owner.tmp" "$lock/owner"
      return 0
    fi
    seen=$(cat "$lock/owner" 2>/dev/null || true)
    if [ -z "$seen" ]; then
      [ $(($(date +%s) - $(mtime "$lock"))) -ge 10 ] || return 1  # its holder is still writing it
    elif runner_alive; then
      return 1
    fi
    if mv "$lock" "$lock.stale.$$" 2>/dev/null; then
      if [ "$(cat "$lock.stale.$$/owner" 2>/dev/null || true)" = "$seen" ]; then
        rm -rf "$lock.stale.$$"
      else  # another caller took the lock in between: give it back
        [ -e "$lock" ] || mv "$lock.stale.$$" "$lock"
        return 1
      fi
    fi
  done
  return 1
}
release_lock() {
  if [ "$(sed -n 1p "$lock/owner" 2>/dev/null || true)" = "$$" ]; then rm -rf "$lock"; fi
}

turn_events() {  # events of the latest turn: lines after the offset recorded at its start
  local off
  off=$(cat "$base.offset" 2>/dev/null || echo 0)
  tail -n +"$((off + 1))" "$base.events.jsonl" 2>/dev/null || true
}
thread_id() {
  local t=''
  [ ! -s "$base.thread" ] || t=$(cat "$base.thread")
  [ -n "$t" ] || t=$(jq -R -r 'fromjson? | select(.type == "thread.started") | .thread_id' \
    "$base.events.jsonl" 2>/dev/null | head -n 1 || true)
  printf '%s\n' "$t"
}
# `codex exec --json` prints nothing while the model reasons or polls a
# command, for up to about 300 s. Codex's own rollout file still grows.
rollout_mtime() {  # <thread>: newest mtime of its rollout files, empty when none
  local f m best=''
  for f in "$CODEX_DIR"/sessions/*/*/*/rollout-*"$1".jsonl; do
    [ -f "$f" ] || continue
    m=$(mtime "$f")
    if [ -z "$best" ] || [ "$m" -gt "$best" ]; then best=$m; fi
  done
  printf '%s' "$best"
}
# Commands started in the latest turn that have not completed.
open_commands() {
  local n
  n=$(turn_events | jq -R -s '[split("\n")[] | fromjson?] | (map(.type) | rindex("turn.started")) as $t
    | .[($t // 0):] | map(select(.item.type? == "command_execution")) | group_by(.item.id)
    | map(select(all(.type == "item.started"))) | length' 2>/dev/null || true)
  printf '%s\n' "${n:-0}"
}
last_turn_event() {
  turn_events | jq -R -r 'fromjson? | select((.type // "") | test("^(turn\\.|error$)")) | .type' \
    2>/dev/null | tail -n 1 || true
}
failure_reason() {  # the turn's last error message; Codex sometimes nests one as a JSON string
  turn_events | jq -R -r 'fromjson? | select(.type == "turn.failed" or .type == "error")
    | ((.error | if type == "object" then .message else . end) // .message // "" | tostring) as $m
    | (((try ($m | fromjson) catch null)
        | if type == "object" then (.error | if type == "object" then .message else . end) // .message // .detail
          else null end) // $m)
    | tostring | gsub("\\s+"; " ")' 2>/dev/null | tail -n 1 || true
}

turn_live() {
  [ ! -e "$base.exit" ] || return 1
  codex_alive && return 0
  [ ! -s "$base.pid" ] || return 1  # codex ran and is gone
  runner_alive                      # the runner has not launched codex yet
}

STATE=''; REASON=''; WARNED=''
compute_status() {  # <stall>: sets STATE and REASON for the latest turn
  local stall=$1 now age act roll th last
  STATE=''; REASON=''
  [ -e "$base.offset" ] || { STATE=none; return 0; }
  now=$(date +%s)
  if turn_live; then
    if [ -z "$(turn_events | head -c 1)" ]; then
      age=$((now - $(cat "$base.started" 2>/dev/null || echo "$now")))
      if [ "$age" -lt "$STARTUP_S" ]; then STATE=starting
      else STATE=stalled; REASON="no event from codex after ${age}s"; fi
      return 0
    fi
    act=$(mtime "$base.events.jsonl")
    th=$(thread_id); roll=''
    [ -z "$th" ] || roll=$(rollout_mtime "$th")
    if [ -z "$roll" ]; then
      [ -n "$WARNED" ] || printf 'codex-session: warning: no rollout file for thread %s under %s/sessions; liveness uses events.jsonl only\n' \
        "${th:-unknown}" "$CODEX_DIR" >&2
      WARNED=1
    elif [ "$roll" -gt "$act" ]; then
      act=$roll
    fi
    age=$((now - act))
    if [ "$age" -lt "$stall" ]; then STATE=running
    elif [ "$(open_commands)" -gt 0 ] && [ "$age" -lt $((stall * 3)) ]; then STATE=busy
    else STATE=stalled; REASON="no activity for ${age}s"; fi
    return 0
  fi
  last=$(last_turn_event)
  case $last in
    turn.completed)
      if [ "$(open_commands)" -gt 0 ]; then
        STATE=incomplete
        REASON="the turn ended while a command it started was still running; resume and ask for that command to be rerun until it exits"
      else STATE="done"; fi ;;
    turn.failed | error) STATE=failed; REASON=$(failure_reason) ;;
    *)
      STATE=died
      if [ -e "$base.exit" ]; then REASON="codex exited $(cat "$base.exit") before the turn ended; see $base.stderr"
      else REASON="the runner and codex stopped before the turn ended; see $base.stderr"; fi ;;
  esac
}
print_state() {
  printf '%s\n' "$STATE"
  [ -z "$REASON" ] || printf 'codex-session: %s\n' "$REASON" >&2
}

watch_turn() {  # <stall> <max-seconds or 0> [turn]: poll until the turn ends, then print its state
  local stall=$1 max=$2 want=${3:-} t0 now cur nap
  t0=$(date +%s)
  while :; do
    cur=$(cat "$base.turn" 2>/dev/null || echo 0)
    if [ -n "$want" ] && [ "$cur" -lt "$want" ]; then STATE=none; REASON=''  # not started yet
    else compute_status "$stall"; fi
    now=$(date +%s)
    case $STATE in
      starting | running | busy) nap=$POLL_S ;;
      none)
        [ $((now - t0)) -lt "$STARTUP_S" ] || break
        nap=5; [ "$POLL_S" -ge 5 ] || nap=$POLL_S ;;
      *) break ;;
    esac
    if [ "$max" -gt 0 ]; then
      [ $((now - t0)) -lt "$max" ] || break
      [ $((t0 + max - now)) -ge "$nap" ] || nap=$((t0 + max - now))
    fi
    sleep "$nap"
  done
  print_state
}

marked_pids() {  # processes that carry this session's marker
  local mark
  mark=$(cat "$base.mark" 2>/dev/null || true)
  [ -n "$mark" ] || return 0
  if [ -r /proc/self/environ ]; then
    grep -lsaFxz "$MARK_VAR=$mark" /proc/[0-9]*/environ 2>/dev/null | awk -F/ '{ print $3 }' || true
  else  # macOS shows the environment of non-platform binaries only
    # Pass only the value: macOS awk rewrites `-v m=value` in its own argv,
    # which would make ps show this awk with the whole marker.
    ps -E -A -ww -o pid= -o command= 2>/dev/null |
      awk -v var="$MARK_VAR" -v mark="$mark" '{ for (i = 2; i <= NF; i++) if ($i == var "=" mark) { print $1; next } }' || true
  fi
}
ps_table() { LC_ALL=C ps -A -o pid= -o ppid= -o pgid= -o stat= -o lstart= 2>/dev/null || true; }

# Every live process of this session: codex, processes the runner recorded,
# and marked processes, each with its process group and its descendants.
# Codex starts each command in its own process group, and a command can
# outlive codex, so a walk from the codex PID alone misses them.
session_pids() {
  local seeds keep=''
  seeds=$(marked_pids | tr '\n' ' ')
  if codex_alive; then seeds="$seeds $(sed -n 1p "$base.pid")"; fi
  if runner_alive; then keep=$(sed -n 1p "$lock/owner"); fi
  ps_table | awk -v seeds="$seeds" -v known="$base.procs" -v self=$$ -v keep="$keep" '
    BEGIN {
      n = split(seeds, s, " "); for (i = 1; i <= n; i++) seed[s[i]] = 1
      while ((getline line < known) > 0) { split(line, f, " "); rec[f[1]] = f[3] " " f[4] " " f[5] " " f[6] " " f[7] }
    }
    $4 !~ /^Z/ {
      ppid[$1] = $2; pg[$1] = $3
      if (($1 in rec) && rec[$1] == ($5 " " $6 " " $7 " " $8 " " $9)) seed[$1] = 1
    }
    END {
      for (p in seed) if (p in ppid) { take[p] = 1; if (pg[p] > 1) grp[pg[p]] = 1 }
      for (p in ppid) if (pg[p] in grp) take[p] = 1
      do {
        changed = 0
        for (p in ppid) if (!(p in take) && (ppid[p] in take)) { take[p] = 1; changed = 1 }
      } while (changed)
      for (p in take) if (p != self && p != keep) print p
    }' || true
}
stop_processes() {  # SIGTERM, then SIGKILL after STOP_S; true when none is left
  local pids _
  pids=$(session_pids)
  [ -n "$pids" ] || return 0
  # shellcheck disable=SC2086  # one argument per PID
  kill -TERM $pids 2>/dev/null || true
  for _ in $(seq "$STOP_S"); do
    sleep 1
    pids=$(session_pids)
    [ -n "$pids" ] || return 0
  done
  # shellcheck disable=SC2086
  kill -KILL $pids 2>/dev/null || true
  sleep 1
  [ -z "$(session_pids)" ]
}

track() {  # <codex pid>: append codex's descendants (pid pgid start) to <name>.procs while it runs
  local root=$1
  while kill -0 "$root" 2>/dev/null; do
    ps_table | awk -v root="$root" -v known="$base.procs" '
      BEGIN { while ((getline line < known) > 0) { split(line, f, " "); seen[f[1] " " f[3] " " f[4] " " f[5] " " f[6] " " f[7]] = 1 } }
      $4 !~ /^Z/ { ppid[$1] = $2; pg[$1] = $3; st[$1] = $5 " " $6 " " $7 " " $8 " " $9 }
      END {
        take[root] = 1
        do {
          changed = 0
          for (p in ppid) if (!(p in take) && (ppid[p] in take)) { take[p] = 1; changed = 1 }
        } while (changed)
        for (p in take) if (p != root && (p in st) && !((p " " st[p]) in seen)) print p, pg[p], st[p]
      }' >>"$base.procs" || true
    sleep "$TRACK_S"
  done
}

runner_fail() { printf 'error %s %s\n' "$1" "$2"; exit "$1"; }

# The detached runner: one per turn. Until the handshake line `turn <n> <pid>`,
# its stdout and stderr are the caller's pipe; it then keeps that pipe open on
# fd 4, so the caller sees EOF when the runner exits.
runner() {
  local op=$1 cwd model effort mode prompt codex thread='' n mark cpid tpid rc
  local -a args
  shift
  take_lock || runner_fail 2 "session $name is busy: its turn is still running, or another start or resume holds it"
  trap release_lock EXIT
  if [ "$op" = start ]; then
    cwd=$1 model=$2 effort=$3 mode=$4 prompt=$5 codex=$6
    [ ! -e "$base.cwd" ] || runner_fail 2 "session $name exists; use resume"
    n=1
  else
    prompt=$1 effort=$2 codex=$3
    [ -e "$base.cwd" ] || runner_fail 2 "no session $name in $run"
    ! codex_alive || runner_fail 2 "session $name is still running; wait for it, or stop it"
    cwd=$(cat "$base.cwd")
    [ -d "$cwd" ] || runner_fail 3 "session $name cannot resume: its directory $cwd is gone. Start a new session with a handoff."
    thread=$(thread_id)
    [ -n "$thread" ] || runner_fail 2 "no thread id for $name: codex never started this session; start a new session"
    model=$(cat "$base.model"); mode=$(cat "$base.sandbox")
    [ -n "$effort" ] || effort=$(cat "$base.effort" 2>/dev/null || true)
    # A command from an earlier turn must not run next to the new one.
    stop_processes || runner_fail 1 "could not stop the processes left by an earlier turn of $name"
    n=$(($(cat "$base.turn" 2>/dev/null || echo 1) + 1))
  fi
  sandbox_args "$mode" "$cwd"
  { cat "$prompt" && printf '\n' && footer; } >"$base.prompt.tmp" ||
    { rm -f "$base.prompt.tmp"; runner_fail 2 "cannot read prompt file $prompt"; }

  # From here on the session files change.
  if [ "$op" = start ]; then
    printf '%s\n' "$cwd" >"$base.cwd"; printf '%s\n' "$model" >"$base.model"; printf '%s\n' "$mode" >"$base.sandbox"
    printf 'cs-%s-%s-%s\n' "$(date +%s)" "$$" "$RANDOM" >"$base.mark"
  fi
  printf '%s\n' "$effort" >"$base.effort"
  rm -f "$base.exit" "$base.last.md" "$base.pid"
  : >"$base.procs"
  touch "$base.events.jsonl"
  wc -l <"$base.events.jsonl" | tr -d ' ' >"$base.offset"
  date +%s >"$base.started"
  mv "$base.prompt.tmp" "$base.prompt"
  printf '%s\n' "$n" >"$base.turn.tmp" && mv "$base.turn.tmp" "$base.turn"
  printf 'turn %s %s\n' "$n" "$$"
  exec 4>&1 >/dev/null 2>>"$base.stderr"

  cd "$cwd"  # exec resume has no --cd; the session must resume from its directory
  mark=$(cat "$base.mark")
  if [ "$op" = start ]; then args=(exec); else args=(exec resume "$thread"); fi
  # Without -m and the effort, resume falls back to the configured defaults.
  args+=(--json -m "$model")
  [ -z "$effort" ] || args+=(-c "model_reasoning_effort=$effort")
  args+=("${sbx[@]}" -o "$base.last.md" -)
  # The prompt file is stdin; never an open pipe. codex leads its own process
  # group, and every process it starts inherits the session marker.
  env "$MARK_VAR=$mark" perl -e 'setpgrp(0, 0); exec { $ARGV[0] } @ARGV or die "codex-session: cannot run $ARGV[0]: $!\n"' \
    "$codex" "${args[@]}" <"$base.prompt" >>"$base.events.jsonl" 2>>"$base.stderr" 4>&- &
  cpid=$!
  ident "$cpid" >"$base.pid.tmp" && mv "$base.pid.tmp" "$base.pid"
  track "$cpid" 4>&- &
  tpid=$!
  rc=0; wait "$cpid" || rc=$?
  kill "$tpid" 2>/dev/null || true
  [ -s "$base.thread" ] || thread_id >"$base.thread"
  printf '%s\n' "$rc" >"$base.exit"
}

launch() {  # <runner args>: detach the runner, relay its handshake, wait for the turn
  local line='' rc n rpid rstart
  # perl forks and the child starts a new session: the runner is in neither
  # the caller's process group nor its process tree.
  exec 3< <(perl -MPOSIX -e 'exit 0 if fork; POSIX::setsid(); exec { $ARGV[0] } @ARGV or die "codex-session: cannot start the runner: $!\n"' \
    "$BASH" "$self" _run "$run" "$name" "$@" </dev/null 2>&1)
  IFS= read -r line <&3 || true
  case $line in
    "turn "*) ;;
    "error "*) rc=${line#error }; printf 'codex-session: %s\n' "${rc#* }" >&2; exit "${rc%% *}" ;;
    *) { [ -z "$line" ] || printf '%s\n' "$line"; cat <&3; } >&2
       echo "codex-session: the runner stopped before the turn started" >&2; exit 1 ;;
  esac
  read -r _ n rpid <<<"$line"
  printf 'turn %s\n' "$n"
  rstart=$(proc_start "$rpid")
  # Wait for EOF (the runner exited), and check for a stall at each poll.
  # bash 3.2 returns 1 for both EOF and a read timeout.
  while :; do
    rc=0; IFS= read -r -t "$POLL_S" line <&3 || rc=$?
    [ "$rc" -ne 0 ] || continue
    same_proc "$rpid" "$rstart" " _run " || break
    compute_status "$STALL_S"
    [ "$STATE" != stalled ] || break
  done
  exec 3<&-
  watch_turn "$STALL_S" 0 "$n"
  [ "$STATE" = "done" ] || exit 1
}

do_stop() {
  local live=0 _
  if turn_live; then live=1; fi
  for _ in 1 2 3; do
    stop_processes || { printf 'codex-session: could not stop every process of session %s\n' "$name" >&2; exit 1; }
    # The runner records the end of the turn when codex exits.
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      if [ -e "$base.exit" ] || ! runner_alive; then break; fi
      sleep 0.5
    done
    if [ -e "$base.exit" ] || ! runner_alive; then break; fi
    kill -TERM "$(sed -n 1p "$lock/owner")" 2>/dev/null || true  # it had not launched codex yet
  done
  if [ "$live" = 1 ] && [ ! -e "$base.exit" ]; then echo 143 >"$base.exit"; fi
  compute_status "$STALL_S"
  print_state
}

case $cmd in
  start)
    [ $# -eq 5 ] || usage
    worktree=$1 model=$2 effort=$3 mode=$4 prompt=$5
    [ -n "$model" ] && [ -n "$effort" ] || die2 "model and effort must not be empty"
    check_prompt "$prompt"
    [ -d "$worktree" ] || die2 "worktree is not a directory: $worktree"
    worktree=$(CDPATH='' cd "$worktree" && pwd)
    sandbox_args "$mode" "$worktree"
    [ ! -e "$base.cwd" ] || die2 "session $name exists; use resume"
    codex=$(find_codex) || exit 2
    launch start "$worktree" "$model" "$effort" "$mode" "$prompt" "$codex"
    ;;
  resume)
    [ $# -ge 1 ] && [ $# -le 2 ] || usage
    check_prompt "$1"
    [ -e "$base.cwd" ] || die2 "no session $name in $run"
    codex=$(find_codex) || exit 2
    launch resume "$1" "${2:-}" "$codex"
    ;;
  status)
    [ $# -le 1 ] || usage
    stall=${1:-$STALL_S}; is_num "$stall" || die2 "stall-seconds must be a number: $stall"
    compute_status "$stall"
    print_state
    ;;
  watch)
    [ $# -le 3 ] || usage
    stall=${1:-$STALL_S} max=${2:-0} turn=${3:-}
    is_num "$stall" && is_num "$max" || die2 "stall-seconds and max-seconds must be numbers"
    [ -z "$turn" ] || is_num "$turn" || die2 "turn must be a number: $turn"
    watch_turn "$stall" "$max" "$turn"
    ;;
  stop) [ $# -eq 0 ] || usage; do_stop ;;
  _run) runner "$@" ;;
  *) usage ;;
esac
