# Code Factory

Code Factory is a plugin with eleven skills, six Codex agent presets, and one
review agent. It helps an
agent plan software changes, implement approved plans, review tests, and care
for pull requests. Claude Code, Codex, and Factory Droid load it as a plugin. The package supports the
Codex app, CLI, and Cloud through available host tools. OpenCode uses
links made by the install script.

## Skills

| Skill | Use |
| --- | --- |
| `boat` | Run, monitor, and steer coding tasks on Boat VMs through a local gateway. |
| `model-choice` | Default models and named Codex agents for each work tier. |
| `writing-plans` | Write a plan with requirements and proofs. |
| `orchestrate-execution` | Guide native orchestration of implementation, review, and PR feedback. |
| `adversarial-review` | Run one adversarial review pass on one commit. |
| `calling-codex` | Run, watch, resume, and stop Codex CLI sessions from a non-Codex agent. |
| `calling-claude` | Run and resume headless Claude Code from a non-Claude agent. |
| `session-retro` | Review a finished run and propose improvements. |
| `babysit-pr` | Collect and address one round of PR feedback. |
| `audit-tests` | Find weak or duplicate tests. |
| `security-audit` | Hunt, validate, and plan fixes for vulnerabilities in one commit. |

`orchestrate-execution` and `security-audit` require explicit user invocation. Plan approval
alone does not invoke it.

The `review-finder` agent runs the finders of an `adversarial-review` pass.
One source builds it for Claude Code, Factory Droid, and OpenCode. Codex plugins cannot ship
agents, so Codex sessions pass the same role prompt by file path.

## Design principle

Repository instructions and tools come first. Use scripts bundled with a
skill only when the repository has no command for the job.

## Review flow

`orchestrate-execution` runs one `adversarial-review` pass on each PR
before its first push, and one more for each fix that is a new design and
each major or architectural change after that push. A pass is small. A coordinator on the reviewer model
splits the change among at most five finders at `high` effort, so each can
read its part in full: one finder for a small change, one per area for a
large one, a finder for contracts between areas, and a test-audit finder for
code changes. One verifier tries to disprove every finding and writes
`verified.md`. The orchestrator groups findings by the invariant they break
and sends one fix per group to the PR's implementer. It reproduces each bug
before fixing it, and fixes each finding or refutes it with evidence. A repository can guide reviews with a `REVIEW.md`
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

### Factory Droid

```sh
droid plugin marketplace add neekolas/code-factory
droid plugin install code-factory@code-factory --scope user
```

Use `--scope project` to install for one project. Restart Droid after installing.
The native Factory package includes all eleven skills and the `review-finder`
droid. The review droid inherits the caller's model and uses Factory's
read-only tool policy.

Skills that call other providers need the corresponding Codex or Claude CLI
and credentials. See the Boat skill for its CLI and gateway setup.

Remove the plugin and marketplace:

```sh
droid plugin uninstall code-factory@code-factory --scope user
droid plugin marketplace remove code-factory
```

See [Factory's plugin guide](https://docs.factory.com/harness/plugins).

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

The portable package uses root `plugin.json` and `skills/`.
Install it through a marketplace supported by your host. Local marketplace
support can differ by surface. Installing it on a local machine does not
prove that it is installed in a Cloud task. Check the task's skill list and
connected tools. See [OpenAI's packaging guide](https://developers.openai.com/plugins/build/plugins).

Skills use native agent tools when available. They check the host's model
list, writable paths, GitHub access, and services. They do not require a
nested Codex CLI. Cloud tasks preserve run records as supported artifacts.
When independent review or required CI evidence is unavailable, the task
reports that gap and supplies a handoff.

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

## External artifact services

Use an external artifact service when the user requests one, project rules
require one, or the document already lives there. Prefer OpenArtifacts when
the host has access and the user or project has left the choice open.

## Repository layout

| Path | Contents |
| --- | --- |
| `skills/` | Skills, with their references, scripts, and tests. |
| `src/agents/` | Review agent definition. |
| `agents/` | Generated Claude Code review agent. |
| `droids/` | Generated Factory review droid. |
| `.factory-plugin/` | Factory plugin and marketplace manifests. |
| `opencode/agents/` | Generated OpenCode review agent. |
| `scripts/` | Agent generator, version check, and OpenCode installer. |
| `.claude-plugin/` | Claude Code plugin and marketplace manifests. |
| `plugin.json` | Portable plugin manifest and OpenAI UI metadata. |
| `skills/*/agents/openai.yaml` | Skill UI metadata. |
| `evals/` | Manual skill evaluation tasks. |

## Check the repository

Run these commands from the repository root:

Use Python 3.11 or newer for the Python tests.

```sh
skills/babysit-pr/tests/test-check-pr.sh
python3 skills/babysit-pr/tests/test_feedback_scripts.py
skills/calling-codex/tests/test-codex-session.sh
python3 skills/session-retro/tests/test_retro_mine.py
python3 -m unittest discover -s skills/boat/tests -v
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
