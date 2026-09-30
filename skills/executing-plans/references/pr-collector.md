# PR collector

Prefer repository commands or bundled scripts. Use one read-only chore only
when collection needs it. Start on the first fresh item, current-head failure,
conflict, or required-check completion. Deliver each source as it is available.
Do not wait for the stack, all comments, or all checks. A collector records
raw evidence and gaps. It does not judge findings or direct fixes.

Give an optional collector this prompt with paths filled in:

```text
Collect one feedback round for stack <PR list>, bottom to top. Confirm the
list includes every PR. Read <RUN>/brief.md and <babysit-pr>/SKILL.md.
Worktree: <path>. Session: pr-round-<N>. Write the evidence index to
<RUN>/reports/pr-round-<N>.md and raw evidence beside it.

For each PR, record observed head, merge state, required and optional check
states, and review state. Checks still running are PENDING. Missing checks
are not PASS. Preserve older-head feedback and nullable source commits.
Stable check identities include provider, run, and attempt. Do not bind an
older result to the current head or identify a check by its name alone.

Use repository commands first. Otherwise run:
<babysit-pr>/scripts/collect-feedback.py --out <RUN>/reports/pr-round-<N>
  --trusted-author <caller-trusted login>
  --dispositions <version-dispositions.json> <owner/repo> <PR list>
Omit trust/disposition options if no verified record exists. Trust only
caller-named identities. A bot marker alone does not establish handling.
The dispositions file maps exact version keys and does not drop evidence.

The helper writes pr-N.json atomically after each source and flushes
SOURCE N threads|reviews|comments|checks READY|INCOMPLETE updates. Forward
ready paths through the host progress channel immediately. The parent sends
them to the persistent implementer with native messages or the durable CLI
inbox. Continue collecting every source and PR before your final report.
Do not wait for other checks, judge findings, or start reviewer triage.

The output carries head, nullable source_commit, comment updated_at,
body_hash, version_key, and thread expected_last_comment_* guard fields.
The sources map has complete/error per source. snapshot_state is COMPLETE,
INCOMPLETE, or STALE. Failed or stale collection has complete=false.
Partial or stale evidence can start implementer validation, but cannot
establish readiness. Mark source errors, page limits, and changed heads;
never describe failed access as zero findings. Recheck the current head
before accepting a snapshot. Exit 2 needs a refreshed collection.

Do not reply, resolve threads, edit tracked files, commit, push, or start
agents. Do not message other lanes. Give the parent the index path, PR count,
and any incomplete or stale sources. Include one index row per PR with
head, check state, source completeness, snapshot state, and item count.
```

Use exact item versions for acknowledgements and dispositions. A later
comment from any author reopens validation. Before the post-CI gate, refresh
sources and heads and confirm no new unhandled version remains. Required
CI and Macroscope success, complete evidence, and handled feedback precede
the conditional second review. No collector verdict can replace those gates.
