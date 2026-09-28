---
name: audit-tests
description: Judge whether tests detect real regressions. Use for focused test review, new test design, or a scoped audit of weak, brittle, or duplicate tests. Preserve independent contracts and report evidence before cleanup.
---

# Audit Tests

Review the requested test area. Identify tests to keep, delete, merge, or
improve. A code review uses the quality checks below for changed tests and
the coverage they claim; it does not start a repository-wide audit.

This skill is language-agnostic. Adapt test discovery, module boundaries, and verification commands to the repository's existing conventions.

## Core Principle

Prefer tests that protect real behavior. Remove or change tests that mainly protect implementation shape, generated text, incidental structure, or current coding choices.

A low-quality test is unlikely to catch a real bug but likely to break during valid changes.

## Test value checks

Before writing or judging a test, establish:

- The observable result or independent contract it protects.
- A plausible defect that makes the assertion fail.
- The extra risk it covers beyond existing tests. A second layer can add
  value when it exercises transport, serialization, or lifecycle behavior
  that the first layer cannot reach.
- Whether production code supplies the result. A mock, fixture, or copy of
  the implementation must not supply the behavior the test claims to prove.

A vacuous test passes even when the claimed behavior is broken. New or
changed vacuous tests are review findings and must be fixed or removed.
Adding them causes avoidable review cycles.

Check the complete test and the production path it enters. Follow setup,
calls, and assertions to the result. For a failure case, check that it reaches
the intended guard and fails for the intended reason. For a bug regression,
run it against the broken behavior, then the fix. For other new tests, use a
small, plausible temporary defect when needed to establish detection. Follow
stricter repository rules. Restore edits before running the final proof.
If a check cannot run, say what remains unverified.

One-off verification is a valid alternative when a permanent test would only
check incidental text or a one-time migration. Use a temporary script,
command, or manual check. Record the command or steps, input, commit, expected
result, and observed result so another person can repeat it. Do not check in
the helper only to fill a proof row. Retain regression tests for recurring
behavior when they add useful protection, and follow repository requirements.

## Preserve independent contracts

Source inspection, snapshots, ordering checks, and static checks are not
automatically weak. Keep them when they independently protect a public API,
wire format, generated binding, security rule, release artifact, or another
required contract. An intentional contract change may correctly break a test.
Speed and deletion count do not decide test value.

Do not add a public export, flag, or wrapper only to make a test possible when
the real entry point can test the same risk. Before removing an existing test
or support seam, inspect its callers, history, and the proof that will remain.
A failing retained test can expose a product bug; investigate before deleting.

## Workflow

1. Inspect repository structure.
   - Identify language ecosystems, package boundaries, test frameworks, and test commands.
   - In monorepos, define modules by package/workspace/app/library ownership.
   - In single projects, define modules by major source or test directories.
   - Use repository-native metadata where possible: workspaces, package manifests, build files, project files, test config, or CI config.

2. Dispatch bounded audit workers by module when the environment supports it.
   - Prefer explorer-style subagents when they are available and working.
   - Give each worker one module or bounded test area.
   - Ask workers to inspect tests and return structured findings only.
   - Do not ask workers to edit files.
   - If the repository is small, use one worker for all tests.
   - If subagent launch fails because of tool-schema incompatibility, missing tools, or platform limits, stop retrying the same worker type and continue the audit in the parent agent module-by-module.

3. Build a test inventory within the agreed scope.
   - Include test file, test name, behavior under test, inputs and states, assertions, setup, mocks/helpers, and related production code.
   - Note duplicate or overlapping behavior across files and modules.
   - Distinguish unit, integration, end-to-end, contract, snapshot, policy, smoke, and regression tests when the distinction matters.

4. Grade each test.
   - Evaluate behavior value, bug signal, brittleness, uniqueness, setup quality, flakiness risk, runtime cost, and maintenance burden.
   - Assign one action: `keep`, `delete`, `merge`, `upgrade`, `helperize`, or `investigate`.

5. Review across modules.
   - Deduplicate tests that cover the same behavior and inputs.
   - Prefer one clear behavior-level test over several narrow implementation-detail tests.
   - Preserve coverage for important states, edge cases, regressions, contracts, security boundaries, and business requirements.

6. Propose a precise cleanup plan.
   - List tests recommended for deletion with rationale.
   - List tests to merge and identify the surviving test.
   - List tests to upgrade and the behavior/assertion change needed.
   - List repeated setup that should become shared helpers.
   - Include verification commands to run after cleanup.

7. Edit only after user approval unless the user explicitly asked for implementation.
   - Delete tests that add little or no incremental value.
   - Merge duplicate tests into the clearest surviving behavior-level case.
   - Refactor repeated setup only when it reduces real maintenance burden.
   - Avoid broad unrelated test rewrites.

## Subagent Compatibility

The audit must not fail only because a specific subagent type is unavailable.

In Claude Code, if an Explore subagent fails immediately with an API error like `input_schema does not support oneOf, allOf, or anyOf at the top level`, treat it as a platform/tool-schema incompatibility. Do not retry the same Explore subagent repeatedly. Fall back to one of these approaches:

- Use a different available general-purpose subagent type with the same bounded prompt, if the platform supports it.
- Run the module audit sequentially in the parent agent, keeping the same report format.
- For large repositories, process modules in batches and write intermediate notes before synthesizing the final plan.

Preserve the quality bar and output format regardless of whether the audit used parallel workers.

## Worker Prompt Template

Use this shape when dispatching module workers:

```text
Audit tests in <module/path>. Do not edit files.

Return a structured report with:
- Test files inspected
- For each test case:
  - file and test name
  - exact behavior it claims to evaluate
  - inputs, states, and edge cases covered
  - assertions made
  - setup steps required
  - mocks, fixtures, factories, or helpers used
  - production behavior or requirement protected
  - likely bug this test would catch
  - brittleness risks
  - duplicate/overlap candidates within this module
  - recommended action: keep, delete, merge, upgrade, helperize, or investigate
  - concise rationale
- Repeated setup patterns that should become helpers
- Suspect tests with evidence of a weak assertion or duplicate coverage;
  do not infer quality from whether an AI wrote them
```

## Grading Rubric

Score each dimension from 1 to 5 when useful.

- `bug_signal`: Would the test fail for a plausible real defect?
- `behavior_focus`: Does it test public behavior, user-visible behavior, API contracts, or business rules?
- `change_resilience`: Would valid refactors, renames, formatting changes, or dependency updates leave it passing?
- `uniqueness`: Does it add coverage not already provided elsewhere?
- `setup_quality`: Is setup minimal, readable, and helperized when complex?
- `cost_stability`: Is it fast, deterministic, isolated, and unlikely to flake?
- `requirement_trace`: Can it be tied to a product requirement, API contract, safety invariant, regression, or repo policy?

Guidance:

- Delete when bug signal and uniqueness are low, especially if brittleness is high.
- Merge when multiple tests cover the same behavior and input conditions.
- Upgrade when the intent is valuable but the assertions or setup are brittle.
- Helperize when repeated setup obscures test intent or makes updates expensive.
- Keep tests that protect important behavior even if they need minor cleanup.
- Mark `investigate` when a test may encode historical context that is not visible from the code.

## Low-Quality Test Patterns

Treat these as deletion or upgrade candidates unless there is a strong repo-specific reason:

- Tests that inspect source text, function bodies, private names, or implementation branches.
- Tests that assert generated schema shape without checking consumer-visible behavior or documented contract requirements.
- Tests that enforce dependency, version, style, or repository policy better handled by package manager config, lint, CI policy, or lockfiles.
- Snapshot tests covering broad incidental output with unclear behavioral intent.
- Tests that only assert mocks were called without validating meaningful outcomes.
- Tests that duplicate another test with the same setup, input, and assertion.
- Tests whose main value is preserving current file structure, names, ordering, or formatting.
- Tests with excessive setup for a trivial assertion.
- Tests that require frequent updates during valid product or implementation changes.
- Tests that pass because they reimplement the same logic as production code.
- Tests with broad "does not throw" assertions and no meaningful state or output validation.
- Expected values computed with the function being tested, or self-comparisons.
- Fixtures that pre-fill the state, receipt, or event the production path
  should create; assertions against a store that path never writes.
- Negative tests that fail at a different guard before reaching the claimed
  rejection, or inputs that omit a state named by the test.
- A local implementation used as proof for a separate generated or foreign
  language path that the test never calls.

These are prompts to inspect, not automatic deletion rules. Apply the
independent contract checks above before deciding.

## High-Value Test Patterns

Prefer keeping or strengthening tests that:

- Validate business rules, API contracts, user-visible behavior, persistence behavior, security boundaries, or important regressions.
- Cover failure modes, edge cases, permissions, invalid input, concurrency, recovery, or state transitions.
- Mock irrelevant dependencies while exercising the behavior under test.
- Use helpers/factories to make complex setup readable.
- Would catch a realistic bug without breaking on harmless refactors.
- Encode an explicit repo policy that is not reliably enforced elsewhere.

## Cleanup Plan Format

For each proposed deletion or merge, give the exact test, the defect it can
detect, the remaining proof (or why none is needed), relevant history, and
non-test callers of any support code to remove. Name the risk and focused
validation command. Missing evidence means `investigate`, not `delete`.
Remove unused test-only support code in the same scoped cleanup when its
callers and purpose have been checked.

Present recommendations grouped by action:

```text
Delete:
- path/to/test.ext :: "test name"
  Reason: <why low value or brittle>
  Coverage impact: <why safe / what still covers it>

Merge:
- Remove <duplicate test>; keep or expand <surviving test>
  Shared behavior: <behavior and inputs>

Upgrade:
- path/to/test.ext :: "test name"
  Current issue: <weakness>
  Proposed assertion/setup: <change>

Helperize:
- Repeated setup: <description>
  Used by: <files/tests>
  Proposed helper: <name/location>

Keep:
- Notable valuable tests worth preserving

Investigate:
- Tests whose value depends on missing product, policy, or historical context
```

## Verification

After approved edits:

- Run the narrowest relevant test command first.
- Run broader package or repo checks when deletion or merge affects shared behavior.
- Report any commands that could not be run.
- Summarize removed tests, preserved coverage, and remaining risks.

## Source

The test value and retention guidance draws on
[OpenClaw's test-audit skill](https://github.com/openclaw/openclaw/blob/main/.agents/skills/test-audit/SKILL.md).
Use this skill's repository-neutral commands and scope.
