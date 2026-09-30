---
name: executing-plans
description: Run an approved plan with one implementer per lane, direct implementer handling of CI feedback, a required review before PR submission, conditional review after CI, and proof-based repair. Use for changes with several tasks. Supports Claude Code, the Codex app, CLI, and Cloud.
---

# Executing plans

You are the orchestrator. You own delivery, dependencies, integration, and
unresolved decisions. User instructions take precedence over this skill.
Each lane's implementer owns its code, proofs, and PR
feedback. The reviewer finds defects in an independent context.

The default flow is:

```text
implement tasks -> fast local checks -> clean committed candidate
  -> fresh adversarial review -> repair initial findings with proof
  -> first PR submission -> CI and Macroscope feedback to same implementer
  -> current-head checks succeed and feedback is handled
  -> assess accumulated behavior and risk changes
  -> conditional second adversarial review -> readiness evidence
```

Always finish one fresh adversarial review before the first PR submission.
Record the reviewed candidate, repaired candidate, and closure proofs. Do
not submit with an initial blocking finding open. Routine initial repairs
close with proof. Do not dispatch a second adversarial review before CI
settles. Track independent closure needs for the post-CI decision. If useful
proof is impossible, request an owner decision and keep the item open.

During CI and Macroscope loops, send all feedback directly to the persistent
implementer as it becomes available. Do not run reviewer triage or adversarial
repair reviews in that loop. Track risk and pending review closure flags.
After current-head checks succeed and feedback is handled, assess the total
change from the first review. A second review is conditional on behavior and
risk changes. Line count does not decide it. A verdict alone is not readiness.

Read your platform variant now:

- Claude Code: `references/claude-code.md`
- Codex: `references/codex.md`

OpenCode has no orchestration variant. Use Claude Code or Codex for this skill.
`<skill dir>` means the directory that contains this file.

## 1. Start

1. Read the approved plan and the repository instructions on the path to the
   code. Each requirement needs a proof. If proofs are missing, use
   `writing-plans`. Read Ref plans directly with the Plans tools and follow
   `working-with-ref`. Pass Ref IDs and section references, not exported
   copies. Use existing paths for repository plans.
2. Check tasks for file conflicts, shared contracts, contradictions, and gaps.
   Record each decision as `Ruling: <what> - <why> - <cost if wrong>`.
3. Name the implementer, reviewer, and chore models with `model-choice`.
   Existing user choices and the approved plan take precedence.
4. Record the base commit, branches, PR map, and lanes. Use the current
   worktree unless parallel lanes need separate worktrees. Name one
   implementer as the owner of each PR. If several lanes produce one PR, name
   its owner before integration. Each lane keeps ownership of its files.
5. Check the tools, writable paths, Ref access, and GitHub access. Follow the
   Codex variant for app and Cloud limits. Do not change host configuration
   or install a second CLI to make the workflow run.
6. Create one run directory per orchestrator session:

   ```text
   <writable run root>/<YYYY-MM-DD>-<repo>-<plan slug>-<run ID>/
     log.md       models, lanes, PR owners, commits, review scope, decisions
     brief.md     verified commands, baseline, repository and plan references
     tasks/       task deltas and starting paths
     reports/     implementer and chore reports
     feedback/    finding records and raw PR feedback, grouped by PR
     inbox/       durable item versions and acknowledgements for CLI lanes
     proofs/      requirement results and output paths, grouped by PR
     prompts/     dispatch prompts when the platform needs files
     sessions/    Codex session files
   ```

Use `~/.agents/runs/` when writable. Otherwise use a host-provided writable
artifact directory or a scratch directory outside tracked source. Use a
short random run ID when the host supplies no session ID. Share the absolute
path with agents. Do not write state into the installed plugin directory.

`$RUN` below is this directory. Record each session start, task completion,
review candidate and scope, feedback disposition, push, and recovery before
the next action. Never repeat work that the log and git show as complete.
Keep the run directory for a requested retro. Before a Cloud task ends,
preserve the log, feedback index, and proof records as supported artifacts.
Local cleanup may remove a run 30 days after its PRs merge.

## 2. Prepare the context

Pay the environment setup cost once. Check git status and record the exact
starting commit. For a clean start, reuse completed CI evidence for that
commit when its named checks cover the needed baseline. Record the CI links,
commit, checks, and results. A green result on another commit, a pending run,
or a suite with no relevant coverage is not baseline evidence.

Do not run every plan proof before implementation. Run environment status
commands needed for the task, plus new or one-off verification commands and
checks that CI does not cover. If baseline evidence is missing or stale, run
only the checks needed to resolve that gap. Mark checks for new behavior as
NOT APPLICABLE on the base when that behavior does not yet exist. Record
existing failures, service needs, and environment problems.
Start repository-required helpers only when the host
supports them. Record their commands and limits in the log. Cloud setup
must use available services and credentials, not the user's local machine.

Put these items in `$RUN/brief.md`:

- Repository paths, worktrees, branches, base commit, PR owners, and file
  ownership. Include repository git rules and the stack push owner.
- Exact format, compile, lint, test, and service commands to use. Mark which
  ran in preflight, which reuse exact-commit CI evidence, and which await the
  implementation. Include wrappers, ports, baseline results, and failures.
- Approved plan and design IDs or paths, relevant sections, and revision
  metadata when available. The plan remains the source of requirements.
- The absolute path to this plugin's `audit-tests/SKILL.md`. Require useful
  tests or repeatable one-off proofs, subject to repository coverage rules.
- Report paths. Implementer and chore final messages stay under 1,500
  characters. Full reports go to `$RUN/reports/<session>.md`. A review exists
  only as the reviewer's final message; finding records are not full reviews.

Each implementer reads the full approved plan and design once at session
start. A replacement does the same. Each task brief points to requirement
IDs and contains only deltas, rulings, starting paths, affected callers, and
paths the lane must not edit. Do not copy a reduced version of the task spec.

When a plan changes, update its source and send affected lanes the changed
section references. They read those sections before continuing. If a change
invalidates active work, interrupt at a safe point and preserve edits. After
compaction, read the current task and governing decisions again.

Watch the first lane's first calls. Correct a wrong directory, command, or
sandbox before it causes repeated failures.

## 3. Assign ownership and sessions

- **Implementer:** one persistent session per lane, across tasks and PRs. Give
  it the tasks for a coherent PR in one turn when dependencies allow. It
  validates review findings and CI comments, writes all lasting code and
  tests, runs proofs, and prepares replies. It owns standalone PR pushes and
  replies when the task authorizes those actions and its tools support them.
- **Orchestrator:** schedules lanes, integrates their work, checks delivery
  evidence, and resolves escalations. Pass feedback paths directly to the
  owning implementer. Do not add a reviewer triage turn or rule on every
  routine finding. Coordinate shared-stack pushes and replies when lane
  sessions cannot safely perform them.
- **Reviewer:** a fresh session for one PR's broad review. Give it
  `references/review-prompt.md`, the base and candidate commits, plan and
  requirement references, briefs, and raw proof output paths. Do not give it
  the conversation, the implementer's report, or design arguments. It owns
  the bug search and returns all confirmed findings as one batch.
- **Chore:** optional help for long commands or large feedback collection.
  Prefer repository commands and bundled scripts for mechanical collection.
  A collector gathers evidence only. It does not classify findings or direct
  fixes. Read `references/pr-collector.md` only when using a collector agent.

Parallel lanes need disjoint files and stable contracts. Use the repository's
worktree method and build limits. Do not put worktrees in session scratchpads.
Keep one writer per worktree. While a reviewer uses temporary edits or runs
proofs in the lane worktree, the implementer and its child agents stay idle.
The first review precedes submission. CI and external review run after submission.
A later independent review starts only after the current-head check gate.

For complex work, choose two independent reviewers with different focus
areas in the same review phase. They may run in parallel only in separate
checkouts or read-only snapshots. Temporary edits require separate checkouts.
Record the focus areas and wait for both reports before accepting the phase.

Retire a reviewer after the first pass unless a later review is needed.
Reuse it for a related scope only while its context remains intact.
Start a fresh reviewer for another PR, an unrelated scope, or compaction.
Its handoff contains commits, relevant decisions, and open finding IDs and
scenarios, not the previous review or transcript. There is no turn-count
rotation rule and no reviewer session for routine CI feedback.

Keep the implementer session unless it dies, moves to an unrelated area, or
needs a stronger model. A replacement gets the run brief, full plan and
design references, task deltas, commit and diff summaries, open findings,
proof paths, and lane log entries. Do not discard uncommitted work.

Implementers and reviewers may use fast-tier chore agents for bounded reads
or commands. They keep implementation and review decisions in their own
sessions. Finish or stop all child agents before returning the final report.
Do not start extra fixers or agents that only drive other agents.

## 4. Implement the PR

Send `references/implementer-prompt.md` with the lane, PR, task, and run paths.
The implementer works through its assigned tasks in dependency order:

1. Write the code and useful tests or one-off proofs. Apply `audit-tests` to
   test design. Use existing coverage when it proves the behavior.
2. Run fast, cheap local checks after writing the change: format, focused
   lint or compile, and small tests or one-off proofs for the changed behavior.
   Use the commands and scope in the brief. Do not run the full repository
   CI suite before review. A required slow or full-suite proof runs in CI or
   a separate scheduled check; record it as pending until it completes. Fix
   local failures and commit. Coordinate costly commands with the build limit.
3. Record each requirement's commit, command or named test, expected result,
   observed result, and raw output path in `$RUN/proofs/<PR>.md`. A code read
   or a summary claim is not an executed proof. A suite counts only when a
   named test proves the requirement. Record missing evidence as UNVERIFIED.
4. Report task commits and evidence. The next related task does not need an
   adversarial review of the previous task. A task is implemented when its
   code and proofs are complete. It is ready only when its PR is ready.

The run brief must distinguish fast local checks from slow checks that
belong in CI. Do not replace a missing fast check with the full CI suite.
Before review, report the fast-check results and any pending slow proofs.

The implementer may finish several tasks in one turn. Do not ask it to stop
part way for a task review or an acknowledgement. Resolve an unclear contract
through the owning plan or owner decision before dependent work. Keep the
fresh adversarial review at the complete pre-submission candidate.

Integrate parallel lanes before reviewing their combined PR candidate. Run
compile and targeted checks after integration where lanes share a contract.
The PR owner collects each lane's proofs and handles integration feedback
through the owning lane, without editing another lane's files.

## 5. Review, submit, and handle feedback

### Review before first submission

After integration and fast local checks, record the clean candidate SHA.
Start a fresh independent adversarial review before opening or submitting
its first PR. The reviewer checks the whole diff, changed failure paths,
contracts, and proof quality. It runs focused checks to establish defects.
It does not run the full repository CI suite. Slow proofs can be PENDING.

Check HEAD and status before and after review. They must match the candidate.
The reviewer restores only its temporary edits. If the candidate changes,
repeat the affected scope on the correct candidate. Give findings stable IDs
and preserve each risk and recheck flag. Send all findings to the implementer.

The implementer validates and repairs initial findings with useful
executable closure proofs or valid dispositions. Record risk changes and
independent closure needs for the post-CI decision. Do not dispatch another
adversarial reviewer before that gate, even for a major repair. If useful
proof is impossible, request an owner decision; do not invent a review
exception. Record the first reviewed candidate, repaired candidate, finding
dispositions, and proofs. Initial blocking findings and incomplete initial
scope prevent submission. A tracked independent closure need may remain
for the deferred post-CI review when the blocking defect has proven repair.

Then push and submit the PR with the repository's stack tool when authorized.
Describe the behavior, requirements, verification, and known gaps. Do not
paste the review report. The first review does not certify final readiness.

### Deliver all CI and Macroscope feedback directly

Start `babysit-pr` on the first fresh item, current-head failure, or conflict.
Send each item and raw evidence to the same implementer as it becomes
available. Do not wait for a batch, other PRs, all comments, or all checks.
Keep collecting sources and record partial or failed sources. A collector
only gathers evidence. There is no reviewer triage or mid-loop adversarial
repair review. Use native messages for native sessions. For active CLI
sessions that cannot receive messages, use `references/feedback-inbox.md`.
Resume idle sessions with the inbox path. Do not interrupt useful work.

Keep each item in `$RUN/feedback/<PR>.md`: stable source ID and version,
source link and head, current head, scenario, raw evidence, disposition,
fix commit, named closure proof, risk flags, and pending review scope.
Preserve older-head comments and source evidence. Validate them against
current code. Older CI results do not prove current-head status.

The implementer reads each cited requirement's MUST and MUST NOT rows and
exact waiver IDs. It validates every item before changing behavior:

- **DEFECT:** establish the trigger, faulty path, and result. Repair it and
  check related paths for the same cause. Blocking defects prevent readiness.
- **NOT A DEFECT:** supply a concrete trace or reproduction. For a defect
  already repaired, give the repair commit and proof instead.
- **OWNER:** an unresolved scope, contract, design, or waiver decision.
  Send evidence and the exact decision to the orchestrator. Keep it open.
- **BASE or ENV:** establish the actual cause and baseline or environment
  evidence. A required failing check still prevents readiness.
- **BLOCKED:** record missing proof or failed access. Keep it open.

An item cannot waive a requirement without the needed owner approval. Record
approved decisions in the owning spec or repository equivalent.

### Repair with proofs and track deferred closure

Start accepted repairs promptly. Group ready related items only when that
will not delay repair. Run the useful reproduction or regression check and
fast affected checks. Do not run full repository CI suites as local checks.
Record actual commits and raw results. Format and compile alone do not prove
a runtime repair. Missing or failed closure proof leaves the item unhandled.

Flag changes to security or authorization, ownership, cancellation,
concurrency, a public API, stored data formats, shared contracts, substantial
new behavior, and repairs without adequate executable closure. Keep named
pending review scopes. Do not dispatch a reviewer during the CI loop.

Push repaired code after fast checks. Do not wait for slow CI or future
comments to push it. Use one push owner for a shared stack. Lane implementers
supply commits and replies; they do not edit another lane or switch branches.
New heads need new required CI and Macroscope results.

Reply with `🤖 ` and evidence. Resolve a repaired thread only after its named
closure proof passes and any required independent scoped review passes.
A thread waiting solely for deferred review remains open. Other slow checks
still gate readiness; their pending state need not block that thread's
closure. Leave questions, disagreements, and owner decisions open.

Before posting or resolving, verify the PR head and last comment version
against the validated item. GitHub has no compare-and-swap parameter for
thread resolution. These are best-effort pre-mutation checks, not atomic
closure. Leave newer or uncertain items open and collect them again.

### Assess divergence only after checks finish

Wait until all current-head CI and Macroscope checks finish
successfully and all available feedback is handled with evidence. Here,
**handled** means validated, dispositioned, and repaired with available
proofs. Identified threads may remain open solely for a deferred independent
review. This exception does not cover owner decisions, blocking defects,
missing proof, incomplete sources, or unhandled new comments. Refresh the
head and sources before applying the gate. Do not hide new feedback.

Compare the current candidate with the first reviewed candidate, including
repairs to initial findings. Assess the
accumulated behavior and risk changes, proof quality, and pending closure
flags. Record SECOND REVIEW REQUIRED or SECOND REVIEW SKIPPED, the reason,
commits, evidence, and scope. Do not use line count as the trigger. Security
or authorization, ownership, cancellation, concurrency, public API, stored
data format, shared contract, substantial new behavior, or inadequate
executable closure can require a second adversarial review. Small repairs
that preserve contracts and have useful proofs can skip it. A required
independent closure flag cannot be skipped without an approved disposition.

When needed, give the reviewer the first reviewed and current candidates,
requirements, risk changes, finding IDs, reproductions, and raw proofs. Review
the changed behavior and related regression paths. Broaden the scope only
when the accumulated change needs it. Do not automatically repeat the whole
review after every push.

A second-review finding goes to the implementer and returns the PR to the CI
loop. After repair, finish new current-head checks and handle new feedback
before a needed scoped recheck. Preserve the original review baseline and
recheck only the affected scope. When the review passes, close eligible
threads, refresh sources, and check final readiness.

## 6. Keep sessions healthy

- Record each session's ID, worktree, owner, and state when it starts.
- Use event waits bounded by the host limit, at most 60 seconds per call.
  Check live sessions and their worktrees after each stretch. Silence alone
  is not proof of progress.
- A turn is finished when the platform says it ended, its final report
  exists, and its reported commits are in git. In Codex, finish all commands
  before ending the turn. If the host cannot wait for remote CI, record
  PENDING and give a resumable handoff. Do not claim readiness. In Claude Code, a lane may end a turn for its own
  background command and resume on completion; do not redispatch its task.
- Treat no new event for 20 minutes, with no running command, as a stall.
  A live build or test gets three times that interval before recovery.
- Recover by stopping leftover work and resuming the same session. Ask it to
  check status and recent commits, read its current task, and continue without
  repeating committed work. After two failed resumes, replace it with a
  handoff. Preserve uncommitted edits.
- Switch an unavailable model using `model-choice`. Restore the planned model
  when available, subject to the review scope and clean-context rules.
- Restart required helpers after a restart or disk-full error. Give waiters
  total timeouts and bound each API call to 60 seconds with a supported
  timeout tool or command timeout. Stop an old
  waiter before starting another. Back off on transient tool failures.
- Check the worktree volume after each wait. Below 15% free space, remove
  finished worktrees before the next build. Release their services first.
  A pending repair, proof, or CI result is unfinished work. Never remove a
  worktree used as a live session's directory. Stop its sessions first.
- When a person must decide, record the question and end the turn. Do not
  poll for that person.

## 7. Escalate exceptions and improve the process

Use `model-choice` for repeated failed repair attempts on the same cause.
Count attempts by their check results, not reviewer turns. Repeated failures
need a cause analysis and a different approach, not equivalent pushes.
Record a recurring cause and the workflow or brief change that prevents it.

The implementer escalates unclear requirements, disputed findings it cannot
settle with evidence, missing proof, and work outside its lane. The
orchestrator assigns the owning lane or coordinates a contract decision. It
does not add a reviewer triage pass for all CI comments.

Ask the user when the needed action is outside existing authorization or the
approved plan cannot be met. Keep working on independent tasks. An unresolved
or deferred blocking finding is an open item, not a passing result.

## 8. Finish with evidence

Check readiness from recorded evidence after the conditional review decision:

1. Every PR has its first pre-submission review and repaired candidate
   recorded. Initial blocking findings are closed. The post-CI divergence
   decision is recorded. Any required second review and scoped recheck have
   passed, and review-dependent threads are closed with their named proofs.
2. Every requirement has an executed proof with its command, result, output
   path, and final candidate commit. Inspect command or CI evidence, not a
   summary claim. If a proof is missing or stale, run it once on the final
   candidate, using a chore for a long run. Do not repeat evidence already
   complete on that commit. FAIL and UNVERIFIED prevent completion.
3. All required CI checks are green on each PR's current head. Approvals and
   addressed feedback are present, and no merge conflict remains. A required
   pending check, an earlier green head, or a missing approval is not ready.

Each PR needs its own proofs. For a stacked plan, also verify the combined
requirements on the final commit of the top PR. A later push invalidates
affected rows; refresh them on the new commit. Do not relabel an earlier run
with the new SHA. Unaffected rows remain historical evidence until the final
candidate check confirms the needed results. CI can provide named proofs when
its output establishes those requirements on that candidate.

After a rebase, run CI on the new head. Rerunning an old merge commit does
not include a base-branch fix. Rebase and push when the fix is on the base.
Do not merge automatically.

Append deviations, significant defects, process corrections, and environment
problems to the plan's Execution notes. Update Spec changes when needed.
Stop live sessions before removing finished worktrees and temporary files.
Report PR states, proof counts and failures, deviations, model substitutions,
and open items. Keep the run directory. Run `session-retro` only on request.

## Token discipline

- Pass IDs, section references, paths, and commits instead of copied context.
- Keep one implementer across related tasks, repairs, and CI feedback.
- Use scripts for collection and give evidence paths directly to implementers.
- Keep raw logs out of the orchestrator's context. Read full reports only for
  unresolved decisions. Record compact findings instead of full reviews.
- Run one broad review before submission. Assess later review only after CI
  and feedback settle. Spend it on the accumulated changed risk and scope.
- Let context compact at a phase boundary after writing the run state.
