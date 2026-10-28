# Local gateway and base image

Validated platform: macOS gateway, Boat Ubuntu VMs, CLIProxyAPI 8.0.45,
Boat CLI 1.0.81. Recheck command help after upgrades.

## Gateway on the Mac

```sh
brew install cliproxyapi
python3 <skill-dir>/scripts/configure-host.py --install-service
tailscale up
tailscale serve --bg --https=443 http://127.0.0.1:8317
tailscale serve status
```

The configuration and client key live under
`~/.config/code-factory/boat-proxy/`. The launchd job is
`local.code-factory.boat-proxy`. It starts at login and restarts after a crash.
Keep the Mac awake and online while tasks run. Login service availability is not
the same as availability before login or while asleep.

The script binds only loopback, disables the management API and panel, and
requires a generated client key. Tailscale Serve provides private HTTPS. Do not
enable Funnel. The provider tokens are in the `auth/` subdirectory. Treat that
directory, config, and client key as secrets. Do not attach them to tasks or logs.
Request-body logging is off. The setup disables optional client cloaking; it
does not promise that a provider permits subscription proxying.

## Native Boat agent environment

Boat regenerates its agent service and does not preserve arbitrary systemd
drop-ins there. A named environment provides credentials for shell commands,
but live testing showed that arbitrary variables do not reach native agents.
The connection helper also configures the actual clients: Claude's
`settings.json` and Codex's provider table. This stores the **gateway client key**
with Boat and in each worker's protected client files; upstream OAuth tokens
remain on the Mac. Confirm that the user has authorized this transfer; do not
ask again when approval already covers the destination. The setup script sends values through stdin and captures
responses so secrets are not written into command arguments or terminal output.

```sh
python3 <skill-dir>/scripts/configure-environment.py \
  --url https://<gateway-name>.<tailnet>.ts.net
```

The dedicated `boat-proxy` environment disables direct agent logins, Boat account
credentials, and GitHub credential injection. It enables its own secret variables
only. Enable GitHub access separately if the user wants workers to fetch or push
private repositories. Do not run workers with `--no-env`; that bypasses this
environment. Use `--no-env` for the credential-free image builder instead.

The pending environment also requests a one-hour Claude main-conversation
prompt cache. The Codex provider enables WebSockets. Verify both with native
tasks after environment activation; a successful SSE test does not verify
WebSockets. If the client transport fails, diagnose it before claiming success.

Authenticate through each provider's browser flow on the Mac:

```sh
cliproxyapi -config ~/.config/code-factory/boat-proxy/config.yaml -claude-login
# Repeat and choose the second Claude account.
cliproxyapi -config ~/.config/code-factory/boat-proxy/config.yaml -codex-login
```

Count the resulting auth files by provider without printing tokens. Repeating
login on the same account does not create another subscription. CLIProxyAPI
watches the directory and refreshes tokens. Avoid importing a refresh token that
another process also renews. Round-robin assigns new sessions; session affinity
keeps an active conversation on its selected account, with failover when an
account becomes unavailable. These do not increase any subscription's limits.

To explicitly select one Claude account, add a unique `prefix` to its auth JSON
on the Mac and use a model ID returned by the refreshed `/v1/models` list. Do not
guess prefixed IDs or expose auth JSON to the VM. Unprefixed requests pool eligible
accounts by default. An isolated single-account test should disable the other
credential temporarily, restore it afterward, and never delete it as a test.

The local gateway uses `claude-1`, `claude-2`, and `codex-1` prefixes. For
direct CLI or API calls, `claude-2/claude-sonnet-5-5` selects the second account. Read
the matching top-level deployment JSON beside the host config (for example,
`libxmtp.json`) for its snapshot and validation status. Boat 1.0.81 rejects prefixed model IDs. Use its supported
unprefixed IDs with the shared pool. Direct native CLI runs support the prefixes,
but do not become Boat conversations with native steering. Do not claim explicit
account pinning through `boat prompt`.

## Tailscale enrollment and access

Use a reusable, ephemeral, tagged auth key for this personal workflow, or keep a
scoped OAuth client on the control host and mint one-off keys. Do not put the
OAuth client secret on workers. Save the chosen enrollment key in the local file
`~/.config/code-factory/boat-proxy/tailscale-auth-key` with mode 600. It is not part
of the repository or image. Rotate it before its expiry.

In the Tailscale policy, define `tag:boat` and allow it only to the gateway's
TCP 443. Replace the example address below with the gateway's Tailscale IP:

```json
{
  "tagOwners": {"tag:boat": ["autogroup:admin"]},
  "grants": [
    {"src": ["tag:boat"], "dst": ["100.64.0.10"], "ip": ["tcp:443"]}
  ]
}
```

Merge this into the existing policy; do not replace unrelated policy. Tailscale
grants and ACLs are additive. A default allow-all rule defeats this restriction;
remove the Boat tag from broader access and test denial to another device/port.
Check that the gateway is reachable before handing off tasks. Generate the key
with `tag:boat`, Reusable, Ephemeral, and pre-approval if device approval is on.
Key creation does not itself enforce a network restriction.

## Build a credential-free snapshot

Create a builder from the user's existing image with `--no-env`. This does not
remove credentials already baked into the source image. Inspect credential file
names and scrub the builder before saving it. Do not modify the source image.

```sh
boat new --from <source-snapshot> --no-env --name proxy-image-builder --ttl 7200 --json
python3 <skill-dir>/scripts/connect-vm.py <builder-id> --wait-only
# Copy these two files individually (avoids macOS archive metadata issues).
boat scp <skill-dir>/scripts/install-vm.sh <builder-id>:/tmp/install-vm.sh
boat scp <skill-dir>/scripts/vm-connect.py <builder-id>:/tmp/vm-connect.py
boat scp <skill-dir>/scripts/repair-nix.sh <builder-id>:/tmp/repair-nix.sh
boat ssh <builder-id> -- sudo bash /tmp/install-vm.sh
```

`install-vm.sh` installs Tailscale through its signed package repository, sets
`tailscaled --state=mem:`, and installs `boat-proxy-connect` and the Nix repair
helper. It does not modify the agent server binary or its generated service.

Connection explicitly reloads systemd units before restarting Tailscale. This
matters because Boat can restore configuration files after systemd has loaded
the stock units. Checking files alone does not verify the running service.

The connection helper waits for full file restoration before changing services.
Boat's `ready` state can precede restoration of file modes; treating it as fully
restored caused a real Nix socket permission failure. It supplies a transient shell environment under
`/run/boat-proxy`. It also writes the gateway key into the native client files
with mode 600: Claude's `env.ANTHROPIC_AUTH_TOKEN` and Codex's
`experimental_bearer_token`. It backs up each existing client file before its
first edit and preserves unrelated settings. It connects through Tailscale and
checks the authenticated model list. Client configuration survives a worker
snapshot; `/run` and the Tailscale identity do not.

At the end, the helper restarts Boat's agent service from SSH. This discards
native client processes warmed before the network and configuration were ready.
Run it before starting tasks, not during active work. In the resume test, a
stalled Codex conversation completed after this restart and explicitly selecting
its original model. Preserve provider, model, and effort on resume.

## Preserve and verify Nix

The user's `libxmtp` source image already has Determinate Nix, `/nix/store`,
`/etc/nix/nix.custom.conf` with the XMTP Cachix URL and public signing key, and
shell initialization. Keep those. `install-vm.sh` is an additive proxy installer,
not a replacement for the original `~/setup.sh` or the repository's `dev/nix-up`.

On the inspected clone, Nix was on PATH and the daemon appeared active, yet
`dev/nix-shell` failed with `Connection refused`. The socket units had failed
because their service was already active during restore. `repair-nix.sh` stops
the service, restarts both installed socket units, then starts the service and
checks daemon connectivity. The connection helper runs this after each restore.

Prove the full environment on a fresh clone, not just the installer:

```sh
boat exec <id> --cwd libxmtp --timeout 600 -- bash -lc \
  'dev/nix-shell --refresh --command bash -c "rustc --version && cargo --version && just --version && node --version && pnpm --version && protoc --version"'
```

Use `bash -c` inside the Nix environment. A nested login shell (`bash -lc`)
can reset PATH and hide the Nix tools. Also check `nix config show substituters`
for `https://xmtp.cachix.org`. Do not reinstall Nix or rewrite its managed
`nix.conf` merely because a restored socket needs repair.

Build base images from a **dedicated `--no-env` builder that has never run
`connect-vm.py`**. Do not promote an authenticated worker to a base image:
its client files, backups, shell snapshots, or Boat environment files may
contain the gateway key. Keep the clean base and apply changed scripts to a
builder derived from it. Before saving that builder:

```sh
boat ssh <builder-id> -- sudo systemctl stop tailscaled
boat ssh <builder-id> -- sudo rm -rf /run/boat-proxy
boat ssh <builder-id> -- rm -f /home/user/.codex/auth.json /home/user/.claude/.credentials.json
boat snapshot <builder-id> <new-versioned-name>
```

Also inspect other credential locations in the source snapshot, such as GitHub,
cloud CLIs, `.env` files, and shell history. A coding image may intentionally
contain private source; never share it publicly. Save a new name, test a clone,
and retain the source snapshot for rollback. Stop the builder when finished.

## Start or resume a worker

```sh
boat new --from <new-versioned-name> --environment boat-proxy --name <task> --ttl 7200 --json
python3 <skill-dir>/scripts/connect-vm.py <id> \
  --url https://<gateway-name>.<tailnet>.ts.net \
  --auth-key-file ~/.config/code-factory/boat-proxy/tailscale-auth-key
# Pick model IDs supported by both Boat and the successful helper output.
boat prompt <id> --provider claude --model <id-from-model-list> --new '<task>'
```

For a stopped worker, `boat resume <id>` then run `connect-vm.py` again before
prompting. The runtime environment and Tailscale identity are intentionally not
preserved across a reboot. No reconnect means no working gateway; do not fall
back to copying subscription credentials into the VM.

## Check failures in order

1. Mac: `launchctl print gui/$(id -u)/local.code-factory.boat-proxy`;
   `tailscale status`; `tailscale serve status`. Check that the Mac is awake.
2. Worker: `boat info <id> --json`, `boat ssh <id> -- tailscale status`.
   Reconnect after resume. A missing/expired enrollment key needs renewal.
3. Proxy: unauthenticated `/v1/models` must return 401, authenticated must return
   200 and provider models. Management routes must return 404. Do not put the key
   directly in a command argument or diagnostic output.
4. Agent: inspect `boat conversations` and `boat events`. Check provider auth,
   quota, exact model ID, and the Codex custom provider. Do not treat an HTTP 200
   stream as success until the agent reports a completed turn.

Stop local serving with `tailscale serve --https=443 off`. Stop the login service
with `launchctl bootout gui/$(id -u)/local.code-factory.boat-proxy`. Keep config
and auth files for a reversible stop; remove them only when asked.
