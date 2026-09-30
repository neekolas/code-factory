#!/usr/bin/env bash
# check-pr.sh <pr-number|branch|url> [repo-dir]
#
# Deterministic PR status snapshot as greppable KEY=VALUE lines. This script
# only reports — all judgment (what to fix, when to sleep, when to give up)
# stays with the agent. Always exits 0 unless the PR itself can't be fetched.
#
# Output keys:
#   PR, URL, STATE, DRAFT, BRANCH, BASE, HEAD_SHA, MERGEABLE, MERGE_STATE
#   CI=PASS|FAIL|PENDING|NONE|ERROR|STALE          (aggregated over the HEAD commit's checks)
#   REQUIRED_CI=PASS|FAIL|PENDING|NONE|ERROR|STALE (required checks only)
#   CI_ERROR=<error summary>              (only when CI=ERROR)
#   FAILED_CHECKS_BEGIN … FAILED_CHECKS_END   (name<TAB>required|optional|unknown<TAB>link)
#   UNRESOLVED_THREADS=<n>
set -euo pipefail

# Python is available with the feedback helpers. This works on macOS and Linux.
# Each API call has a 60-second limit. Do not print the API error body.
gh() {
  python3 -c '
import subprocess, sys
try:
    result = subprocess.run(["gh", *sys.argv[1:]], capture_output=True, timeout=60)
except subprocess.TimeoutExpired:
    print("gh call exceeded 60 seconds", file=sys.stderr)
    sys.exit(124)
except OSError:
    print("gh call failed", file=sys.stderr)
    sys.exit(127)
sys.stdout.buffer.write(result.stdout)
if result.stderr.startswith(b"no required checks reported"):
    sys.stderr.write("no required checks reported\n")
elif result.stderr:
    print("gh returned an error", file=sys.stderr)
sys.exit(result.returncode)
' "$@"
}

pr="${1:?usage: check-pr.sh <pr-number|branch|url> [repo-dir]}"
dir="${2:-.}"
cd "$dir"

view=$(gh pr view "$pr" --json number,url,state,isDraft,headRefName,headRefOid,baseRefName,mergeable,mergeStateStatus)
num=$(jq -r .number <<<"$view")
echo "PR=$num"
echo "URL=$(jq -r .url <<<"$view")"
echo "STATE=$(jq -r .state <<<"$view")"
echo "DRAFT=$(jq -r .isDraft <<<"$view")"
echo "BRANCH=$(jq -r .headRefName <<<"$view")"
echo "BASE=$(jq -r .baseRefName <<<"$view")"
echo "HEAD_SHA=$(jq -r .headRefOid <<<"$view")"
echo "MERGEABLE=$(jq -r .mergeable <<<"$view")"
echo "MERGE_STATE=$(jq -r .mergeStateStatus <<<"$view")"

# gh pr checks uses nonzero exits to signal failing/pending checks. Its JSON
# output is still valid in those cases. A missing JSON array is an error.
error_file=$(mktemp)
trap 'rm -f "$error_file"' EXIT
required='[]'
checks=$(gh pr checks "$num" --json name,state,bucket,link 2>"$error_file") || :
check_error=
if ! jq -e 'type == "array"' >/dev/null 2>&1 <<<"$checks"; then
  check_error='gh pr checks returned no JSON array'
else
  required=$(gh pr checks "$num" --required --json name,bucket,link 2>"$error_file") || :
  # gh reports an empty required set as an error message, not JSON.
  if [ -z "$required" ] && grep -q '^no required checks reported' "$error_file"; then
    required='[]'
  fi
  if ! jq -e 'type == "array"' >/dev/null 2>&1 <<<"$required"; then
    check_error='required checks returned no JSON array'
  else
    checks=$(jq -n --argjson all "$checks" --argjson required "$required" '
      $all | map(. as $check | . + {
        required: (if any($required[]; .name == $check.name and (.link // "") != "" and .link == $check.link) then "required"
                   elif any($required[]; .name == $check.name and (.link // "") == "") then "unknown"
                   else "optional" end)
      })')
  fi
fi

agg() {
  jq -r '
    if length == 0 then "NONE"
    elif any(.[]; .bucket == "fail" or .bucket == "cancel") then "FAIL"
    elif any(.[]; .bucket == "pending") then "PENDING"
    elif all(.[]; .bucket == "pass" or .bucket == "skipping") then "PASS"
    else "ERROR" end' <<<"$1"
}

repo=$(gh repo view --json owner,name --jq '.owner.login + " " + .name')
owner=${repo%% *}
name=${repo##* }
unresolved=0
cursor=
while :; do
  # GraphQL variables must remain literal.
  # shellcheck disable=SC2016
  args=(-f query='query($owner:String!,$name:String!,$pr:Int!,$cursor:String){repository(owner:$owner,name:$name){pullRequest(number:$pr){reviewThreads(first:100,after:$cursor){nodes{isResolved} pageInfo{hasNextPage endCursor}}}}}'
    -f owner="$owner" -f name="$name" -F pr="$num")
  if [ -n "$cursor" ]; then
    args+=(-f cursor="$cursor")
  fi
  page=$(gh api graphql "${args[@]}" 2>/dev/null) || { unresolved='?'; break; }
  if ! jq -e '.data.repository.pullRequest.reviewThreads | .nodes != null and .pageInfo.hasNextPage != null' >/dev/null 2>&1 <<<"$page"; then
    unresolved='?'
    break
  fi
  count=$(jq '[.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved | not)] | length' <<<"$page")
  unresolved=$((unresolved + count))
  if [ "$(jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.hasNextPage' <<<"$page")" != true ]; then
    break
  fi
  cursor=$(jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.endCursor // empty' <<<"$page")
  if [ -z "$cursor" ]; then
    unresolved='?'
    break
  fi
done
echo "UNRESOLVED_THREADS=$unresolved"

# The checks endpoint uses the live PR head. Bind the result to a stable head.
final_view=$(gh pr view "$num" --json headRefOid 2>"$error_file") || :
head_state=COMPLETE
if ! jq -e '.headRefOid | type == "string" and length > 0' >/dev/null 2>&1 <<<"$final_view"; then
  head_state=ERROR
  check_error='cannot verify the final PR head'
elif [ "$(jq -r .headRefOid <<<"$final_view")" != "$(jq -r .headRefOid <<<"$view")" ]; then
  head_state=STALE
fi
if [ -n "$check_error" ] && [ "$head_state" != STALE ]; then
  head_state=ERROR
fi
echo "SNAPSHOT=$head_state"
if [ "$head_state" = STALE ]; then
  echo 'CI=STALE'
  echo 'REQUIRED_CI=STALE'
elif [ -n "$check_error" ]; then
  echo 'CI=ERROR'
  echo 'REQUIRED_CI=ERROR'
  echo "CI_ERROR=$check_error"
else
  echo "CI=$(agg "$checks")"
  echo "REQUIRED_CI=$(agg "$required")"
fi
echo 'FAILED_CHECKS_BEGIN'
if [ -z "$check_error" ] && [ "$head_state" != STALE ]; then
  jq -nr --argjson all "$checks" --argjson required "$required" '
    ($all + [$required[] | . as $r | select(all($all[]; .name != $r.name or .link != $r.link)) | . + {required: "required"}])[] |
    select(.bucket == "fail" or .bucket == "cancel") | [.name, .required, (.link // "-")] | @tsv'
fi
echo 'FAILED_CHECKS_END'
