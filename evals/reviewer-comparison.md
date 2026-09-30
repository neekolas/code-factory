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

## Candidate cases

These are source leads, not a verified answer set. Confirm each on its cited
original finding commit before use; a comment's current commit can contain
later fixes. Keep this list out of reviewer inputs.

| Case | Why it matters | Source |
| --- | --- | --- |
| Cancellation before readiness | An await can precede abort handling. | [libxmtp #4256](https://github.com/xmtp/libxmtp/pull/4256#discussion_r4117489293) |
| Result encoding fails, then cleanup fails | A local error handler can release a lock while a resource remains live. | [libxmtp #4256](https://github.com/xmtp/libxmtp/pull/4256#discussion_r4117317041) |
| Default filter omits an input state | A test can pass for a plausible weaker implementation. | [libxmtp #4250](https://github.com/xmtp/libxmtp/pull/4250#discussion_r4116521802) |
| Rust callback used as binding proof | Valid local coverage can leave a foreign language boundary untested. | [libxmtp #4255](https://github.com/xmtp/libxmtp/pull/4255#discussion_r4116924336) |

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
Test the first pre-submission review and conditional post-CI review boundary.
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
