#!/usr/bin/env bash
# Live checks for scripts/codex-session.sh against the real Codex CLI.
# Not run in CI: it needs a logged-in `codex` and spends a few cheap turns.
#   CODEX_LIVE_MODEL (default gpt-6-luna) and CODEX_LIVE_EFFORT (default low).
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
S="$here/../scripts/codex-session.sh"
M=${CODEX_LIVE_MODEL:-gpt-6-luna}; E=${CODEX_LIVE_EFFORT:-low}
tmp=$(mktemp -d); run="$tmp/run"
cleanup() { git -C "$tmp/main" worktree remove --force "$tmp/wt" 2>/dev/null; rm -rf "$tmp"; }
trap cleanup EXIT
die() { echo "SETUP FAILED: $*"; exit 2; }
fails=0
check() { if [ "$2" = "$3" ]; then echo "ok   $1"; else echo "FAIL $1: want $2, got $3"; fails=$((fails + 1)); fi; }
g() { git -c user.name=t -c user.email=t@t -c commit.gpgsign=false "$@"; }

g init -q -b main "$tmp/main" && g -C "$tmp/main" commit -q --allow-empty -m init || die "main repo"
g -C "$tmp/main" worktree add -q -b lane "$tmp/wt" || die "linked worktree"

rollout() { ls -t ~/.codex/sessions/*/*/*/rollout-*"$(cat "$run/$1.thread")".jsonl 2>/dev/null | head -n 1; }
last_ctx() { jq -r "select(.type==\"turn_context\") | .payload.$2 // empty" "$(rollout "$1")" | tail -n 1; }

# 1. write mode in a linked worktree: commit (common git dir) and network.
cat >"$tmp/w1.md" <<'EOF'
In the current directory, create a file w.txt that contains the line x. Stage it and commit it with
`git -c user.name=t -c user.email=t@t -c commit.gpgsign=false commit -m w`. Then run
`curl -sS -o /dev/null -w '%{http_code}' https://example.com` and note the status code.
Reply with exactly one line: COMMIT=<short hash> HTTP=<status code or FAILED>.
EOF
check "write: turn finishes" "done" "$("$S" start "$run" w "$tmp/wt" "$M" "$E" write "$tmp/w1.md")"
check "write: commit landed through the common git dir" 1 "$(git -C "$tmp/wt" log --oneline main..lane | wc -l | tr -d ' ')"
check "write: network reachable" "HTTP=200" "$(grep -o 'HTTP=[0-9A-Z]*' "$run/w.last.md" 2>/dev/null)"
check "write: sandbox mode" "workspace-write" "$(last_ctx w sandbox_policy.type)"
check "write: approval policy" "never" "$(last_ctx w approval_policy)"

# 2. read mode cannot write.
cat >"$tmp/r1.md" <<'EOF'
Run `echo y > r.txt` in the current directory. Do not use any other way to create the file.
Reply with exactly one line: WRITE=ok if r.txt now exists, else WRITE=denied.
EOF
check "read: turn finishes" "done" "$("$S" start "$run" r "$tmp/wt" "$M" "$E" read "$tmp/r1.md")"
check "read: no file written" "absent" "$([ -e "$tmp/wt/r.txt" ] && echo present || echo absent)"

# 3. resume keeps the model and applies an effort override; no model-switch warning.
printf 'Reply with exactly the word resumed.\n' >"$tmp/w2.md"
check "resume: turn finishes" "done" "$("$S" resume "$run" w "$tmp/w2.md" medium)"
check "resume: model kept" "$M" "$(last_ctx w model)"
check "resume: effort override applied" "medium" "$(last_ctx w effort)"
check "resume: no model-switch warning" 0 "$(tail -n +"$(( $(cat "$run/w.offset") + 1 ))" "$run/w.events.jsonl" | grep -c 'is resuming with')"
check "resume: same thread" 1 "$(jq -r 'select(.type=="thread.started") | .thread_id' "$run/w.events.jsonl" | sort -u | wc -l | tr -d ' ')"

# 4. watch sees a real session through to done.
printf 'Reply with exactly the word watched.\n' >"$tmp/a1.md"
"$S" start "$run" a "$tmp/wt" "$M" "$E" read "$tmp/a1.md" >/dev/null &
check "watch: reports done" "done" "$("$S" watch "$run" a 600)"
wait

# 5. stop in the middle of a command, then resume from the log.
printf 'Run the shell command `sleep 120`, then reply with the word slept.\n' >"$tmp/s1.md"
"$S" start "$run" s "$tmp/wt" "$M" "$E" read "$tmp/s1.md" >/dev/null &
for _ in $(seq 60); do [ "$("$S" status "$run" s 1)" = busy ] && break; sleep 2; done
check "stop: command seen running" "busy" "$("$S" status "$run" s 1)"
check "stop: session stopped" "died" "$("$S" stop "$run" s)"
wait
check "stop: no sleep left running" 0 "$(pgrep -f 'sleep 120' | wc -l | tr -d ' ')"
printf 'Your session was interrupted. Reply with exactly the word back.\n' >"$tmp/s2.md"
check "stop: resume after the kill finishes" "done" "$("$S" resume "$run" s "$tmp/s2.md")"
check "stop: resumed reply" "back" "$(tr -d '[:space:]' <"$run/s.last.md")"

[ "$fails" -eq 0 ] && echo "all passed" || { echo "$fails failed"; exit 1; }
