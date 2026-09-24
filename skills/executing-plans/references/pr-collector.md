# PR collector

Use one cheap, read-only chore agent for the entire stack in one feedback
round. The orchestrator starts this task on the first fresh review item,
current-head check failure, merge conflict, or completion of required checks.
The collector checks every PR before it reports. It does not wait for other
checks, judge findings, or direct other agents.

Give the agent this prompt with the paths filled in:

```text
Collect one PR feedback round for the entire stack <PR list>, bottom to top.
Confirm the list contains every PR in that stack. Read <RUN>/brief.md and the
snapshot and collection steps in <babysit-pr>/SKILL.md. Worktree:
<path>. Use session name pr-round-<N>. Write a short index to
<RUN>/reports/pr-round-<N>.md. Put full failure logs and comment bodies in
files beside the index; link each file from it.

Before you report, inspect every PR in the stack. For each PR, record its
current head SHA, merge state, required and optional check states, and review
state. Mark running checks PENDING. Fetch the logs and annotations for every
check that has failed so far on that head. Fetch every page of review bodies,
conversation comments, unresolved threads, and replies. Record stable IDs,
links, authors, and the last reply for each item. Do not treat an earlier
head's check as current.
Do not return a report after finding one failure or comment. Finish the
snapshot and feedback collection for every PR first.
Use the repository's commands first; use gh where they lack a source. If a
head changes while you collect, mark that PR STALE so the orchestrator can
collect it again.

Do not reproduce or classify findings, summarize a likely root cause, reply
on the PR, resolve threads, edit tracked files, commit, push, or start agents.
In the index, give one line for every PR: head, check state, item count, and
whether collection is complete. Give the orchestrator only the index path,
the number of PRs checked, and whether any collection is INCOMPLETE. A
pending check does not make collection incomplete. Report any API error or
page limit as INCOMPLETE, not as zero findings.
```

The index groups items by PR and head. Each item has an ID, source type,
link, and evidence file. It marks already handled items using the run log and
the last `🤖 ` reply. It does not omit a later human reply on that thread.
