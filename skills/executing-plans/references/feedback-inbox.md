# Durable feedback inbox

Use native messages for native agents. An active `codex exec` session cannot
accept a new prompt through `codex-session.sh`. For that path, publish feedback
in the run directory. This is a file protocol. It needs no daemon or new CLI
feature. The implementer reads it at safe checkpoints and before commit,
push, and its final report. A long useful command can finish first. Do not
busy poll or interrupt useful work. Resume an idle lane with its inbox path.

## Items and versions

Use `$RUN/inbox/<lane>/items/` and `$RUN/inbox/<lane>/acks/`. The collector or
orchestrator is the only item writer. The implementer is the only ack writer.
Use one immutable JSON item per source version. The key includes repository,
PR, source type, and stable provider ID. For a check, include provider, run ID,
and attempt. Do not use a display name or an arrival order as identity.

The version key includes the source ID and its update time or body hash.
For a thread, bind it to the last comment ID and update time or body hash.
Use the collector's `version_key` when supplied. Preserve `source_commit`
when known and use null when the source does not establish it. Record the
observed PR head separately. A newer head does not erase older feedback.

Each item contains `item_key`, `version_key`, PR, source identity and link,
`source_commit`, observed head, raw evidence paths, source completeness,
and required last-comment guard fields. Hash the version key for its file
name. Write a temporary file in the same directory, flush and close it,
then rename it atomically to the final name. Never overwrite an older
version with a newer version. Publish the complete item before sending a
native message or recording its path in the index.

## Read and acknowledge

At each safe checkpoint, list item files and compare their version keys
with ack files. Read every unhandled version. Process versions of the same
item in source order. If a newer version makes an earlier action obsolete,
record that disposition and evidence for both versions. Do not silently
skip a version. New files that arrive during a scan remain for the next scan.

Write each ack with the same atomic temporary-file and rename procedure.
An ack contains `item_key`, `version_key`, state, disposition, candidate,
proof paths, action results, and pending review scope. Use these states:

- `RECEIVED`: the implementer read the item. Work can remain open.
- `HANDLED`: validation and disposition are complete. A repair has available
  passing closure proof. Record threads open solely for deferred review.
- `CLOSED`: the named proof and any required independent review passed.
  Record the external reply or resolution result when authorized.

A receipt is not a handled version. Owner decisions, blocking defects,
missing proof, and incomplete source evidence cannot become HANDLED. Keep
all ack versions for recovery. Before repeating an action after a restart,
check the ack, git, proof record, and remote thread. Use recorded commits and
external reply IDs to avoid duplicate fixes or replies. A crash between an
external mutation and its ack needs reconciliation, not a blind repeat.
The files do not make external mutations atomic.

Use this prompt at lane start and on idle resume:

```text
Feedback inbox: <RUN>/inbox/<lane>/items/. Acks: <RUN>/inbox/<lane>/acks/.
Read all unhandled item versions at safe checkpoints and before commit,
push, and final report. Preserve IDs and source heads. Record validation,
proofs, action results, and pending review scopes in atomic ack files.
Do not poll while a useful command runs. Reconcile recorded and external
actions before repeating them after recovery.
```

Before the post-CI gate, refresh all sources and drain all published versions.
Check for new items again after the gate snapshot. A partial source or a new
unhandled version returns the lane to feedback handling.
