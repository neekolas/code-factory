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
