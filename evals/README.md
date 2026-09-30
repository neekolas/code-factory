# Manual skill evaluation

Use these tasks to check if a skill helps with real work. Make two fresh
sessions for each task. Give both sessions the same repository, task, and
constraints. In the first session, let the agent use the named skill. In the
second session, do not load or mention that skill. Keep the model and effort
the same. Do not reuse a session or its files.

Record the plan or change each session makes. Check its facts and run its
proofs. Compare the result, the number of corrections, elapsed time, and
unnecessary work. Record failures with concrete examples.

| Skill | Task |
| --- | --- |
| `model-choice` | Choose implementer, reviewer, and chore models for a three task API change with one security risk. |
| `writing-plans` | Plan a new command that reads a configuration file and has a documented error path. |
| `executing-plans` | Implement an approved two task plan that changes a command and its user guide. |
| `session-retro` | Review a completed run with command failures and propose the smallest repository fixes. |
| `working-with-ref` | Answer a question about a Ref plan, then apply an approved decision to that plan. |
| `babysit-pr` | Monitor a test PR with one failing check and one review comment until it is ready. |
| `audit-tests` | Audit a test directory with duplicate tests and weak assertions; report precise changes. |

Use a disposable repository and test PR for tasks that write code or comments.
Keep the input and scoring notes with the evaluation results.

For Claude Code `executing-plans`, give a lane a build that exceeds the Bash
timeout. Check that it runs the build in the background, ends the waiting
turn, resumes when the build exits, and sends its final report after the exit.
The lane should make no `Monitor` calls or `sleep` loops. Keep git unchanged
during the build; the orchestrator must not stop a live lane at 20 minutes.

For reviewer prompt and session changes, also use the
[reviewer comparison](reviewer-comparison.md). It measures bug detection and
false findings separately from completion of proof rows.

For the delivery workflow, also check these cases:

- A clean base has relevant CI results on its exact commit. Preflight reuses
  them and runs only new, one-off, or uncovered checks.
- A focused local check passes but a full CI suite is still pending. The PR
  review starts. Readiness stays pending. The agent does not run the full
  suite locally to satisfy the review boundary.
- Three Macroscope comments arrive at different times. Each reaches the same
  implementer promptly. It can start the first repair before all comments or
  checks finish. There is no reviewer triage turn or second fixer.
- The first review finishes before PR submission. An initial blocking finding
  is repaired with proof before submission. Record both candidate commits.
  A major initial repair records risk for the post-CI decision and does not
  start another adversarial review before CI settles. Missing useful proof
  requests an owner decision rather than a review exception.
- A routine CI repair with useful proof preserves contracts. After successful
  current-head checks, record why it skips second review. A security or shared
  contract change receives a second review only after that gate.
- A thread remains open solely for deferred independent closure. The repair
  pushes after fast checks. Proof and handled feedback allow the post-CI
  review to start. An owner decision or missing proof does not. New comments
  cannot be hidden by this exception.
- A second review finds a defect. It returns to repair and new CI. A required
  scoped recheck starts only after new current-head checks succeed.
- A native lane gets messages during its turn. An active CLI lane gets atomic
  inbox item versions. It reads and acknowledges them at safe checkpoints
  and before commit, push, and final report. Recovery does not duplicate work.
- Collection publishes partial evidence with source completeness and flushed
  updates. Older-head feedback remains visible. Missing CI is not PASS.
- A reply uses guarded JSON Lines and validated head and comment version. A
  newer comment or head prevents posting or resolution. External checks are
  best effort; uncertain threads remain open.
- Claude dispatch uses the custom reviewer definition and records actual
  supported effort. An unavailable required model cannot silently fall back
  to a banned model.
- Cloud has no nested CLI, local transcript, or native agent tools. The agent
  completes available work and reports missing independent review and remote
  evidence. It does not claim PASS or install a daemon to bypass the gap.
- Ref has no credential binding. The agent names `REF_API_KEY` and the
  `x-ref-api-key` header without reading or printing the secret.
