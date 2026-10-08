---
name: orchestrate-execution
description: Guide native orchestration of implementation, code review, and PR feedback with a few rules. Use only when the user explicitly invokes orchestrate-execution.
disable-model-invocation: true
---

# Orchestrate execution

Use this skill only when the user explicitly invokes it. Plan approval alone
does not invoke this skill.

Use [model-choice](../model-choice/SKILL.md) for defaults. Before dispatch,
get user approval for models and effort levels through the approved plan or
`AskUserQuestion` (or the host's equivalent). Repeated failed implementation
attempts can move standard work to the approved frontier model.

- Use native orchestration tools. Let the agent choose task order and parallel work within the approved plan.
- Give each PR one primary worktree. Use temporary worktrees for independent work, integrate before review, and delete them when finished.
- Give each PR one implementer agent. Reuse it for implementation, review fixes, and CI feedback.
- All substantial code changes need adversarial review with the reviewer model before PR submission. Review in the implementation worktree with other writers idle. Reviewers must remove their temporary edits.
- Use fast local checks and tests that prove the changed behavior. Leave slow checks to CI unless repository rules require them locally.
- The orchestrator owns all pushes and runs [babysit-pr](../babysit-pr/SKILL.md) after each push. For stacks, address all feedback from a round before pushing again.
- Send feedback directly to the owning implementer. It must fix the issue or refute it with evidence. Escalate unresolved requirements and decisions.
- Repeat adversarial review only when later changes justify it through changed behavior, risk, or weak proof. Assess this after CI and feedback settle.
- Share paths, commits, and requirement references instead of copied context. Keep enough state to resume without repeating completed work.
- Declare completion only when required checks pass on the current commits, requirements have proof, and blocking feedback is closed. Report remaining gaps clearly.
