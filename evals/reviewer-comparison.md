# Reviewer comparison

Prompt edits are hypotheses. Use this procedure before claiming that a new
prompt catches more bugs or costs less.

## Paired runs

1. Select small historical changes with independently confirmed defects and
   their fixes. Freeze each base and candidate commit. Include clean changes
   and valuable contract tests as controls. A bot comment alone is not a
   confirmed defect: reproduce it or establish the full code path first.
2. Give two fresh reviewers the same code, plan, tools, model, effort, and
   budget. One gets the old prompt; one gets the draft. Give neither reviewer
   the bug report, fix, expected finding, or the other review. Keep answer
   notes outside their input and checkout. Counterbalance run order.
3. Judge findings against the frozen code. Count a known defect only when the
   reviewer identifies the trigger, faulty path, and wrong result. Validate
   new findings too; do not mark them false merely because the answer notes
   did not list them.
4. Record confirmed bugs found and missed, false findings, vacuous tests
   caught, valuable tests wrongly rejected, proof gaps, elapsed time, tokens
   when available, and repeated commands. Keep process-only findings separate.
5. Repeat on several changes. Use unseen defects from the same broad classes
   as a holdout. The examples used to write the prompt are development cases,
   not evidence that it generalizes.

## Splitting

Compare area-split finders with whole-change finders on large changes.
Start with libxmtp #4596; add other multi-thousand-line PRs with defects
that CI reviewers found. Run each case 3 times with fresh sessions with
area-split finders, and 3 times with finders that each get the whole change.
Hold models, effort, and REVIEW.md constant. Record defects found, false
findings, and wrongly refuted true defects. Count a finding as found only
when its scenario names the trigger, the faulty path, and the wrong result.

## Scoring sheet

Record one row per run:

| Case | Split | Run | Known defects found / total | Confirmed new defects | False findings (REFUTED by you) | Wrongly refuted true defects | UNPROVEN | Finders | Wall time | Tokens |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

"Wrongly refuted true defects" is the most important column: a coordinator
that refutes a real bug loses it for good. Judge every REFUTED item yourself.

## Long list

Hand the coordinator 16 findings for one change: 8 true and 8 false, mixed
severity. Include a true defect whose only current caller avoids it. Count
wrongly refuted true defects and missing statuses. This tests whether the
coordinator, on the reviewer model, stays accurate over a long list.

## Candidate cases

These are source leads, not a verified answer set. Confirm each on its cited
original finding commit before use; a comment's current commit can contain
later fixes. Keep this list out of reviewer inputs.

| Case | Why it matters | Source |
| --- | --- | --- |
| Public constructor stops validating | Two finders dismissed it because today's only caller validates first. | [libxmtp #4596](https://github.com/xmtp/libxmtp/pull/4596); found by Macroscope, fixed in `89e09cadf3`. See [E1](adversarial-review.md) |
| Cancellation before readiness | An await can precede abort handling. | [libxmtp #4256](https://github.com/xmtp/libxmtp/pull/4256#discussion_r4117489293) |
| Result encoding fails, then cleanup fails | A local error handler can release a lock while a resource remains live. | [libxmtp #4256](https://github.com/xmtp/libxmtp/pull/4256#discussion_r4117317041) |
| Default filter omits an input state | A test can pass for a plausible weaker implementation. | [libxmtp #4250](https://github.com/xmtp/libxmtp/pull/4250#discussion_r4116521802) |
| Rust callback used as binding proof | Valid local coverage can leave a foreign language boundary untested. | [libxmtp #4255](https://github.com/xmtp/libxmtp/pull/4255#discussion_r4116924336) |
| BSD-only `stat -f %m` in a session script | A portability bug that passes every macOS run; Linux prints filesystem status instead of an mtime. | This repository: fixed in `2ea03ac`; review the commit that added the call |
| Resume into a removed worktree | A recovery path fails with a bare `cd` error instead of a clear exit. | This repository: fixed in `2d7d77f` |
| Comment-only review body listed as feedback | A parser treats an HTML-comment marker as a review item. | This repository: fixed in `79ffe8c`; introduced with the collector in `2ebadb4` |
| Check reporting in `check-pr.sh` | Status mapping that reports the wrong check state. | This repository: fixed in `632058d` |

Add controls for an independent wire-format test, observable callback order,
and a useful one-off migration check. The desired result is preservation of
valid proof without a demand for duplicate permanent tests.

## Session lifetime

Evaluate lifetime separately from prompt wording. Hold the prompt constant.
Replay the same tasks, fixed revisions, and PR feedback to a lane-long
reviewer and to fresh reviewers at PR, unrelated-scope, or compaction boundaries. Record new defects
found, repeated resolved findings, handoff cost, and time or tokens. Do not
attribute a difference to lifetime if the candidates or models also changed.

There is no turn-count rotation rule. Start fresh for each PR, unrelated
scope, or compaction. Reuse only related review context that remains intact.
Test the review before the first push and the review of a major change after it.
Hold candidates and models constant when comparing session policies.

## Plan context

Compare task-only context with the full approved plan and design plus task
deltas. Include a task that depends on a decision outside its own section,
and an approved decision changed between tasks. Check whether the implementer
keeps the dependency, applies the latest decision, and stays within its lane.
Hold the task, model, and review prompt constant. This tests context handling
separately from reviewer quality.

For a Ref-hosted plan, let agents read Ref directly. Pass IDs and section
references, and check that later reads cover changed decisions without
exporting or relaying the full document. Include an edit that moves section
line numbers to test whether the agent checks headings or requirement IDs.
