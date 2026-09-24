---
name: working-with-ref
description: Use when the user asks for a Ref, a plan in Ref, or a Ref review, gives a plan.ref.tools link or Ref id, or when project rules require a Ref plan - covers when to write a Ref and when not to, the Plans MCP tools, review without polling, local copies for subagents, and writing decisions back
---

# Working with Ref

Ref (plan.ref.tools) keeps plan documents. The user reviews them and adds
comments. The Plans MCP server supplies the tools, named `mcp__Plans__<Tool>`.
Old transcripts show `mcp__plugin_ref_Plans__<Tool>`. The tools are the same.

This skill replaces the Ref plugin guidance. Do not call `ListSkills`, `Skill`,
or `Manual`. They load the old guidance, and that guidance conflicts with this
skill.

## When to write a Ref

Write a Ref only when one of these is true:

- The user asks for a Ref, a plan in Ref, or a review in Ref.
- Project rules require a Ref plan (for example, new public API surface).
- The work continues a Ref that already exists.

Do not write a Ref for:

- An adversarial review of a spec or code. Give the review in the session
  that asked for it.
- Subagent prompts, handoffs, or reports. Use files in the run directory
  (`~/.agents/runs/`, see `executing-plans`).
- Investigations, summaries, or records of finished work that nobody asked to
  keep in Ref. Answer in chat.
- An "artifact" or a "doc". That is a Claude Doc, not a Ref.
- Questions about a document. Answer in the session. Change the Ref only with
  the revisions that the discussion causes.

If you are not sure, ask the user. Do not make a Ref "to be safe".

## Tools

A Ref id is the last part of its URL: `https://plan.ref.tools/<id>`.

| Tool | Key parameters | Use |
|---|---|---|
| `Create` | `title`, `initial_content`, `initiative` | Make a Ref. Returns the id and URL. `initiative` is `user` when the user asked for the document, else `agent`. |
| `Read` | `planId`, `offset`, `limit` | Read a Ref. |
| `Edit` | `planId`, `old_string`, `new_string`, `replace_all` | Change part of a Ref. Use this for all normal changes. |
| `Write` | `planId`, `content`, `force_overwrite` | Replace the full Ref. Use only for a full rewrite. |
| `Comments` | `planId`, `action`, `threadId`, `message`, `includeResolved` | `list` gives threads and the latest verdict. Also `reply`, `resolve`, `request_review`. |
| `PrLinks` | `planId`, `action`, `url` | `add` attaches a PR that delivers a task. |
| `List` | `owner`, `updated_since`, `limit` | Find a Ref when you do not have its id. |
| `Rename` | `planId`, `title` | Change the title. |

Many tools accept a `title` parameter. It is a sidebar label. Do not send it.

Do not use `AwaitReview`. It blocks for about 50 seconds and tells you to call
it again until the user answers. Do not use `LaunchAgent`, `SendMessage`,
`ListDevices`, `Automations`, `Media`, or `Share` unless the user names them.
This setup uses its own subagents, not Ref agents.

## Write the Ref

- Line 1 is `# <title>`. The app reads the title from that line.
- The title names the subject: "Migrate sessions to Postgres", not "Plan".
- The first paragraph gives the subject, the reason, and the decision or the
  request.
- The reader has no chat history. Do not write "as discussed" or "the error
  above". Name files, symbols, and errors in full.
- Write work as tasks. A PR may hold several tasks; the plan's delivery
  section says which. A task looks like this:

```markdown
# Task 1: Verb noun name
One sentence that gives the goal and the change.

:::collapse
## Files — 3 files
:::
- `path/to/file.rs` - what changes here.
:::end

## Decisions
- **The decision.** One sentence.
  - Overruled: the alternative, and why it lost.

## Verification
One sentence that names a result a reader can see.
```

- Number `# Task N:` headers in order. The app splits the Ref on them.
- `✅` in a task header means the PR merged. Do not add it before the merge.
- Every `:::collapse` needs its own `:::end`.
- Put questions for the user in an open questions section. Include only
  decisions that a person must make.
- Use `Edit` for each later change. Replace the old text; do not add the new
  text beside it. Ref keeps the version history.

## Request a review without polling

1. Finish the Ref.
2. Call `Comments` with `action: "request_review"` and a `message` of two or
   three sentences (400 characters maximum): what changed and what to check.
3. Print the review link on its own line.
4. End the turn. Do not call `AwaitReview`. Do not sleep, loop, or start the
   work.

The user's next message starts the next turn. Then:

1. Call `Comments` with `action: "list"`. It gives the latest verdict and the
   open threads. Read them even when the user says "approved" in chat, because
   an approval can have comments.
2. For each thread, edit the Ref. Then resolve the thread. Reply only when the
   thread asks a question.
3. If the user requested changes, request a review again with a new message,
   print the link, and end the turn.
4. If the user approved, do the work.

## Write decisions back in the same turn

The Ref is the source of truth. Implementers work from it. Chat, Claude Doc
comments, and local copies are not the source of truth.

When a discussion gives a decision, a clearer definition, or a new open
question, edit the Ref in the same turn:

- A settled item: change the text in place. If the Ref has a decisions table,
  add a row.
- An open item: add it to the open questions or proposals section.

Tell the user which sections changed. If a local copy or a Claude Doc is now
old, say so.

## Give a Ref to subagents

Subagents do not call the Plans tools.

1. `Read` the Ref once. If the result stops early, read again with `offset`
   and `limit` until you have all lines.
2. Write it to `$RUN/plan.md` in the run directory (`executing-plans`,
   section 1). Outside a run, use
   `~/.agents/runs/<YYYY-MM-DD>-<repo>-<slug>-<session>/plan.md`. Put the Ref
   URL and the read time on the first line.
3. Give the subagent the file path and its task numbers.
4. The subagent reports to you. You edit the Ref.

Read the Ref again before new work if the user can have changed it.

## Record delivery

- When a PR for a task opens, call `PrLinks` with `action: "add"` and the PR
  URL. Put the Ref URL in the PR description.
- When the PR merges, change `# Task N: Name` to `# Task N: ✅ Name`. Add a
  `## Completed` section with the PR link and only the notable differences
  from the plan. Do not change the goal, decisions, or verification text.
- A report that says "done" is not a merge.
