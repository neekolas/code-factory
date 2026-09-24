#!/usr/bin/env bash
# Tests for scripts/codex-session.sh against the stub in tests/bin/codex.
set -uo pipefail
die() { echo "SETUP FAILED: $*"; exit 2; }
here=$(cd "$(dirname "$0")" && pwd)
S="$here/../scripts/codex-session.sh"
export PATH="$here/bin:$PATH" CODEX_SESSION_STOP_S=2 CODEX_SESSION_STARTUP_S=3
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
git -C "$tmp" init -q && git -C "$tmp" -c commit.gpgsign=false -c user.name="Fixture User" -c user.email="fixture@example.invalid" commit -q --allow-empty -m init \
  || die "fixture repository"
run="$tmp/run"; echo "prompt" >"$tmp/p.md"
fails=0
check() { if [ "$2" = "$3" ]; then echo "ok   $1"; else echo "FAIL $1: want $2, got $3"; fails=$((fails + 1)); fi; }

check "status of an unknown session" none "$("$S" status "$run" nobody)"
check "start succeeds" "done" "$(FAKE_MODE=ok "$S" start "$run" a "$tmp" m low write "$tmp/p.md")"
check "thread id recorded" stub-thread-1 "$(cat "$run/a.thread")"
check "failed resume is not reported as done" failed "$(FAKE_MODE=fail "$S" resume "$run" a "$tmp/p.md")"
check "a failed turn leaves no stale report" no "$([ -e "$run/a.last.md" ] && echo yes || echo no)"
check "resume after a failure succeeds" "done" "$(FAKE_MODE=ok "$S" resume "$run" a "$tmp/p.md")"
rm -f "$run/a.last.md"
check "reading and deleting the report keeps done" "done" "$("$S" status "$run" a)"
echo 1 >"$run/z.offset"; echo $(( $(date +%s) - 600 )) >"$run/z.started"; : >"$run/z.events.jsonl"
check "a launcher that died before codex started is died" died "$("$S" status "$run" z)"
check "resume keeps the session's model" m "$(FAKE_MODEL_LOG="$tmp/models" FAKE_MODE=ok "$S" resume "$run" a "$tmp/p.md" >/dev/null; tail -n 1 "$tmp/models")"

# A session whose directory was removed cannot resume; it says so at once.
mkdir "$tmp/gone"
FAKE_MODE=ok "$S" start "$run" f "$tmp/gone" m low read "$tmp/p.md" >/dev/null
rm -rf "$tmp/gone"
msg=$(FAKE_MODE=ok "$S" resume "$run" f "$tmp/p.md" 2>&1); rc=$?
check "resume in a removed directory exits 3" 3 "$rc"
check "resume in a removed directory asks for a handoff" yes "$(grep -q 'is gone. Start a new session with a handoff' <<<"$msg" && echo yes || echo no)"
check "a refused resume keeps the session state" "done" "$("$S" status "$run" f)"

# The watcher may start before the session writes anything.
( sleep 1; FAKE_MODE=ok "$S" start "$run" b "$tmp" m low write "$tmp/p.md" >/dev/null ) &
check "watch waits for a late start" "done" "$("$S" watch "$run" b 60)"
wait

# A running command is busy, not stalled; a silent turn becomes stalled.
FAKE_MODE=hang "$S" start "$run" c "$tmp" m low write "$tmp/p.md" >/dev/null &
sleep 2
check "open command within 3x the stall limit is busy" busy "$("$S" status "$run" c 1)"
check "stop ends a hung session" died "$("$S" stop "$run" c)"
wait

FAKE_MODE=silent "$S" start "$run" d "$tmp" m low write "$tmp/p.md" >/dev/null &
sleep 1
check "no event yet is starting" starting "$("$S" status "$run" d)"
sleep 3
check "no event after the startup limit is stalled" stalled "$("$S" status "$run" d)"
"$S" stop "$run" d >/dev/null; wait

FAKE_MODE=ignore_term "$S" start "$run" e "$tmp" m low write "$tmp/p.md" >/dev/null &
sleep 2
t0=$(date +%s)
check "stop kills a session that ignores SIGTERM" died "$("$S" stop "$run" e)"
check "stop returns within its deadline" yes "$([ $(( $(date +%s) - t0 )) -le 6 ] && echo yes || echo no)"
wait
left() {   # pgrep: 0 = found, 1 = none, anything else = it could not look
  local out rc; out=$(pgrep -f "$here/bin/codex"); rc=$?
  case $rc in 0) echo "$out" | wc -l | tr -d ' ' ;; 1) echo 0 ;; *) die "pgrep failed ($rc)" ;; esac
}
for _ in 1 2 3; do [ "$(left)" = 0 ] && break; sleep 1; done   # let killed processes exit
check "no stub process is left" 0 "$(left)"

[ "$fails" -eq 0 ] && echo "all passed" || { echo "$fails failed"; exit 1; }
