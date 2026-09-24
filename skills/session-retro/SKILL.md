---
name: session-retro
description: Run only when the user asks for a retro of a finished orchestrated run - mines the orchestrator's and subagents' transcripts, groups findings with earlier retro proposals from any agent, proposes repository script, check, skill, and AGENTS.md changes with tokens-saved and time-saved estimates, puts rule and skill text in a review document, and turns approved proposals into fix PRs or issues
---

# Session retro

A retro finds the repository defects that cost this run time and proposes the
smallest change that would have prevented each one. It changes repository
files only:

| Kind | What changes | Efficacy |
| --- | --- | --- |
| `script` | A script or recipe that was missing, wrong, or badly documented | 0.9 |
| `check` | A hook, lint, or CI check for a rule that agents broke anyway | 0.9 |
| `skill` | A repository skill: its body, or its `description` when it was not invoked | 0.6 |
| `agents-md` | One or two lines in the nearest `AGENTS.md` that owns the area | 0.4 |
| `remove` | Delete or replace a rule or skill text that steered agents wrong | 0.4 |

Prefer the kinds in that order. A script fix helps every agent. An `AGENTS.md`
line is loaded in every session, so it has a carrying cost.

The user asks for a retro; no other skill starts one. The session that runs it
acts as the orchestrator: the analysis runs in a subagent, and nothing waits
on the user.

`<skill dir>` below is the directory of this file. Claude Code gives it as
`${CLAUDE_SKILL_DIR}`; Codex and OpenCode show it in their skill list.

## 1. Find the run, then gate

Use the run directory the user names, or the newest one for this repository
in `~/.agents/runs/`. Its `log.md` gives the orchestrator's session ID and CLI,
the start time, and the worktrees. `$RUN` below is that directory. The gate is
one script and no model call:

```bash
S="<skill dir>/scripts"
python3 "$S/retro-mine.py" --gate-only --repo . \
  --claude ~/.claude/projects/*/<orchestrator session ID>.jsonl \
  --since <start time> --worktrees <every worktree the run used>
```

`--claude` is the orchestrator's transcript; the miner adds the subagent
transcripts beside it. `--since` and `--worktrees` add every Codex rollout that
was active in those checkouts during the run, and only events after `--since`
count. A Codex orchestrator omits `--claude` and passes its own thread ID with
`--codex`.

The gate recommends; you decide. Weigh `gate.recommend` and its reasons with
the run log: sessions that died, reviews that repeated, reports that proved
wrong, time the user had to prod the orchestrator. A long, clean run can trip
the gate on an expected compaction. When you stop here, tell the user in one
line why the full retro is not worth its cost.

## 2. Analyse

```bash
python3 "$S/retro-mine.py" --repo . <same session arguments> > "$RUN/retro/retro.json"
python3 "$S/retro-ledger.py" list --repo "$(git remote get-url origin)" --open > "$RUN/retro/ledger.json"
```

Start one analysis subagent: workhorse tier from `model-choice`, clean
context. It may read files and run read-only `git` and `gh` commands. Give it
the repository path, the run's PR numbers, `$RUN/retro/retro.json`,
`$RUN/retro/ledger.json`, the run log, and the plan's `Execution notes`:

```text
Find repository defects that cost this run time, and propose fixes.
Inputs: <retro.json>, <ledger.json>, <run log>, <plan Execution notes>,
repository <path>, PRs <numbers>. Do not edit files. Do not start subagents.
Your final message is the result.

Evidence
- Work from retro.json. For each signature, open at least one `where` entry
  in its transcript and confirm the failure is real. Report the confirmed
  count, not the raw count. Never read a transcript whole. Transcripts can
  hold secrets: quote only text that retro.json already scrubbed.
- `repeats` lists successful commands run eight or more times. Each is a
  candidate for a script.
- Read the reviews and checks of the run's PRs (`gh pr view <n> --json
  reviews,comments`, the repository's CI status command). The same class of
  review finding, or the same CI job going red, on two or more PRs is a
  signature.
- A proposal needs two or more confirmed occurrences, unless a command,
  recipe, or flag deterministically does not exist.

Causes
- For each signature, stall, and prod, ask what the agent did wrong and why:
  missing context, wrong guidance, a skill that exists but was not invoked, a
  missing or broken script, a misleading error, or a one-off.
- Propose a change only for a cause in the repository. A one-off, or a model
  error with no repository cause, is "acknowledge", with one line.
- When a rule or skill already covers the signature and was broken three or
  more times, do not reword it. Propose a `check` or a wrapper `script`. State
  how often the check would fire on this run's commands ("fires on X of Y;
  the incident is included") and one command it must not fire on.
- When a skill covers it but the session never invoked it, the fix is the
  skill's `description`.
- An `agents-md` proposal is one or two lines in the form "When X, do Y". A
  vague principle, or a rule agents already follow, is not a proposal. If it
  needs a paragraph, it is a `skill`.

Grouping and duplicates
- ledger.json holds open proposals from earlier retros by any agent. When a
  proposal is the same defect as an earlier one, give it that proposal's
  `group`. Add your evidence; do not restate theirs.
- Search for a fix that already landed or is in flight: `git log --oneline
  -20 origin/<default> -- <target>`, `gh pr list --state all --search
  '<keyword>' --limit 10`, `gh issue list --search '<keyword>'`. If one
  exists, withdraw the proposal or narrow it to what the fix lacks.
- A ledger group with a `fixed` status and a `merged_at` date whose defect
  occurs again after that date: mark it "fix ineffective" and propose the next
  kind up (agents-md -> skill -> script or check).

Output
- At most seven proposals, ranked by tokens saved. For each: kind, target
  file, title, exact before and after text (or the script change), the group,
  the signature IDs, and `evidence` copied from the signature's `incidents`.
- Estimate over the next 30 days, with ranges from tokens_p25 and tokens_p75:
    occurrences = history_rate_30d, or this run's count when it is null
                  (history missing or "generic");
    tokens saved = tokens_median x occurrences x efficacy - carrying cost;
    time saved   = minutes_median x occurrences x efficacy;
    carrying cost (agents-md) = rule tokens x sessions in 30 days x 0.1;
    a `remove` counts the removed text's carrying cost as a saving.
  Mark n < 3 as low confidence. Assign each signature to one proposal.
- Also write the proposals as JSON lines, one per proposal, in the ledger's
  record format (see retro-ledger.py), in a fenced block at the end. Copy
  `history_rate_30d` from the signature, and set `carrying_tokens_30d` for an
  `agents-md` proposal, so the ledger's combined forecast uses the same
  inputs.
- If nothing survives, say "No high-confidence change" and why.
```

Check the result. Drop a proposal whose evidence does not match `retro.json`,
that duplicates an existing rule, or that a landed fix already covers. Then
record the survivors: save the JSON lines to `$RUN/retro/proposals.jsonl` and run
`retro-ledger.py add "$RUN/retro/proposals.jsonl"`. Run `retro-ledger.py aggregate
--repo <url>` for the combined figures of each group.

## 3. Review document

Put every proposal in one review document. `agents-md`, `skill`, and `remove`
proposals show the full before and after text. `script` and `check` proposals
show the intended change and the test.

- In Claude Code: a Claude doc (Artifact), opened for the user.
- In Codex: a Ref document (see `working-with-ref`).

For each proposal: the title, kind, and target; before and after; the
evidence (signature IDs, confirmed counts, one scrubbed sample, and the
earlier proposals in its group with their agents and dates); the combined
estimate from `aggregate` and this run's share; and the confidence. Scrub the
text again before you write it: the document leaves the machine.

Then post one message in chat and continue with other work. Do not use a
blocking question tool.

```text
Retro: <N> repository fixes, about <T> tokens and <M> minutes a month
(combined with <K> earlier proposals). Review: <document link>

| # | Change | Kind | Seen | Tokens / 30 d | Time / 30 d | Confidence |
| 1 | <title> | script | 7 times, 3 agents, 2 retros | 0.8–1.2M | 45 min | high |

Reply: `fix 1 2` (PR now), `issue 3` (later), `edit 2: <new text>`, `skip 4`.
Comments on the document work too. No reply means nothing happens.
```

When nothing survives, post: "Retro: no repository fixes (<N> signatures,
all acknowledged or already fixed)."

## 4. Act on the reply

- **`fix`**: start one implementer (workhorse tier) in a new worktree from the
  default branch, on a branch `retro/<date>-<slug>`. It fetches first and
  repeats the landed-fix search. It applies the approved text exactly; any
  difference is listed in the PR. One PR for all fixes in one reply, one
  commit per proposal. It runs the repository's lint for changed files and
  tests for any changed script or check. A script or check also gets a review
  from the reviewer model. The PR description has, per proposal, the evidence
  (scrubbed), the estimate, and the before and after. Never merge a retro PR.
- **`issue`**: one issue per proposal in the repository's tracker (`gh issue
  create` by default) with the problem, the scrubbed evidence, the estimate,
  and the proposed change. When the group already has an open issue, add a
  comment with the new evidence and the combined estimate instead.
- **`edit N: <text>`**: replace the after text, update the document, then
  treat it as approved for `fix`.
- **`skip`**: record it as skipped.

Record every decision: `retro-ledger.py set <id> status=<fixed|issue|skipped>
pr=<url> issue=<url>`. When a retro PR merges, set `merged_at`.

## Rules

- Scrub before anything leaves the machine: documents, PR text, issue text,
  and commit messages. Do not add raw transcript text.
- Never change user-level files (`~/.claude`, `~/.codex`, `~/.agents`) from a
  retro. A finding about these skills themselves becomes an `issue` proposal
  in the plugin's own repository.
- Never block the user or the PR follow-up on the retro.
