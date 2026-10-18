#!/usr/bin/env bash
# Tests for scripts/codex-session.sh against the stub in tests/bin/codex.
# CODEX_SESSION_SCRIPT=<path> runs the same checks against another copy of the script.
set -uo pipefail
die() { echo "SETUP FAILED: $*"; exit 2; }
here=$(cd "$(dirname "$0")" && pwd)
S=${CODEX_SESSION_SCRIPT:-$here/../scripts/codex-session.sh}
stub=$here/bin/codex
unset CODEX_BIN CODEX_APP_BIN
tmp=$(mktemp -d) && tmp=$(cd "$tmp" && pwd -P) || die "temporary directory"
export PATH="$here/bin:$PATH" CODEX_SESSION_STOP_S=2 CODEX_SESSION_STARTUP_S=3 CODEX_SESSION_POLL_S=1 \
  CODEX_SESSION_TRACK_S=1 CODEX_HOME="$tmp/codex-home" CODEX_APP_BIN="$tmp/no-app/codex" \
  GIT_CEILING_DIRECTORIES="$tmp"
cleanup() {   # every process these tests start has $tmp in its arguments
  pkill -KILL -f -- "$tmp" 2>/dev/null
  rm -rf "$tmp"
}
trap cleanup EXIT
g() { git -c commit.gpgsign=false -c user.name="Fixture User" -c user.email="fixture@example.invalid" "$@"; }
repo=$tmp/repo
g init -q "$repo" && g -C "$repo" commit -q --allow-empty -m init || die "fixture repository"
g -C "$repo" worktree add -q -b lane "$tmp/wt" || die "linked worktree"
mkdir "$tmp/plain" "$tmp/cwd" || die "fixture directories"
run=$tmp/run; p=$tmp/p.md; echo "prompt" >"$p"
fails=0
check() { if [ "$2" = "$3" ]; then echo "ok   $1"; else echo "FAIL $1: want $2, got $3"; fails=$((fails + 1)); fi; }
yesno() { if "$@"; then echo yes; else echo no; fi; }
last() { tail -n 1; }
rc_of() { "$@" >/dev/null 2>&1; echo $?; }
files_of() { find "$run" -maxdepth 1 -name "$1.*" 2>/dev/null | wc -l | tr -d ' '; }
bounded() { perl -e 'alarm shift; exec @ARGV or die "exec: $!\n"' "$@"; }  # <seconds> <command...>
procs_with() { pgrep -f -- "$1" | wc -l | tr -d ' '; }
age_file() { perl -e 'my $t = time - shift; utime $t, $t, @ARGV' "$2" "$1"; }  # <file> <seconds ago>
wait_state() {  # <name> <space-separated states> [seconds]
  local i s
  for i in $(seq $((${3:-10} * 5))); do
    s=$("$S" status "$run" "$1" 2>/dev/null)
    case " $2 " in *" $s "*) return 0 ;; esac
    sleep 0.2
  done
  return 1
}
wait_file() { local i; for i in $(seq $(($2 * 5))); do [ -e "$1" ] && return 0; sleep 0.2; done; return 1; }
tree() { local c; for c in $(pgrep -P "$1"); do echo "$c"; tree "$c"; done; }

# --- Existing behaviour
check "status of an unknown session" none "$("$S" status "$run" nobody)"
check "start succeeds" "done" "$(FAKE_MODE=ok "$S" start "$run" a "$repo" m low write "$p" | last)"
check "thread id recorded" stub-thread-1 "$(cat "$run/a.thread")"
check "failed resume is not reported as done" failed "$(FAKE_MODE=fail "$S" resume "$run" a "$p" 2>/dev/null | last)"
check "a failed turn leaves no stale report" no "$(yesno test -e "$run/a.last.md")"
check "resume after a failure succeeds" "done" "$(FAKE_MODE=ok "$S" resume "$run" a "$p" 2>/dev/null | last)"
rm -f "$run/a.last.md"
check "reading and deleting the report keeps done" "done" "$("$S" status "$run" a 2>/dev/null)"
echo 1 >"$run/z.offset"; echo $(($(date +%s) - 600)) >"$run/z.started"; : >"$run/z.events.jsonl"
check "a launcher that died before codex started is died" died "$("$S" status "$run" z 2>/dev/null)"
check "resume keeps the session's model" m "$(FAKE_MODEL_LOG="$tmp/models" FAKE_MODE=ok "$S" resume "$run" a "$p" >/dev/null 2>&1; tail -n 1 "$tmp/models")"

mkdir "$tmp/gone"
FAKE_MODE=ok "$S" start "$run" f "$tmp/gone" m low read "$p" >/dev/null 2>&1
rm -rf "$tmp/gone"
msg=$(FAKE_MODE=ok "$S" resume "$run" f "$p" 2>&1); rc=$?
check "resume in a removed directory exits 3" 3 "$rc"
check "resume in a removed directory asks for a handoff" yes "$(yesno grep -q 'is gone. Start a new session with a handoff' <<<"$msg")"
check "a refused resume keeps the session state" "done" "$("$S" status "$run" f 2>/dev/null)"

(sleep 1; FAKE_MODE=ok "$S" start "$run" b "$repo" m low write "$p" >/dev/null 2>&1) &
check "watch waits for a late start" "done" "$(bounded 30 "$S" watch "$run" b 60 2>/dev/null)"
wait

FAKE_MODE=hang "$S" start "$run" c "$repo" m low write "$p" >/dev/null 2>&1 &
sleep 2
check "open command within 3x the stall limit is busy" busy "$("$S" status "$run" c 1 2>/dev/null)"
check "stop ends a hung session" died "$(bounded 30 "$S" stop "$run" c 2>/dev/null)"
wait

FAKE_MODE=silent "$S" start "$run" d "$repo" m low write "$p" >/dev/null 2>&1 &
sleep 1
check "no event yet is starting" starting "$("$S" status "$run" d 2>/dev/null)"
sleep 3
check "no event after the startup limit is stalled" stalled "$("$S" status "$run" d 2>/dev/null)"
bounded 30 "$S" stop "$run" d >/dev/null 2>&1; wait

FAKE_MODE=ignore_term "$S" start "$run" e "$repo" m low write "$p" >/dev/null 2>&1 &
sleep 2
t0=$(date +%s)
check "stop kills a session that ignores SIGTERM" died "$(bounded 30 "$S" stop "$run" e 2>/dev/null)"
check "stop returns within its deadline" yes "$(yesno test $(($(date +%s) - t0)) -le 6)"
wait

# --- P65 binary discovery: CODEX_BIN, then PATH, then CODEX_APP_BIN
for w in A B C; do
  mkdir -p "$tmp/bin-$w"
  printf '#!/usr/bin/env bash\nexport FAKE_WHO=%s\nexec "%s" "$@"\n' "$w" "$stub" >"$tmp/bin-$w/codex"
  chmod +x "$tmp/bin-$w/codex"
done
nocodex=''
IFS=: read -r -a dirs <<<"$PATH"
for d in "${dirs[@]}"; do [ -x "$d/codex" ] || nocodex="$nocodex${nocodex:+:}$d"; done
who() {  # <name> <environment...>: the stub that ran a start
  local n=$1; shift
  : >"$tmp/who"
  env "$@" FAKE_WHO_LOG="$tmp/who" "$S" start "$run" "$n" "$repo" m low read "$p" >/dev/null 2>&1
  cat "$tmp/who"
}
check "binary: CODEX_BIN comes first" A "$(who w1 CODEX_BIN="$tmp/bin-A/codex" PATH="$tmp/bin-B:$nocodex" CODEX_APP_BIN="$tmp/bin-C/codex")"
check "binary: then codex on PATH" B "$(who w2 PATH="$tmp/bin-B:$nocodex" CODEX_APP_BIN="$tmp/bin-C/codex")"
check "binary: then CODEX_APP_BIN" C "$(who w3 PATH="$nocodex" CODEX_APP_BIN="$tmp/bin-C/codex")"
msg=$(env PATH="$nocodex" "$S" start "$run" w4 "$repo" m low read "$p" 2>&1); rc=$?
check "binary: none found exits 2" 2 "$rc"
check "binary: the error names all three places" yes \
  "$(yesno grep -q 'CODEX_BIN.*PATH.*CODEX_APP_BIN' <<<"$msg")"
check "binary: none found writes no session file" 0 "$(files_of w4)"
check "binary: a CODEX_BIN that cannot run exits 2" 2 \
  "$(rc_of env CODEX_BIN="$tmp/no-such-codex" PATH="$tmp/bin-B:$nocodex" "$S" start "$run" w5 "$repo" m low read "$p")"

# --- P66 validate before writing: exit 2, no files, and the name works on retry
check "relative run dir exits 2" 2 "$(cd "$tmp/cwd" && rc_of "$S" start rel v1 "$repo" m low read "$p")"
check "relative run dir writes nothing" 0 "$(find "$tmp/cwd" -mindepth 1 | wc -l | tr -d ' ')"
check "relative prompt path exits 2" 2 "$(cd "$tmp" && rc_of "$S" start "$run" v2 "$repo" m low read p.md)"
check "relative prompt path writes no session file" 0 "$(files_of v2)"
check "unreadable prompt exits 2" 2 "$(rc_of "$S" start "$run" v3 "$repo" m low read "$tmp/missing.md")"
check "unreadable prompt writes no session file" 0 "$(files_of v3)"
check "missing worktree exits 2" 2 "$(rc_of "$S" start "$run" v4 "$tmp/nope" m low read "$p")"
check "missing worktree writes no session file" 0 "$(files_of v4)"
check "write mode outside a git worktree exits 2" 2 "$(rc_of "$S" start "$run" v5 "$tmp/plain" m low write "$p")"
check "write mode outside a git worktree writes no session file" 0 "$(files_of v5)"
for v in v1 v2 v3 v4 v5; do
  check "after a refused start, $v starts" "done" "$(FAKE_MODE=ok "$S" start "$run" "$v" "$repo" m low read "$p" 2>/dev/null | last)"
done

# --- P67 session lock
FAKE_MODE=ok "$S" start "$run" k "$repo" m low read "$p" >/dev/null 2>&1
: >"$tmp/args-k"
for i in 1 2; do
  (FAKE_MODE=slow FAKE_ARGS_LOG="$tmp/args-k" bounded 30 "$S" resume "$run" k "$p" >/dev/null 2>&1; echo $? >"$tmp/k$i.rc") &
done
wait
check "two resumes at once: one exits 2" "0 2" "$(cat "$tmp/k1.rc" "$tmp/k2.rc" | sort | tr '\n' ' ' | sed 's/ $//')"
check "two resumes at once: one codex process" 1 "$(wc -l <"$tmp/args-k" | tr -d ' ')"
check "two resumes at once: one new turn" 2 "$(cat "$run/k.turn" 2>/dev/null)"
FAKE_MODE=slow FAKE_SLOW_S=6 "$S" resume "$run" k "$p" >/dev/null 2>&1 &
wait_state k "running busy"; sleep 2   # let the runner record the stub's processes
snap() { for f in "$run"/k.* "$run"/k.lock/*; do [ -f "$f" ] && printf '%s %s\n' "$f" "$(cksum <"$f")"; done; }
before=$(snap)
check "resume of a live session exits 2" 2 "$(rc_of "$S" resume "$run" k "$p")"
check "a refused resume changes no session file" "$before" "$(snap)"
wait
sleep 0 & dead=$!; wait "$dead"
mkdir "$run/k.lock"; printf '%s\n%s\n' "$dead" "Thu Jan  1 00:00:00 2026" >"$run/k.lock/owner"
check "a lock whose holder is dead is cleared" "done" "$(FAKE_MODE=ok bounded 30 "$S" resume "$run" k "$p" 2>/dev/null | last)"
check "the lock is released after the turn" absent "$([ -e "$run/k.lock" ] && echo present || echo absent)"
sleep 60 & other=$!
mkdir "$run/k.lock"; printf '%s\n%s\n' "$other" "Thu Jan  1 00:00:00 2026" >"$run/k.lock/owner"
check "a lock whose holder's identity differs is cleared" "done" "$(FAKE_MODE=ok bounded 30 "$S" resume "$run" k "$p" 2>/dev/null | last)"
check "the process named in that lock is untouched" yes "$(yesno kill -0 "$other")"
check "that lock is released after the turn" absent "$([ -e "$run/k.lock" ] && echo present || echo absent)"
kill "$other"; wait "$other" 2>/dev/null

# --- P68, P69 sandbox arguments on start and resume
gitdir=$(git -C "$tmp/wt" rev-parse --absolute-git-dir)
common=$(git -C "$tmp/wt" rev-parse --path-format=absolute --git-common-dir)
for m in read write full; do
  : >"$tmp/args-$m"
  FAKE_ARGS_LOG="$tmp/args-$m" "$S" start "$run" "mode-$m" "$tmp/wt" m low "$m" "$p" >/dev/null 2>&1
  FAKE_ARGS_LOG="$tmp/args-$m" "$S" resume "$run" "mode-$m" "$p" >/dev/null 2>&1
done
runs_with() { grep -cF -- "$2" "$tmp/args-$1"; }   # <mode> <text>: runs whose arguments contain it
for m in read write full; do
  check "$m: approval_policy never on start and resume" 2 "$(runs_with "$m" 'approval_policy="never"')"
done
check "read: read-only sandbox on start and resume" 2 "$(runs_with read 'sandbox_mode="read-only"')"
check "write: writable roots have the worktree's git dir" 2 "$(runs_with write "\"$gitdir\"")"
check "write: writable roots have the common git dir" 2 "$(runs_with write "\"$common\"")"
check "full: bypass flag on start and resume" 2 "$(runs_with full --dangerously-bypass-approvals-and-sandbox)"
check "full: no sandbox_workspace_write keys" 0 "$(runs_with full sandbox_workspace_write)"

# --- P70, P71 liveness: the newer of events.jsonl and the rollout file
FAKE_MODE=hang FAKE_THREAD=thread-hb "$S" start "$run" hb "$repo" m low read "$p" >/dev/null 2>&1 &
wait_state hb "running busy"
roll=$CODEX_HOME/sessions/2026/01/02/rollout-2026-01-02T00-00-00-thread-hb.jsonl
mkdir -p "$(dirname "$roll")"; : >"$roll"
age_file "$run/hb.events.jsonl" 100
check "stale events with a fresh rollout is running" running "$("$S" status "$run" hb 60 2>/dev/null)"
rm -f "$roll"
check "no rollout file gives a warning on stderr" yes "$(yesno grep -q 'no rollout file' <<<"$("$S" status "$run" hb 60 2>&1 >/dev/null)")"
check "both stale with an open command is busy" busy "$("$S" status "$run" hb 60 2>/dev/null)"
age_file "$run/hb.events.jsonl" 200
check "busy turns stalled after 3x the stall limit" stalled "$("$S" status "$run" hb 60 2>/dev/null)"
age_file "$run/hb.events.jsonl" 1100
check "default stall limit: 1100 s quiet is running" running "$("$S" status "$run" hb 2>/dev/null)"
age_file "$run/hb.events.jsonl" 1300
check "default stall limit: 1300 s quiet with an open command is busy" busy "$("$S" status "$run" hb 2>/dev/null)"
bounded 30 "$S" stop "$run" hb >/dev/null 2>&1; wait

# --- P72 incomplete
check "an open command at turn.completed is incomplete" incomplete "$(FAKE_MODE=abandon "$S" resume "$run" a "$p" 2>/dev/null | last)"

# --- P73 effort
effort_of_last_run() { tail -n 1 "$tmp/args-e" | grep -o 'model_reasoning_effort=[a-z]*'; }
: >"$tmp/args-e"
FAKE_ARGS_LOG="$tmp/args-e" "$S" resume "$run" a "$p" >/dev/null 2>&1
check "resume passes the stored effort" model_reasoning_effort=low "$(effort_of_last_run)"
FAKE_ARGS_LOG="$tmp/args-e" "$S" resume "$run" a "$p" xhigh >/dev/null 2>&1
FAKE_ARGS_LOG="$tmp/args-e" "$S" resume "$run" a "$p" >/dev/null 2>&1
check "an effort given to resume is kept" model_reasoning_effort=xhigh "$(effort_of_last_run)"

# --- P74, P75 turn-scoped and bounded watch
out=$(FAKE_MODE=ok "$S" start "$run" t "$repo" m low read "$p" 2>/dev/null)
check "start prints turn 1 first" "turn 1" "$(head -n 1 <<<"$out")"
(sleep 1; FAKE_MODE=slow FAKE_SLOW_S=3 FAKE_REPORT=second "$S" resume "$run" t "$p" >"$tmp/t.resume" 2>/dev/null) &
st=$(bounded 30 "$S" watch "$run" t 60 0 2 2>/dev/null)
check "watch for turn 2 does not report turn 1" "done second" "$st $(cat "$run/t.last.md" 2>/dev/null)"
wait
check "resume prints turn 2 first" "turn 2" "$(head -n 1 "$tmp/t.resume")"
FAKE_MODE=hang "$S" start "$run" bw "$repo" m low read "$p" >/dev/null 2>&1 &
wait_state bw "running busy"
t0=$(date +%s); st=$(bounded 30 "$S" watch "$run" bw 1200 2 2>/dev/null); t1=$(date +%s)
check "a bounded watch prints the live state" running "$st"
check "a bounded watch returns after its limit" yes "$(yesno test $((t1 - t0)) -ge 2 -a $((t1 - t0)) -le 5)"
bounded 30 "$S" stop "$run" bw >/dev/null 2>&1; wait

# --- P76 the turn survives its launcher's process group and process tree
perl -e 'setpgrp(0, 0); exec @ARGV' env FAKE_MODE=slow FAKE_SLOW_S=4 "$S" start "$run" pk "$repo" m low read "$p" >/dev/null 2>&1 &
launcher=$!
wait_state pk "running busy"
victims=$(tree "$launcher")
# shellcheck disable=SC2086
{ kill -TERM -- "-$launcher"; kill -TERM $victims; sleep 0.5; kill -KILL -- "-$launcher"; kill -KILL $victims; } 2>/dev/null
wait "$launcher" 2>/dev/null
wait_file "$run/pk.exit" 15
check "after the launcher is killed the turn writes .exit" yes "$(yesno test -e "$run/pk.exit")"
check "after the launcher is killed the turn writes last.md" report "$(cat "$run/pk.last.md" 2>/dev/null)"
check "after the launcher is killed the turn is done" "done" "$("$S" status "$run" pk 2>/dev/null)"

# --- P77 no process of a turn is left after stop, or after resume of a died turn
FAKE_MODE=orphan FAKE_SLOW_S=2 FAKE_ORPHAN_MARK="$tmp/orphan-a" bounded 30 "$S" start "$run" or1 "$repo" m low read "$p" >/dev/null 2>&1
check "a codex that exits mid-turn is died" died "$("$S" status "$run" or1 2>/dev/null)"
check "its command outlives it (setup)" 1 "$(procs_with "$tmp/orphan-a")"
bounded 30 "$S" stop "$run" or1 >/dev/null 2>&1
check "stop leaves no process of a turn whose codex is gone" 0 "$(procs_with "$tmp/orphan-a")"
FAKE_MODE=orphan FAKE_SLOW_S=2 FAKE_ORPHAN_MARK="$tmp/orphan-b" bounded 30 "$S" start "$run" or2 "$repo" m low read "$p" >/dev/null 2>&1
check "its command outlives it (setup, second session)" 1 "$(procs_with "$tmp/orphan-b")"
check "resume after died succeeds" "done" "$(FAKE_MODE=ok bounded 30 "$S" resume "$run" or2 "$p" 2>/dev/null | last)"
check "resume after died stops the leftover command first" 0 "$(procs_with "$tmp/orphan-b")"

# --- P78 a stored PID now used by another process
sleep 60 & other=$!
FAKE_MODE=ok "$S" start "$run" id "$repo" m low read "$p" >/dev/null 2>&1
{ echo "$other"; sed -n '2,$p' "$run/id.pid"; } >"$run/id.pid.new" && mv "$run/id.pid.new" "$run/id.pid"
rm -f "$run/id.exit"
check "a reused PID is not reported as running" "done" "$("$S" status "$run" id 2>/dev/null)"
bounded 30 "$S" stop "$run" id >/dev/null 2>&1
check "stop does not kill the process that reused the PID" yes "$(yesno kill -0 "$other")"
kill "$other"; wait "$other" 2>/dev/null

# --- P79 footer
FAKE_PROMPT_LOG="$tmp/seen" FAKE_MODE=ok "$S" start "$run" ft "$repo" m low read "$p" >/dev/null 2>&1
check "start: the prompt file comes first" prompt "$(head -n 1 "$tmp/seen")"
check "start: the footer asks codex to wait for each command" yes "$(yesno grep -q 'Wait until each command you start exits' "$tmp/seen")"
FAKE_PROMPT_LOG="$tmp/seen" FAKE_MODE=ok "$S" resume "$run" ft "$p" >/dev/null 2>&1
check "resume: the prompt ends with the footer" yes "$(yesno grep -q 'Wait until each command you start exits' <<<"$(tail -n 1 "$tmp/seen")")"

# --- P82 failure reason
msg=$(FAKE_MODE=fail "$S" resume "$run" a "$p" 2>&1 >/dev/null)
check "a failed turn prints the error message" yes "$(yesno grep -q 'boom' <<<"$msg")"
msg=$(FAKE_MODE=failjson "$S" resume "$run" a "$p" 2>&1 >/dev/null)
check "a nested error message is unwrapped" yes "$(yesno grep -qx 'codex-session: The model is not supported' <<<"$msg")"
check "status of a failed turn prints the error message" yes \
  "$(yesno grep -q 'The model is not supported' <<<"$("$S" status "$run" a 2>&1 >/dev/null)")"

left() {   # pgrep: 0 = found, 1 = none, anything else = it could not look
  local out rc; out=$(pgrep -f -- "$1"); rc=$?
  case $rc in 0) echo "$out" | wc -l | tr -d ' ' ;; 1) echo 0 ;; *) die "pgrep failed ($rc)" ;; esac
}
for _ in 1 2 3 4 5; do [ "$(left "$stub.*$tmp")" = 0 ] && break; sleep 1; done   # let killed processes exit
check "no stub process is left" 0 "$(left "$stub.*$tmp")"
check "no runner is left" 0 "$(left "_run $run")"

[ "$fails" -eq 0 ] && echo "all passed" || { echo "$fails failed"; exit 1; }
