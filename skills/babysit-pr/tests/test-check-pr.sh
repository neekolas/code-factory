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

output=$(run_case required_failure)
expect_line 'required failure: CI' "$output" 'CI=FAIL'
expect_line 'required failure: required CI' "$output" 'REQUIRED_CI=FAIL'
printf -v row 'compile\trequired\thttps://example.test/compile'
expect_line 'required failure: listed as required' "$output" "$row"

output=$(run_case optional_failure)
expect_line 'optional failure: CI' "$output" 'CI=FAIL'
expect_line 'optional failure: required CI' "$output" 'REQUIRED_CI=PASS'
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
expect_line 'gh failure: first error line' "$output" 'CI_ERROR=API unavailable'
expect_empty_list 'gh failure: no false failures' "$output"

output=$(run_case required_error)
expect_line 'required query failure: CI' "$output" 'CI=ERROR'
expect_line 'required query failure: first error line' "$output" 'CI_ERROR=Required checks API unavailable'

if [[ $fails -eq 0 ]]; then
  echo 'all passed'
else
  echo "$fails failed"
  exit 1
fi
