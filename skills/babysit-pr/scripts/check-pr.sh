#!/usr/bin/env bash
# check-pr.sh <pr-number|branch|url> [repo-dir]
#
# Deterministic PR status snapshot as greppable KEY=VALUE lines. This script
# only reports — all judgment (what to fix, when to sleep, when to give up)
# stays with the agent. Always exits 0 unless the PR itself can't be fetched.
#
# Output keys:
#   PR, URL, STATE, DRAFT, BRANCH, BASE, HEAD_SHA, MERGEABLE, MERGE_STATE
#   CI=PASS|FAIL|PENDING|NONE|ERROR          (aggregated over the HEAD commit's checks)
#   REQUIRED_CI=PASS|FAIL|PENDING|NONE|ERROR (required checks only)
#   CI_ERROR=<first error line>              (only when CI=ERROR)
#   FAILED_CHECKS_BEGIN … FAILED_CHECKS_END   (name<TAB>required|optional<TAB>link)
#   UNRESOLVED_THREADS=<n>
set -euo pipefail

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
checks=$(gh pr checks "$num" --json name,state,bucket,link 2>"$error_file") || :
check_error=
if ! jq -e 'type == "array"' >/dev/null 2>&1 <<<"$checks"; then
  check_error=$(sed -n '1p' "$error_file")
  [ -n "$check_error" ] || check_error=${checks%%$'\n'*}
  [ -n "$check_error" ] || check_error='gh pr checks returned no JSON array'
else
  required=$(gh pr checks "$num" --required --json name,bucket 2>"$error_file") || :
  # gh reports an empty required set as an error message, not JSON.
  if [ -z "$required" ] && grep -q '^no required checks reported' "$error_file"; then
    required='[]'
  fi
  if ! jq -e 'type == "array"' >/dev/null 2>&1 <<<"$required"; then
    check_error=$(sed -n '1p' "$error_file")
    [ -n "$check_error" ] || check_error=${required%%$'\n'*}
    [ -n "$check_error" ] || check_error='gh pr checks returned no JSON array'
  else
    checks=$(jq -n --argjson all "$checks" --argjson required "$required" '
      $all | map(. as $check | . + {
        required: any($required[]; .name == $check.name and .bucket == $check.bucket)
      })')
  fi
fi

agg() { # agg '<jq filter for subset>'
  jq -r --arg f "$1" '
    if length == 0 then "NONE" else
      [.[] | select($f == "all" or .required)] |
      if any(.[]; .bucket == "fail" or .bucket == "cancel") then "FAIL"
      elif any(.[]; .bucket == "pending") then "PENDING"
      else "PASS" end
    end' <<<"$checks"
}
if [ -n "$check_error" ]; then
  echo 'CI=ERROR'
  echo 'REQUIRED_CI=ERROR'
  echo "CI_ERROR=$check_error"
  echo 'FAILED_CHECKS_BEGIN'
  echo 'FAILED_CHECKS_END'
else
  echo "CI=$(agg all)"
  echo "REQUIRED_CI=$(agg required)"
  echo 'FAILED_CHECKS_BEGIN'
  jq -r '.[] | select(.bucket == "fail" or .bucket == "cancel") | [.name, (if .required then "required" else "optional" end), (.link // "-")] | @tsv' <<<"$checks"
  echo 'FAILED_CHECKS_END'
fi

repo=$(gh repo view --json owner,name --jq '.owner.login + " " + .name')
owner=${repo%% *}
name=${repo##* }
unresolved=0
cursor=
while :; do
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
