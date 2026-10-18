#!/usr/bin/env bash
# Live checks for scripts/codex-session.sh against the real Codex CLI.
# Not run in CI: it needs a logged-in codex and a logged-in claude, spends a
# few cheap turns, and takes about 14 minutes (one turn runs `sleep 720`).
#   CODEX_LIVE_MODEL (default gpt-6-luna) and CODEX_LIVE_EFFORT (default low).
#   CODEX_LIVE_DIR: the directory for this run; it must be under $HOME, because
#   /tmp is writable in every Codex sandbox and hides sandbox limits
#   (default ~/.agents/runs/codex-session-live-<id>). CODEX_LIVE_KEEP=1 keeps it.
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
S="$here/../scripts/codex-session.sh"
M=${CODEX_LIVE_MODEL:-gpt-6-luna}; E=${CODEX_LIVE_EFFORT:-low}
die() { echo "SETUP FAILED: $*"; exit 2; }
id=live-$(date +%Y%m%d-%H%M%S)-$$          # the per-run marker
tmp=${CODEX_LIVE_DIR:-$HOME/.agents/runs/codex-session-$id}
case $tmp in "$HOME"/*) ;; *) die "CODEX_LIVE_DIR must be under \$HOME: $tmp" ;; esac
mkdir -p "$tmp" && tmp=$(cd "$tmp" && pwd -P) || die "run directory"
run=$tmp/run; main=$tmp/main; wt=$tmp/wt
sessions="w r fu a s long cc"
pids=''                                    # every background process this script starts
cleanup() {
  local n
  for n in $sessions; do "$S" stop "$run" "$n" >/dev/null 2>&1; done
  # shellcheck disable=SC2086
  [ -z "$pids" ] || kill $pids 2>/dev/null
  pkill -f -- "$id" 2>/dev/null; pkill -f -- "$tmp" 2>/dev/null
  git -C "$main" worktree remove --force "$wt" 2>/dev/null
  if [ "${CODEX_LIVE_KEEP:-0}" = 1 ]; then echo "kept $tmp"; else rm -rf "$tmp"; fi
}
trap cleanup EXIT
fails=0
check() { if [ "$2" = "$3" ]; then echo "ok   $1"; else echo "FAIL $1: want $2, got $3"; fails=$((fails + 1)); fi; }
note() { echo "note $*"; }
g() { git -c user.name=t -c user.email=t@t -c commit.gpgsign=false "$@"; }
mtime() { stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null || echo 0; }
has_line() { if grep -qx -- "$2" "$1" 2>/dev/null; then echo yes; else echo no; fi; }  # <file> <exact line>
thread_of() { jq -r 'select(.type=="thread.started") | .thread_id' "$run/$1.events.jsonl" 2>/dev/null | head -n 1; }
rollout() {
  local t; t=$(thread_of "$1"); [ -n "$t" ] || return 0
  ls -t "${CODEX_HOME:-$HOME/.codex}"/sessions/*/*/*/rollout-*"$t".jsonl 2>/dev/null | head -n 1
}
last_ctx() { jq -r "select(.type==\"turn_context\") | .payload.$2 // empty" "$(rollout "$1")" 2>/dev/null | tail -n 1; }
marked() { pgrep -f -- "$1" | wc -l | tr -d ' '; }
wait_status() {  # <name> <stall> <space-separated states> <seconds>
  local s _
  for _ in $(seq "$4"); do
    s=$("$S" status "$run" "$1" "$2" 2>/dev/null)
    case " $3 " in *" $s "*) echo "$s"; return 0 ;; esac
    sleep 1
  done
  echo "$s"
}

g init -q -b main "$main" && g -C "$main" commit -q --allow-empty -m init || die "main repo"
g -C "$main" worktree add -q -b lane "$wt" || die "linked worktree"
echo "run dir: $tmp"

# P70: a 12-minute command polled every 60 s with stall 150 is never stalled.
# It runs in the background while the other checks run.
cat >"$tmp/long.md" <<EOF
Run the shell command \`sleep 720 && echo finished-$id\` in the current directory.
When it has exited, reply with exactly the word DONE.
EOF
"$S" start "$run" long "$main" "$M" "$E" read "$tmp/long.md" >"$tmp/long.out" 2>"$tmp/long.err" &
long_pid=$!; pids="$pids $long_pid"
poll_long() {  # status every 60 s; event-log writes sampled every 5 s
  local t0 now m prev='' gap max=0 n=0 s roll
  t0=$(date +%s)
  while kill -0 "$long_pid" 2>/dev/null; do
    now=$(date +%s); m=$(mtime "$run/long.events.jsonl")
    if [ "$m" != 0 ] && [ "$m" != "$prev" ]; then
      if [ -n "$prev" ]; then gap=$((m - prev)); [ "$gap" -le "$max" ] || max=$gap; fi
      prev=$m
    fi
    if [ $((n % 12)) -eq 0 ]; then
      s=$("$S" status "$run" long 150 2>>"$tmp/long.poll.err")
      roll=$(rollout long); [ -z "$roll" ] || roll=$((now - $(mtime "$roll")))
      echo "$(date +%H:%M:%S) +$((now - t0))s $s events_age=$((now - ${prev:-$now}))s rollout_age=${roll:-none}s" >>"$tmp/long.poll"
    fi
    n=$((n + 1)); sleep 5
  done
  echo "largest event-log gap: ${max}s" >>"$tmp/long.poll"
}
poll_long &
poll_pid=$!; pids="$pids $poll_pid"

# P68, P84: write mode in a linked worktree commits; network is checked alone.
cat >"$tmp/w1.md" <<'EOF'
In the current directory, create a file w.txt that contains the line x. Stage it and commit it with
`git -c user.name=t -c user.email=t@t -c commit.gpgsign=false commit -m w`.
Reply with exactly one line: COMMIT=<short hash>, or COMMIT=FAILED if the commit failed.
EOF
check "write: turn finishes" "done" "$("$S" start "$run" w "$wt" "$M" "$E" write "$tmp/w1.md" 2>/dev/null | tail -n 1)"
check "write: a commit lands from a linked worktree" 1 "$(git -C "$wt" log --oneline main..lane | wc -l | tr -d ' ')"
cat >"$tmp/w2.md" <<'EOF'
Run `curl -sS -o /dev/null -w '%{http_code}' https://example.com` and nothing else.
Reply with exactly one line: HTTP=<status code>, or HTTP=FAILED if curl failed.
EOF
check "write: network alone returns 200" yes "$("$S" resume "$run" w "$tmp/w2.md" >/dev/null 2>&1; has_line "$run/w.last.md" HTTP=200)"
check "write: sandbox mode" workspace-write "$(last_ctx w sandbox_policy.type)"
check "write: approval policy" never "$(last_ctx w approval_policy)"

# Read mode cannot write; commands inherit the session marker.
cat >"$tmp/r1.md" <<'EOF'
Run `echo y > r.txt` in the current directory. Do not use any other way to create the file.
Then run `printenv CODEX_SESSION_MARK`.
Reply with exactly two lines: WRITE=ok if r.txt now exists, else WRITE=denied; then MARK=<printenv output>.
EOF
check "read: turn finishes" "done" "$("$S" start "$run" r "$wt" "$M" "$E" read "$tmp/r1.md" 2>/dev/null | tail -n 1)"
check "read: no file written" absent "$([ -e "$wt/r.txt" ] && echo present || echo absent)"
check "read: approval policy" never "$(last_ctx r approval_policy)"
check "read: commands inherit the session marker" yes "$(has_line "$run/r.last.md" "MARK=$(cat "$run/r.mark")")"

# P69: full mode has no sandbox and never asks.
printf 'Reply with exactly the word full.\n' >"$tmp/f1.md"
check "full: turn finishes" "done" "$("$S" start "$run" fu "$wt" "$M" "$E" full "$tmp/f1.md" 2>/dev/null | tail -n 1)"
check "full: sandbox mode" danger-full-access "$(last_ctx fu sandbox_policy.type)"
check "full: approval policy" never "$(last_ctx fu approval_policy)"

# P73: resume keeps the model and applies an effort override; same thread.
printf 'Reply with exactly the word resumed.\n' >"$tmp/w3.md"
check "resume: turn finishes" "done" "$("$S" resume "$run" w "$tmp/w3.md" medium 2>/dev/null | tail -n 1)"
check "resume: model kept" "$M" "$(last_ctx w model)"
check "resume: effort override applied" medium "$(last_ctx w effort)"
check "resume: no model-switch warning" 0 "$(tail -n +"$(($(cat "$run/w.offset") + 1))" "$run/w.events.jsonl" | grep -c 'is resuming with')"
check "resume: same thread" 1 "$(jq -r 'select(.type=="thread.started") | .thread_id' "$run/w.events.jsonl" | sort -u | wc -l | tr -d ' ')"

# P74: a watch for turn 1 sees a real session through to done.
printf 'Reply with exactly the word watched.\n' >"$tmp/a1.md"
"$S" start "$run" a "$wt" "$M" "$E" read "$tmp/a1.md" >/dev/null 2>&1 &
a_pid=$!; pids="$pids $a_pid"
check "watch: reports done for turn 1" "done" "$("$S" watch "$run" a 600 600 1 2>/dev/null)"
wait "$a_pid"

# P77: stop in the middle of a command leaves no process; resume continues.
printf 'Run the shell command `perl -e "sleep 600" %s-stop`, then reply with the word slept.\n' "$id" >"$tmp/s1.md"
"$S" start "$run" s "$wt" "$M" "$E" read "$tmp/s1.md" >/dev/null 2>&1 &
s_pid=$!; pids="$pids $s_pid"
check "stop: command seen running" busy "$(wait_status s 1 busy 120)"
check "stop: command process found by marker (setup)" yes "$([ "$(marked "$id-stop")" -ge 1 ] && echo yes || echo no)"
check "stop: session stopped" died "$("$S" stop "$run" s 2>/dev/null)"
wait "$s_pid"
check "stop: no process with the marker is left" 0 "$(marked "$id-stop")"
check "stop: no codex process of the session is left" 0 "$(marked "$run/s.last.md")"
printf 'Your session was stopped. Reply with exactly the word back.\n' >"$tmp/s2.md"
check "stop: resume after the stop finishes" "done" "$("$S" resume "$run" s "$tmp/s2.md" 2>/dev/null | tail -n 1)"
check "stop: resumed reply" yes "$(has_line "$run/s.last.md" back)"

# P76: a session started by a background Bash call inside `claude -p` keeps
# running after SIGTERM to that claude, and writes .exit.
if command -v claude >/dev/null 2>&1; then
  printf 'Run the shell command `sleep 90 && echo cc-%s`. When it has exited, reply with exactly the word CC-DONE.\n' "$id" >"$tmp/cc.md"
  clean_env=(env -u CLAUDECODE -u CLAUDE_PID -u CLAUDE_EFFORT)
  for v in $(compgen -e | grep '^CLAUDE_CODE_'); do clean_env+=(-u "$v"); done
  # The prompt goes on stdin: --allowedTools takes several values and would swallow it.
  printf 'Use the Bash tool with run_in_background set to true to run exactly this command: %s\nAfter it starts, reply with the word launched. Do not run any other command.\n' \
    "$S start $run cc $main $M $E read $tmp/cc.md" >"$tmp/claude-prompt.md"
  (cd "$tmp" && exec "${clean_env[@]}" claude -p --model haiku --allowedTools Bash \
    <"$tmp/claude-prompt.md" >"$tmp/claude.out" 2>&1) &
  claude_pid=$!; pids="$pids $claude_pid"
  check "claude -p: the session starts" yes "$(case $(wait_status cc 150 'running busy' 180) in running | busy) echo yes ;; *) echo no ;; esac)"
  check "claude -p: claude is still waiting (setup)" yes "$(kill -0 "$claude_pid" 2>/dev/null && echo yes || echo no)"
  kill -TERM "$claude_pid" 2>/dev/null
  for _ in $(seq 30); do kill -0 "$claude_pid" 2>/dev/null || break; sleep 1; done
  check "claude -p: claude exited after SIGTERM" no "$(kill -0 "$claude_pid" 2>/dev/null && echo yes || echo no)"
  check "claude -p: its background start command is gone" 0 "$(marked "start $run cc")"
  check "claude -p: the turn keeps running" yes "$(case $("$S" status "$run" cc 150 2>/dev/null) in running | busy) echo yes ;; *) echo no ;; esac)"
  for _ in $(seq 240); do [ -e "$run/cc.exit" ] && break; sleep 1; done
  check "claude -p: the turn writes .exit" yes "$([ -e "$run/cc.exit" ] && echo yes || echo no)"
  check "claude -p: the turn ends done" "done" "$("$S" status "$run" cc 2>/dev/null)"
  check "claude -p: the reply" yes "$(has_line "$run/cc.last.md" CC-DONE)"
else
  echo "FAIL claude -p: claude is not on PATH"; fails=$((fails + 1))
fi

# P70 results.
wait "$long_pid"; wait "$poll_pid"
cat "$tmp/long.poll"
check "long: the turn ends done" "done" "$(tail -n 1 "$tmp/long.out")"
check "long: no poll printed stalled" 0 "$(grep -c ' stalled ' "$tmp/long.poll")"
check "long: the command finished" yes "$(grep -q "finished-$id" "$run/long.events.jsonl" && echo yes || echo no)"
note "$(tail -n 1 "$tmp/long.poll")"

note "background PIDs started by this script:$pids"
[ "$fails" -eq 0 ] && echo "all passed" || { echo "$fails failed"; exit 1; }
