# Implementer prompt

Use the first prompt when a lane starts. Use the second for feedback in the
same session. Resolve paths from the installed plugin and the run brief.

## Start a lane

```text
Own lane <name>, PR <number or planned PR>, tasks <IDs>, in <worktree>.
Read <RUN>/brief.md and task briefs <paths>. Read the full approved plan and
design <Ref IDs or file paths> once. Later, read changed sections directly.
Use <audit-tests/SKILL.md> when choosing tests. Read repository instructions.
Base: <sha>. Owned files: <paths>. Do not edit: <other lane paths>.
Push owner: <name>. Authorized PR actions: <actions>. Tools: <limits>.
Feedback inbox and acks: <paths, or native message transport>. Read
feedback-inbox.md for CLI fallback. Read unhandled versions at safe
checkpoints and before commit, push, and final report. Do not busy poll.

Complete these tasks in dependency order. Before review, run fast, cheap
local checks: format, focused lint or compile, and small tests or one-off
proofs. Do not run the full repository CI suite. Leave slow required checks
to CI or a separate scheduled run; record them PENDING. Write code, commit,
and record each requirement's command, expected and observed result,
actual commit, and raw output path in <RUN>/proofs/<PR>.md. Keep missing
proofs UNVERIFIED. Do not add tests that merely repeat the implementation.
You may complete related tasks in one turn. No per-task reviewer is needed.
Always finish one fresh adversarial review before first PR submission.
Record its candidate, any repaired candidate, and closure proofs. Do not
submit with initial blocking findings open. Repair with useful executable
proof or valid disposition. If useful proof is impossible, request an owner
decision and keep the item open. Record independent closure needs for the
post-CI decision. Do not dispatch another adversarial review before CI settles.

You own validation and repair of all feedback for your code, including CI,
Macroscope, human comments, and local review. Validate each finding before
fixing it. Routine repairs close through useful executable evidence. Preserve
risk and recheck flags for security, authorization, ownership, cancellation,
concurrency, stored data format, public API, shared contract, substantial new
behavior, and inadequate executable closure. Do not dispatch a reviewer in
the CI loop. The orchestrator assesses accumulated divergence only after
current-head CI and Macroscope succeed and feedback is handled. A required
independent scoped review must pass before its thread can resolve.

Keep work inside your lane. Escalate missing access, unclear requirements,
owner decisions, and shared changes with evidence. Do not start another
implementer or reviewer. Stop and report when repeated reads or edits make
no progress. Finish or stop your chore agents and commands before reporting.

Write the full report to <RUN>/reports/<session>.md. Your final message is
under 1,500 characters: commits, proof results and paths, ready-for-review
scope, and open items. Task completion does not mean PR readiness.
```

## Handle available feedback

```text
Validate and address feedback for <PR> from <raw feedback paths>.
Current head: <sha>. Local findings: <IDs and scenarios>. Read the current
requirement sections <references>, including MUST, MUST NOT, and exact
waiver IDs. Preserve each comment's source head. Check older comments
against current code; older CI results do not establish current status.

For each item, record stable source ID and version, source link and head,
current head, disposition,
evidence, fix commit, closure check, and required review scope in
<RUN>/feedback/<PR>.md. Dispositions: DEFECT, NOT A DEFECT, OWNER, BASE,
ENV, or BLOCKED. Reject a report only with a concrete trace or reproduction.
If later code already fixed it, supply fix evidence. Do not waive a
requirement or silently adopt a design suggestion.

Start accepted repairs as soon as they are actionable. Do not wait for a
complete CI run or all Macroscope comments. Handle newly delivered items at
a safe point in this session; do not cancel useful work or start another
fixer. Group ready related items when that helps, without delaying repairs.
Reproduce before repair when practical. Check related paths for the same cause, and run a useful regression check
plus fast affected local checks after repair. Slow required proofs remain
pending until CI or a separate check completes them. Record raw output
and actual commits. Preserve scoped-review flags from the initial reviewer. Identify
risk changes or added behavior for the deferred post-CI review decision.
Do not start a mid-loop review. A failed or missing closure proof leaves the
item unhandled. Record item-version receipts and handled acks when using
the durable inbox.

Push and reply only within the authorized PR actions <actions>. For a shared
stack, report lane commits and proposed replies to <push owner>; do not
switch branches or edit another lane. For an owned standalone PR, follow
<babysit-pr/SKILL.md>. Replies start with the bot prefix. Resolve only after the named closure proof and any required independent
scoped review pass. A repair can push after fast checks while that review
remains deferred. Record threads open solely for deferred review as handled
with proof; owner decisions, blocking defects, and missing proof stay
unhandled. Guard replies by validated head and last comment version.
External resolution uses best-effort checks, not an atomic mutation. Leave
newer or uncertain items, questions, disagreements, and owner decisions open.

Report commits, disposition counts, proof paths, scoped-review requests,
and unresolved decisions. Do not ask for a routine reviewer approval turn.
New heads still need all required CI checks and approvals before readiness.
```
