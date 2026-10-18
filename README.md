# Code Factory

Code Factory is a plugin with ten skills, six Codex agent presets, and one
review agent. It helps an
agent plan software changes, implement approved plans, review tests, and care
for pull requests. Claude Code and Codex load it as a plugin. The package supports the
Codex app, CLI, and Cloud through available host tools. OpenCode uses
links made by the install script.

## Skills

| Skill | Use |
| --- | --- |
| `model-choice` | Default models and named Codex agents for each work tier. |
| `writing-plans` | Write a plan with requirements and proofs. |
| `orchestrate-execution` | Guide native orchestration of implementation, review, and PR feedback. |
| `adversarial-review` | Run one adversarial review pass on one commit. |
| `calling-codex` | Run, watch, resume, and stop Codex CLI sessions from a non-Codex agent. |
| `calling-claude` | Run and resume headless Claude Code from a non-Claude agent. |
| `session-retro` | Review a finished run and propose improvements. |
| `working-with-ref` | Work with plans in Ref. |
| `babysit-pr` | Collect and address one round of PR feedback. |
| `audit-tests` | Find weak or duplicate tests. |

`orchestrate-execution` requires explicit user invocation. Plan approval
alone does not invoke it.

The `review-finder` agent runs the finders of an `adversarial-review` pass.
One source builds it for Claude Code and OpenCode. Codex plugins cannot ship
agents, so Codex sessions pass the same role prompt by file path.

## Design principle

Repository instructions and tools come first. Use scripts bundled with a
skill only when the repository has no command for the job.

## Review flow

`orchestrate-execution` runs one `adversarial-review` pass on each PR
before its first push, and one more for each major or architectural change
after that push. A coordinator on the reviewer model splits the change so
each finder can read its part in full: one finder for a small change, one
per area for a large one, plus a finder for contracts between areas. It
tries to disprove each finding and writes `verified.md`. The PR's
implementer reproduces each bug before fixing it, and fixes each finding or
refutes it with evidence. A repository can guide reviews with a `REVIEW.md`
file in any format; see [the formats](skills/adversarial-review/references/format.md).

Claude Code and Codex run their own models as native subagents. Models
from the other provider run through `calling-codex` or `calling-claude`. A
lane without an OS sandbox needs the user's approval.

## Install

### Claude Code

```sh
claude plugin marketplace add neekolas/code-factory
claude plugin install code-factory@code-factory
```

Remove it in the reverse order:

```sh
claude plugin uninstall code-factory@code-factory
claude plugin marketplace remove code-factory
```

### Codex

```sh
codex plugin marketplace add neekolas/code-factory
codex plugin add code-factory@code-factory
```

Remove it in the reverse order:

```sh
codex plugin remove code-factory@code-factory
codex plugin marketplace remove code-factory
```

### Codex app and Cloud

The portable package uses root `plugin.json`, `skills/`, and `mcp.json`.
Install it through a marketplace supported by your host. Local marketplace
support can differ by surface. Installing it on a local machine does not
prove that it is installed in a Cloud task. Check the task's skill list and
connected tools. See [OpenAI's packaging guide](https://developers.openai.com/plugins/build/plugins).

Skills use native agent tools when available. They check the host's model
list, writable paths, GitHub access, and services. They do not require a
nested Codex CLI. Cloud tasks preserve run records as supported artifacts.
When independent review or required CI evidence is unavailable, the task
reports that gap and supplies a handoff.

### Ref credentials

Use the environment variable **`REF_API_KEY`**. Get the key from
[Ref keys](https://ref.tools/keys). The Ref MCP server is
`https://api.plan.ref.tools/mcp`. Send the variable's value in the
**`x-ref-api-key`** header. Keep the value in the host's environment or
secret store. Do not commit it or put it in agent prompts.

The plugin bundles the endpoint in portable `mcp.json`. Claude Code's
compatibility file, `.mcp.json`, also binds `${REF_API_KEY}` to the header.
Set the variable before starting Claude Code. It supports
[header variable expansion](https://code.claude.com/docs/en/mcp#environment-variable-expansion-in-mcpjson).

The portable MCP format does not expand environment variables in HTTP
headers and has no portable secret binding. The host must supply that
binding. Do not put `${REF_API_KEY}` in portable `mcp.json`; it would be
sent as literal text. See the [portable MCP rules](https://agent-plugins.org/plugin-authors/mcp-servers).

For an existing native Codex connection, the supported binding is:

```toml
[mcp_servers.Plans]
url = "https://api.plan.ref.tools/mcp"
env_http_headers = { "x-ref-api-key" = "REF_API_KEY" }
```

Use that fallback only when the host cannot bind a secret to the bundled
server. Avoid two active Plans connections. The native option is documented
in [Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).
For app or Cloud use, verify a supported host secret binding and access to
`api.plan.ref.tools`. Do not assume that the host has such a binding. A shell variable alone does not
prove that a host-managed MCP connection received the key. Check tool access
without printing the key. The package bundles discovery; authenticated app
and Cloud installation still need an end-to-end check.

### OpenCode

```sh
git clone https://github.com/neekolas/code-factory.git
cd code-factory
scripts/install-opencode.sh
```

The script links each skill and agent into
`~/.config/opencode/`. You can set `OPENCODE_CONFIG_DIR` to use a different
configuration directory. You can run the install command more than once.

To remove only the links that this script made, run:

```sh
scripts/install-opencode.sh --uninstall
```

## Repository layout

| Path | Contents |
| --- | --- |
| `skills/` | Ten skills, with their references, scripts, and tests. |
| `src/agents/` | Review agent definition. |
| `agents/` | Generated Claude Code review agent. |
| `opencode/agents/` | Generated OpenCode review agent. |
| `scripts/` | Agent generator, version check, and OpenCode installer. |
| `.claude-plugin/` | Claude Code plugin and marketplace manifests. |
| `plugin.json` | Portable plugin manifest and OpenAI UI metadata. |
| `mcp.json` | Portable Ref Plans MCP endpoint. |
| `.mcp.json` | Claude Code Ref endpoint and environment header binding. |
| `skills/*/agents/openai.yaml` | Skill UI metadata; Ref tool dependency where required. |
| `evals/` | Manual skill evaluation tasks. |

## Check the repository

Run these commands from the repository root:

```sh
skills/babysit-pr/tests/test-check-pr.sh
python3 skills/babysit-pr/tests/test_feedback_scripts.py
skills/calling-codex/tests/test-codex-session.sh
python3 skills/session-retro/tests/test_retro_mine.py
python3 scripts/validate-skills.py
python3 scripts/build-agents.py --check
python3 scripts/check-versions.py
claude plugin validate .
find . -type f -name '*.sh' -print0 | xargs -0 shellcheck -S warning
shellcheck -S warning skills/calling-codex/tests/bin/codex
shellcheck -S warning skills/babysit-pr/tests/bin/gh
```

The skill validator checks Claude's `disable-model-invocation` flag, then
validates the standard fields with `skills-ref` in temporary copies.

For a manual check against the real CLI, run
`skills/calling-codex/tests/live-codex-session.sh`. It needs a logged-in
`codex` and is not part of CI.

After a change to the finder role or its agent source, run
`python3 scripts/build-agents.py` to update the generated agent files.

## License

MIT. Copyright 2026 Nicholas Molnar. See [LICENSE](LICENSE).
