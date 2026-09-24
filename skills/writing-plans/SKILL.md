---
name: writing-plans
description: Use before a change that needs more than one commit, touches a public contract, or needs a decision from the user - writes a plan whose requirements use the repository's spec row format, gets a clean-context adversarial review, and stops at user approval. Replaces code-factory:writing-specs
---

# Writing plans

A plan says what will change, why, how each result is proven, and how the work
splits into PRs and sessions. It does not say how to write the code. The
implementer is a strong model: give it goals, limits, and proof.

This skill ends when the user approves the plan. `executing-plans` runs it.

## 1. Understand

- Read the repository instructions on the path to the code (`AGENTS.md`,
  `CLAUDE.md`). If the repository has specs, read its spec format and the specs
  that own the area. In libxmtp that is `docs/specs/SPEC-spec-format.md` and
  the spec that `docs/specs/README.md` names.
- Send broad reads to a subagent and keep its conclusions, not the files.
- Ask the user one question at a time, and only when the answer changes the
  plan and the code cannot answer it.
- When a choice has real trade-offs, give two or three approaches with your
  recommendation first. Let the user pick before you write the plan.

## 2. Write

Put the plan in Ref when the session has Ref (Claude Code through the Ref
plugin, Codex through the `Plans` MCP server) and the user uses it. Otherwise
write `docs/plans/YYYY-MM-DD-<slug>.md`, or the path the user names. The format
is the same in both places.

Size the plan to the change. A small fix is a lead, a requirements table, and
one task. Leave out a section that would say nothing, except `Spec changes`,
which is always present.

### Requirements

A plan has two kinds of requirement, with very different bars.

- **Plan requirements** (IDs `P1`, `P2`, and so on). The bar is low. A plan
  requirement is anything this work must do or prove: fine-grained
  behaviour, implementation details, migration steps, tooling, CI, docs.
  Expect many. They live only in the plan and never appear in code comments.
- **Spec requirements.** The bar is high. A spec requirement is a promise the
  system keeps long after this plan: an API boundary or an observable
  behaviour that other code or people rely on. Expect few, and only in a
  repository that keeps specs. When the repository has a spec authoring
  guide (in libxmtp, the `authoring-specs` skill), its admission test decides
  what qualifies; apply it before you propose a spec change. When in doubt,
  keep the requirement in the plan: a plausible but unimportant rule in a spec
  costs every later reader.

Write both kinds the same way. One row each, in a table with the header
`| ID | Title | Requirement | Why |`:

- Condition first, then the actor, then MUST or MUST NOT (the EARS order:
  when, while, where, if ... then). Never SHALL. One obligation per row, at
  most three sentences. A title of two to seven words.
- Name the field, the value, and the comparison. Give a bound its number.
  Replace stand-in words (earliest, latest, bounded, sufficient, promptly,
  appropriate) with what they stand for.
- The Why cell says what breaks without the rule, or is empty. It never
  repeats the rule.
- Reference an existing spec requirement by its ID; do not restate it. When
  the repository has its own spec format, write new spec rows in that format.

Every requirement has a proof: a test (name it, existing or to be written) or
a command with its expected result. Mark proofs that need a person as manual.
A test that proves a spec requirement carries the repository's backlink when
it has one (in libxmtp, `verifies: PREFIX-NNN`). Plan IDs are never linked
from code.

**Spec changes.** Every plan has this section. It lists the spec requirement
IDs the plan implements, the exact text of every spec row it adds or amends,
and the IDs it removes, or it says "None". Writing the spec edit is a task,
usually in the first PR. When the user approves the plan, that approval covers
the exact spec text in this section and nothing else.

### Tasks

A task is the smallest change that has its own tests and that a reviewer could
reject while approving its neighbour. Each task has:

- a goal sentence;
- the requirement IDs it covers;
- the files or areas it changes;
- decisions already made, so the implementer does not reopen them;
- `Consumes` and `Produces` when another lane depends on its interface: exact
  names and types;
- verification: the proofs from the requirements it covers, as commands;
- dependencies on other tasks.

Include code only where it is important. Most code is not. Show:

- key interfaces: signatures, types, protobuf messages, public API, even when
  no other lane depends on them;
- every database schema change, and every important query, as SQL;
- pseudo-code for a key algorithm or a complicated verification.

### Delivery

- **PR map.** Which tasks go in each PR, the base branch, and the stack tool.
  A PR may hold several tasks. Say which PRs cannot pass CI alone, and why.
- **Lanes.** A lane is a set of tasks that share code or decisions. One
  implementer session runs a lane, across tasks and across PRs. Lanes run in
  parallel only when they share no files and no contract that is still
  changing. Say why each parallel pair is disjoint.
- **Risk.** Mark a task `frontier` when it needs the top model tier: security,
  concurrency, protocol state, or data migration.

### Template

```markdown
# <Title>

<Two to four sentences: what changes, why, and the result a user sees.>

## Context
- Catalyst: <issue, thread, or request>
- Code: <paths that change and paths that must not break>
- Specs: <spec files that own this area, or "none">
- Behaviour that must not change: <list, each with the test that guards it>

## Decisions
- <Decision> — <one-line reason>
Open questions (at most three, each with the answer assumed until the user replies):
- <Question> — assumed: <answer>

## Requirements
| ID | Title | Requirement | Why |
| --- | --- | --- | --- |
| P1 | <two to seven words> | When <condition>, <actor> MUST <result>. | <what breaks> |

## Spec changes
Implements: <spec IDs>. Removes: <IDs>. Or: None.
| ID | Title | Requirement | Why |
| --- | --- | --- | --- |
| <new or amended spec row, exact text> | | | |

## Public surface
<Types or functions added or changed in bindings or SDKs. Omit if none.>

## Tasks
### Task 1: <title>
<Goal sentence.>
- Requirements: P1, JOIN-012
- Files: <paths>
- Decisions: <list>
- Consumes / Produces: <exact names and types, when another lane needs them>
- Code: <key interfaces, schema changes and queries as SQL, pseudo-code; omit if none>
- Verification: <command> — expect <result>; manual: <step>
- Depends on: none

## Delivery
| PR | Tasks | Base | Notes |
| --- | --- | --- | --- |
Lanes: A = Tasks 1–3 (one session); B = Task 4 (parallel with A: <why disjoint>).
Frontier tasks: <list or none>.

## Models
Implementer: <model, effort>. Reviewer: <model, effort>. Chore: <model, effort>.
Or: "Ask at execution".

## Execution notes
<Added by executing-plans: deviations, issues found, repository stumbling blocks.>
```

In Ref, follow `working-with-ref` for the title line, task headers, and
review requests. Keep the other sections.

## 3. Adversarial review

Every plan gets one clean-context review before the user sees the final
version. A wrong line in a plan becomes many wrong lines of code, so this
review has the highest return of any review.

- **Reviewer:** the reviewer model from `model-choice`. It must be a different
  model from the one that wrote the plan.
- **Input:** the plan as a file and the repository path. Export a Ref plan to
  a file first. Nothing else: not the conversation, not your reasons.
- **Output:** the reviewer's final message to you. Never put a review in Ref,
  a doc, an artifact, a PR comment, or a file. If the transport needs a file
  (`codex exec -o`), read it and delete it.
- **Claude Code:** an `Agent` call with the reviewer model, or for a Codex
  reviewer `codex-session.sh start ... read` from `executing-plans` (see its
  Claude Code file). A plan review runs no build, so `read` is enough.
- **Codex:** `spawn_agent` with the reviewer model and `fork_turns: "none"`.

Prompt:

```text
Adversarially review this implementation plan. Assume it is flawed and find how.
Plan: <file>. Repository: <path>. Read the repository's instructions
and the specs the plan cites. Do not edit anything. Do not start subagents.
Your final message is the review; do not write it anywhere else.

Attack, in order:
1. Requirements that are untestable, ambiguous, or use a stand-in word
   (earliest, latest, bounded, sufficient, promptly) instead of a field, value,
   or comparison. Requirements with no proof, or a proof that cannot fail.
2. Coverage both ways: a goal with no requirement, a requirement with no task,
   a task with no requirement.
3. Spec fit: a spec change that does not meet the spec bar (spec bloat); a
   lasting API or behaviour promise left only in the plan; a restated spec
   requirement; a conflict with an approved spec; spec text that is not given
   exactly in Spec changes.
4. Changed behaviour with no requirement that keeps the old behaviour.
5. Feasibility: read the code in the impact area. Name any design the code
   cannot support as written.
6. Missing cases: concurrency, dependency failure, retries, restart and
   recovery, limits, security, migration and rollback, older clients.
7. Delivery: a task that leaves an invalid state; lanes called disjoint that
   share files or a contract; a PR that cannot pass CI and does not say so; a
   verification that neither a local run nor CI can execute.
8. Non-goals that hide work the goals need.

Try to refute each finding before you report it. Report only real defects.
No style comments. Prefer one strong finding over several weak ones.

Format:
Verdict: PASS | ISSUES
Findings:
- [CRITICAL|MAJOR|MINOR] <section or ID> — <defect>
  Consequence: <what goes wrong in implementation if unfixed>
Declined to judge: <each thing you set aside as out of scope, with the reason>
Not verified: <what you could not check>
```

Triage each finding yourself: fix it, reject it with a reason, or ask the user
when the fix changes scope or a contract. Review again only after a structural
rewrite, at most twice. Findings still open after that go into Open questions.

## 4. Approval

Give the user the plan's link or path, a short summary of what the review
changed, and the open questions. Then end your turn. Do not poll a review or
approval tool in a loop; the user's reply starts the next turn. Approval lets
`executing-plans` start, and approves the exact spec text in Spec changes.
