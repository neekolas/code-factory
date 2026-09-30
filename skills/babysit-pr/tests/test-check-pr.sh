#!/usr/bin/env bash
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
script="$here/../scripts/check-pr.sh"
export PATH="$here/bin:$PATH"
fails=0

run_case() {
  local case_name=$1
  GH_CASE=$case_name "$script" 42 .
}

expect_line() {
  local label=$1 output=$2 expected=$3
  if grep -Fqx -- "$expected" <<<"$output"; then
    echo "ok   $label"
  else
    echo "FAIL $label: missing $expected"
    fails=$((fails + 1))
  fi
}

expect_empty_list() {
  local label=$1 output=$2 lines
  lines=$(sed -n '/^FAILED_CHECKS_BEGIN$/,/^FAILED_CHECKS_END$/p' <<<"$output" | wc -l | tr -d ' ')
  if [[ $lines == 2 ]]; then
    echo "ok   $label"
  else
    echo "FAIL $label: expected empty failed-check list"
    fails=$((fails + 1))
  fi
}

output=$(run_case passing)
expect_line 'all passing: CI' "$output" 'CI=PASS'
expect_line 'all passing: required CI' "$output" 'REQUIRED_CI=PASS'
expect_empty_list 'all passing: no failures' "$output"
expect_line 'all passing: no unresolved threads' "$output" 'UNRESOLVED_THREADS=0'

output=$(run_case threads_paginated)
expect_line 'thread pages: all unresolved threads counted' "$output" 'UNRESOLVED_THREADS=2'

output=$(run_case required_failure)
expect_line 'required failure: CI' "$output" 'CI=FAIL'
expect_line 'required failure: required CI' "$output" 'REQUIRED_CI=FAIL'
printf -v row 'compile\trequired\thttps://example.test/compile'
expect_line 'required failure: listed as required' "$output" "$row"

output=$(run_case optional_failure)
expect_line 'optional failure: CI' "$output" 'CI=FAIL'
expect_line 'optional failure: required CI' "$output" 'REQUIRED_CI=NONE'
printf -v row 'docs\toptional\thttps://example.test/docs'
expect_line 'optional failure: listed as optional' "$output" "$row"

output=$(run_case pending)
expect_line 'pending: CI' "$output" 'CI=PENDING'
expect_line 'pending: required CI' "$output" 'REQUIRED_CI=PENDING'

output=$(run_case none)
expect_line 'no checks: CI' "$output" 'CI=NONE'
expect_line 'no checks: required CI' "$output" 'REQUIRED_CI=NONE'
expect_empty_list 'no checks: no failures' "$output"

output=$(run_case gh_error)
expect_line 'gh failure: CI' "$output" 'CI=ERROR'
expect_line 'gh failure: required CI' "$output" 'REQUIRED_CI=ERROR'
expect_line 'gh failure: first error line' "$output" 'CI_ERROR=gh pr checks returned no JSON array'
expect_empty_list 'gh failure: no false failures' "$output"

output=$(run_case required_error)
expect_line 'required query failure: CI' "$output" 'CI=ERROR'
expect_line 'required query failure: first error line' "$output" 'CI_ERROR=required checks returned no JSON array'

output=$(run_case differing_response)
expect_line 'required response is independent: all CI' "$output" 'CI=PASS'
expect_line 'required response is independent: required CI' "$output" 'REQUIRED_CI=PENDING'

output=$(run_case missing_required)
expect_line 'required result absent from all results is pending' "$output" 'REQUIRED_CI=PENDING'

output=$(run_case optional_only)
expect_line 'nonempty all and empty required: all CI' "$output" 'CI=PASS'
expect_line 'nonempty all and empty required: required CI' "$output" 'REQUIRED_CI=NONE'

output=$(run_case unknown_required)
expect_line 'unknown required status cannot pass' "$output" 'REQUIRED_CI=ERROR'

output=$(run_case required_only_failure)
expect_line 'required-only failure controls required CI' "$output" 'REQUIRED_CI=FAIL'
printf -v row 'hidden\trequired\thttps://example.test/hidden'
expect_line 'required-only failure remains visible' "$output" "$row"

output=$(run_case head_race)
expect_line 'head change: snapshot is stale' "$output" 'SNAPSHOT=STALE'
expect_line 'head change: all CI cannot pass' "$output" 'CI=STALE'
expect_line 'head change: required CI cannot pass' "$output" 'REQUIRED_CI=STALE'
expect_empty_list 'head change: no failure list from another head' "$output"

output=$(run_case head_error)
expect_line 'final head read failure: snapshot error' "$output" 'SNAPSHOT=ERROR'
expect_line 'final head read failure: required CI error' "$output" 'REQUIRED_CI=ERROR'

# Execute the shell wrapper with a fake subprocess module. No real wait is needed.
# The fake gh above covers argument and exit behavior on macOS and Linux.
timeout_dir=$(mktemp -d)
trap 'rm -rf "$timeout_dir"' EXIT
cat > "$timeout_dir/subprocess.py" <<'PYTHON'
class TimeoutExpired(Exception):
    pass

def run(args, capture_output=False, timeout=None):
    if timeout != 60:
        raise RuntimeError("API call must have a 60-second timeout")
    raise TimeoutExpired()
PYTHON
output=$(PYTHONPATH="$timeout_dir" run_case passing 2>&1) && exit_code=0 || exit_code=$?
if [[ $exit_code == 124 && $output == *'gh call exceeded 60 seconds'* ]]; then
  echo 'ok   API timeout is bounded and portable'
else
  echo "FAIL API timeout: exit=$exit_code output=$output"
  fails=$((fails + 1))
fi

if [[ $fails -eq 0 ]]; then
  echo 'all passed'
else
  echo "$fails failed"
  exit 1
fi
