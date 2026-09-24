# Code Factory

Code Factory is a plugin with seven skills and one review agent. It helps an
agent plan software changes, implement approved plans, review tests, and care
for pull requests. Claude Code and Codex load it as a plugin. OpenCode uses
links made by the install script.

## Skills

| Skill | Use |
| --- | --- |
| `model-choice` | Choose models for an orchestrated run. |
| `writing-plans` | Write a plan with requirements and proofs. |
| `executing-plans` | Run an approved plan and verify each task. |
| `session-retro` | Review a finished run and propose improvements. |
| `working-with-ref` | Work with plans in Ref. |
| `babysit-pr` | Watch a pull request or stack until it is ready. |
| `audit-tests` | Find weak or duplicate tests. |

The `adversarial-reviewer` agent reviews a change with clean context. Its
definition comes from one source for Claude Code and OpenCode.

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
| `plugin.json` | Codex plugin manifest. |
| `evals/` | Manual skill evaluation tasks. |

## Check the repository

Run these commands from the repository root:

```sh
skills/executing-plans/tests/test-codex-session.sh
python3 skills/session-retro/tests/test_retro_mine.py
for skill in skills/*; do npx --yes skills-ref@0.1.5 validate "$skill"; done
python3 scripts/build-agents.py --check
python3 scripts/check-versions.py
claude plugin validate .
find . -type f -name '*.sh' -print0 | xargs -0 shellcheck -S warning
shellcheck -S warning skills/executing-plans/tests/bin/codex
```

After a change to the shared review agent or its prompt, run
`python3 scripts/build-agents.py` to update both generated files.

## License

MIT. Copyright 2026 Nicholas Molnar. See [LICENSE](LICENSE).
