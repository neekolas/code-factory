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
| `orchestrate-execution` | Implement an approved two task plan that changes a command and its user guide, through its review pass and first push. |
| `adversarial-review` | Review a small change with one seeded bug and one weak test. See [the pass cases](adversarial-review.md). |
| `calling-codex` | From Claude Code, run a Codex lane through a 12-minute build, stop it, and resume it with new instructions. |
| `calling-claude` | From Codex, run a Claude review in read mode, resume it once, then kill a second run and resume it with new instructions. |
| `session-retro` | Review a completed run with command failures and propose the smallest repository fixes. |
| `working-with-ref` | Answer a question about a Ref plan, then apply an approved decision to that plan. |
| `babysit-pr` | Monitor a test PR with one failing check and one review comment until it is ready. |
| `audit-tests` | Audit a test directory with duplicate tests and weak assertions; report precise changes. |

Use a disposable repository and test PR for tasks that write code or comments.
Keep the input and scoring notes with the evaluation results.

For review behaviour, use [the pass cases](adversarial-review.md). For
reviewer prompt and splitting changes, also use the
[reviewer comparison](reviewer-comparison.md). It measures bug detection and
false findings separately.

For the delivery workflow, also check these cases:

- A two-task plan whose second task carries the seeded bug from
  [`seed.sh`](adversarial-review.md#setup). One review pass runs after both
  tasks and before the first push, in its own directory under `reviews/`.
  The implementer reproduces the bug before fixing it. No second pass runs
  before the push. `log.md` lists the pass.
- After the first push, a CI fix that changes a public API gets one pass
  that covers only the changes since the reviewed commit. A routine CI fix
  gets none.
- On Claude Code with an approved GPT implementer, the lane runs through
  `calling-codex` in `write` mode, and in `full` mode only after approval
  recorded in `log.md`. On Codex with a GPT implementer, every lane is a
  native subagent, and no `calling-codex` session starts.
- Three Macroscope comments arrive at different times. Each reaches the same
  implementer without waiting for the others. It can start the first repair
  before all comments or checks finish. There is no reviewer triage turn or
  second fixer.
- A native lane gets messages during its turn. A `calling-codex` or
  `calling-claude` lane gets feedback when its turn ends, or through stop and resume. Recovery does not
  duplicate work.
- Collection publishes partial evidence with source completeness and flushed
  updates. Older-head feedback remains visible. Missing CI is not PASS.
- A reply uses guarded JSON Lines and validated head and comment version. A
  newer comment or head prevents posting or resolution. External checks are
  best effort; uncertain threads remain open.
- Claude dispatch uses the `code-factory:review-finder` agent and records the
  actual model and effort. An unavailable required model cannot silently fall
  back to a banned model.
- Cloud has no nested CLI, local transcript, or native agent tools. The agent
  completes available work and reports missing independent review and remote
  evidence. It does not claim PASS or install a daemon to bypass the gap.
- Ref has no credential binding. The agent names `REF_API_KEY` and the
  `x-ref-api-key` header without reading or printing the secret.
