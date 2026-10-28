---
name: boat
description: Create, monitor, steer, resume, and stop coding tasks on Boat VMs. Configure a local CLIProxyAPI gateway over Tailscale and prepare Boat snapshots for Claude Code and Codex.
---

# Boat coding tasks

Use the installed `boat` CLI. Start with `boat --version`, `boat status --json`,
`boat limits --json`, and the relevant subcommand's `--help`. The commands below
were checked with Boat 1.0.81. Use explicit sandbox and conversation IDs: `current`
is shell-local state and is unsafe when coordinating several tasks.

Use this for the user's own coding work. Route Claude subscriptions through
Claude Code, and Codex subscriptions through Codex. Do not serve third-party
traffic through these personal subscriptions.

## Start a task

Read [the local setup](references/setup.md) when preparing a machine, renewing
credentials, or diagnosing the gateway. Read [research](references/research.md)
for architecture, subscription limitations, and source links.

1. Check the local gateway and its model list. Keep subscription OAuth files on
   the gateway host. Never copy them to Boat or put them in a snapshot.
   List the top-level `*.json` files in `~/.config/code-factory/boat-proxy/` and
   read the deployment records matching the requested project or repository.
   There can be several images; `libxmtp.json` is one deployment, not a default
   for unrelated work. Do not recurse into `auth/`. Match the repository and
   workdir, and ask only if more than one record fits. Use its snapshot,
   environment, gateway, and validation status.
2. Create a VM from that snapshot with its recorded `--environment`.
   This environment contains gateway credentials with direct subscription
   credential injection disabled. Connect it with the bundled `connect-vm.py`.
   The helper also works after resume; each boot needs a fresh connection.
   It restarts Boat's agent service, so run it before starting tasks.
3. Check the repository and branch before prompting. A snapshot contains the
   repository state from when it was saved; it is not a fresh checkout.
4. Send a bounded task, with the intended repository, branch, checks, and stopping
   point. Select a model supported by both Boat and the gateway. Boat's prompt
   API rejects account-prefixed model IDs; use unprefixed IDs for its shared pool.

```sh
boat new --from <snapshot-name> --environment <environment-name> --name <task-name> --ttl 7200 --json
python3 <skill-dir>/scripts/connect-vm.py <sandbox-id> --url <deployment-gateway-url> --auth-key-file <local-file>
boat exec <sandbox-id> --cwd <deployment-workdir> -- git status --short --branch
boat prompt <sandbox-id> --provider codex --model <model-id> --new 'Task and checks'
# Or: --provider claude --model <claude-model-id>
```

`boat new --json` emits JSONL; save the ID from `created` immediately and wait for
`ready`. A created ID does not prove setup completed. Do not repeat creation after
an ambiguous network failure: first inspect that ID or list recent sandboxes.

## Monitor and steer

```sh
boat info <sandbox-id> --json
boat conversations <sandbox-id> --json
boat events <sandbox-id> --convo <conversation-id> --json
boat events <sandbox-id> --convo <conversation-id> --follow --json
boat steer <sandbox-id> --convo <conversation-id> 'Additional constraint'
boat interrupt <sandbox-id> --convo <conversation-id>
boat prompt <sandbox-id> --provider <provider> --model <model-id> --resume <conversation-id> 'Continue with this change'
```

Save the conversation ID returned by `prompt`. Steering changes an active turn;
resume continues a finished or interrupted conversation. Reuse the recorded
provider, model, and reasoning effort when resuming; omitted model settings may
select dashboard defaults. Check conversations and
terminal events to distinguish completion from failure. A VM in `ready` state
does not mean its task succeeded. Read events in bounded batches, and wait between
checks. Use a requested heartbeat only when the user asks for future monitoring.

One task per VM gives each task its own files. `--new` starts another conversation
on the same filesystem; it does not create an isolated checkout. Do not run
concurrent writers in one repository unless they have separate worktrees.

## Commands and artifacts

```sh
# Compound commands need a shell; Boat otherwise treats argv literally.
boat exec <sandbox-id> --cwd <deployment-workdir> --timeout 600 -- bash -lc '<repository test command>'
boat exec <sandbox-id> --detach -- bash -lc '<long command>'
boat exec <sandbox-id> --status <pid>
boat history <sandbox-id> --json
boat scp <sandbox-id>:/home/user/<artifact> ./<artifact>
boat push <sandbox-id> .
```

Retrieve the diff, commit IDs, test results, and requested artifacts before
stopping a task. Preserve the task ID and conversation ID in the handoff. A claim
in an agent response is not proof that tests passed or a PR exists.

## Stop, resume, and fork

```sh
boat stop <sandbox-id>
boat resume <sandbox-id>
python3 <skill-dir>/scripts/connect-vm.py <sandbox-id> --url <deployment-gateway-url> --auth-key-file <local-file>
boat fork <sandbox-id> --help
boat snapshot <builder-id> <new-snapshot-name>
```

Stopping keeps data for Boat's retention period and ends compute billing.
Deleting is permanent. Do not delete a VM or replace a named snapshot without
the user's authorization. For image changes, keep the source snapshot, build a
new named version, test a clone, and only then change the chosen default.

Before publishing a base image, stop its Tailscale session and remove runtime
credentials using the preparation command in setup.md. Never snapshot a live
Tailscale identity. Do not assume `--no-env` removes files already in the source
snapshot. Check credential filenames without printing token contents.

For a Nix-based image, run `dev/nix-shell --refresh` with real tool-version
checks on a fresh clone. Nix existing on PATH is not proof that its restored
daemon socket works. The connection helper repairs the Nix sockets when Nix is
installed. Read the Nix section of setup.md before altering the source image.

## Keep images current

Read [snapshot refresh](references/snapshots.md) when preparing an image or when
the selected deployment's cached revision is behind `origin/main`. When working
with Boat, check for stale base artifacts and create a refreshed snapshot when
main or its build inputs have changed. Use a clean builder, warm the project's
build/test caches, verify a clone, and update only that project's deployment JSON.
Never publish an active task branch as the shared base. For libxmtp, the reference
includes its Nix, Cargo, and persistent Kache commands.
