# Code Factory

Code Factory is a plugin with seven skills and one review agent. It helps an
agent plan software changes, implement approved plans, review tests, and care
for pull requests. Claude Code and Codex load it as a plugin. The package supports the
Codex app, CLI, and Cloud through available host tools. OpenCode uses
links made by the install script.

## Skills

| Skill | Use |
| --- | --- |
| `model-choice` | Choose models for an orchestrated run. |
| `writing-plans` | Write a plan with requirements and proofs. |
| `executing-plans` | Run an approved plan with pre-submission review and direct CI feedback. |
| `session-retro` | Review a finished run and propose improvements. |
| `working-with-ref` | Work with plans in Ref. |
| `babysit-pr` | Collect and address one round of PR feedback. |
| `audit-tests` | Find weak or duplicate tests. |

The `adversarial-reviewer` agent reviews a change with clean context. Its
definition comes from one source for Claude Code and OpenCode.

## Design principle

Repository instructions and tools come first. Use scripts bundled with a
skill only when the repository has no command for the job.

## Delivery flow

One persistent implementer owns each lane across tasks and PR feedback.
Always finish a fresh adversarial review after fast local checks and before
first PR submission. Repair initial blocking findings before submission.
Record the reviewed candidate, repaired candidate, and closure proofs.
Full repository suites run in CI; they are not local checks.

Send all CI and Macroscope feedback directly to the implementer as it arrives.
Do not wait for all checks or comments. Do not add reviewer triage or mid-loop
repair reviews. Push ready repairs after fast checks and track risk changes.
Only after current-head CI and Macroscope checks succeed and
feedback is handled, assess accumulated behavior and risk changes from the
first review. Record the decision and scope for a conditional second review.
Small repairs that preserve contracts and have useful proofs can skip it.

A thread that needs independent closure stays open until its named proof
and scoped review pass. It can count as handled for the post-CI gate only
when deferred review is its sole remaining closure step. Owner decisions,
blocking defects, missing proof, and new unhandled comments still block it.
A second-review finding returns to repair and CI before a needed scoped
recheck. Final proofs, current-head CI, feedback closure, and required
approvals gate readiness.

A clean starting commit can use completed CI evidence for its baseline.
Preflight runs new or one-off commands and checks that CI does not cover.
It does not run every plan proof before implementation.

See [the applied workflow and scenarios](docs/workflow-draft.md).

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

The script links each skill and the review agent into
`~/.config/opencode/`. You can set `OPENCODE_CONFIG_DIR` to use a different
configuration directory. You can run the install command more than once.

To remove only the links that this script made, run:

```sh
scripts/install-opencode.sh --uninstall
```

## Repository layout

| Path | Contents |
| --- | --- |
| `skills/` | Seven skills, with their references, scripts, and tests. |
| `src/agents/` | Shared review agent definition. |
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
skills/executing-plans/tests/test-codex-session.sh
python3 skills/session-retro/tests/test_retro_mine.py
for skill in skills/*; do npx --yes skills-ref@0.1.5 validate "$skill"; done
python3 scripts/build-agents.py --check
python3 scripts/check-versions.py
claude plugin validate .
find . -type f -name '*.sh' -print0 | xargs -0 shellcheck -S warning
shellcheck -S warning skills/executing-plans/tests/bin/codex
shellcheck -S warning skills/babysit-pr/tests/bin/gh
```

For a manual check of the session script against the real Codex CLI, run
`skills/executing-plans/tests/live-codex-session.sh`. This check needs a
logged-in `codex` and is not part of CI.

After a change to the shared review agent or its prompt, run
`python3 scripts/build-agents.py` to update both generated files.

## License

MIT. Copyright 2026 Nicholas Molnar. See [LICENSE](LICENSE).
