---
name: security-audit
description: Run a full security audit of one commit - parallel hunting lanes across models, dedup, exploit validation, and a remediation plan. Use only when the user explicitly invokes it.
disable-model-invocation: true
---

# Security audit

Audit one snapshot SHA with the steps, prompts, and finding format in
[the workflow](references/workflow.md). Run everything inside the user's
sandboxed VM; worktree isolation is not a sandbox. Never push.

Keep state in one run directory,
`~/.agents/runs/<YYYY-MM-DD>-<repo>-security-audit/`, with `log.md`,
`prompts/`, `hunt/<lane>/`, `findings/`, and `report.md`. Write each lane's
prompt to `prompts/` before it starts, so a lost lane can restart from it.

## Stages

1. **Confirm.** Show the lanes: prompt, provider, model, and Cyber access
   program. Get approval, then record it in `log.md`.
2. **Hunt.** Fan out one agent per lane, each in its own worktree at the SHA.
   In Claude Code, use a Workflow. Run Codex lanes through
   [calling-codex](../calling-codex/SKILL.md) in `read` mode, with
   `CODEX_SESSION_CYBER` set to the lane's program. Each lane writes to
   `hunt/<lane>/`. Third party reports, such as Octane, are another lane
   directory.
3. **Dedup.** One agent merges `hunt/` into `findings/`.
4. **Validate.** For each finding, a validator exploits or refutes it in a
   pooled worktree, then a reviewer from the other provider checks it.
   Codex validators run in `write` mode. Merge exploit branches into one local
   branch and build `report.md`.
5. **Stop.** Report counts by status and the `report.md` path. The user
   reviews the findings and updates `NON_ISSUES.md`.
6. **Plan.** When the user invokes `security-audit plan <run dir>`, write the
   remediation plan with its coverage table, then hand it to
   [writing-plans](../writing-plans/SKILL.md).
