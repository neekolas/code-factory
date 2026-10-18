# Formats

## Starting a pass

A user runs a pass in their own session. An orchestrator runs each pass in
one native subagent with the reviewer model and effort from model-choice
(in Codex, also `fork_turns: "none"`). Give it the path of this skill's
SKILL.md and the pass request, and read only its final message.

## Pass request

- **Worktree, base, target.** The base is the PR's base branch or commit.
- **Goals.** Plan references or text. Include requirement rows when there is
  a plan.
- **Review directory.** Outside the worktree. In an orchestrated run, use
  `<run dir>/reviews/<pr>-<n>/`. Otherwise use
  `~/.agents/runs/reviews/<YYYY-MM-DD>-<repo>-<id>/`, or
  `$TMPDIR/agents-runs/reviews/...` when that is not writable.
- **Optional.** A prior reviewed commit: review only the changes since it.
  `cross-model`: add one finder from the other provider, with the same kind
  of brief, through [calling-codex](../../calling-codex/SKILL.md) or
  [calling-claude](../../calling-claude/SKILL.md) in `read` mode.

## REVIEW.md

Optional, at the repository root, in any format. Read it from the merge
base and give it to every finder as written. Name high-risk areas there;
when the change is split, each gets its own finder.

## Result

Write `verified.md` in the review directory:

```text
Verdict: PASS | ISSUES | BLOCKED - <reason>
Target: <sha>. Base: <merge base>. From: <prior sha or merge base>.
Finders: <the files or concern each finder covered>

Findings:
- <id> [CRITICAL|MAJOR|MINOR] [bug|vacuous-test|verification-gap]
  <file>:<line> - <title>
  Status: CONFIRMED | UNPROVEN
  Scenario: <trigger, faulty path, wrong result>
  Evidence: <file:line trace>
  Test: <the smallest failing test>

Refuted:
- <file>:<line> - <title> - <the line or run that refutes it>
```

The verdict is ISSUES when any finding is CRITICAL or MAJOR, BLOCKED when
the review could not cover the change, and PASS otherwise. The final
message is the verdict, the finding counts, and the `verified.md` path.
