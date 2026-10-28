# Project deployments and warm snapshot refreshes

## Select a deployment

The common gateway configuration lives in
`~/.config/code-factory/boat-proxy/`. Each project has its own top-level JSON
record, such as `libxmtp.json`. List those files and match `repository`, `name`,
and `workdir` to the requested work. Do not assume one default image and do not
read OAuth JSON files under `auth/` as deployment metadata.

A deployment records at least:

```json
{
  "kind": "boat-deployment",
  "name": "libxmtp",
  "repository": "https://github.com/xmtp/libxmtp",
  "workdir": "/home/user/libxmtp",
  "snapshot": "<validated saved snapshot>",
  "revision": "<full commit SHA>",
  "environment": "boat-proxy",
  "gateway_url": "https://<gateway>.<tailnet>.ts.net",
  "status": "ready",
  "cache": {
    "cargo_target_dir": "/home/user/libxmtp/target",
    "kache_dir": "/home/user/.local/share/code-factory/libxmtp/kache",
    "manifest": "/home/user/.local/share/code-factory/libxmtp/warm.json"
  }
}
```

Other deployments can have different images, workdirs, toolchains, and commands.

## Detect and refresh stale artifacts

When preparing Boat work, fetch the repository's `main` and compare its full
commit SHA with the deployment's cached `revision`. Also refresh when the
recorded warm-up failed, build inputs changed, or a restored clone lacks the
recorded caches. Use a clean builder; never reset an active task's worktree.
A documentation-only update may produce a no-op build, but the snapshot still
needs the current checkout and revision.

1. Create a builder from the project's prior clean base with `--no-env`. Wait
   for `.sandbox.hydrated == true`, not only `state == ready`:
   `python3 <skill-dir>/scripts/connect-vm.py <id> --wait-only`.
2. Check for local changes and commits. Fetch `origin/main` and fast-forward
   only. If that fails, investigate; do not discard changes or include an
   unreviewed task branch in the shared base.
3. Read the repository's current instructions. Apply the current image scripts
   and warm its actual build and test targets.
4. Put caches in paths Boat saves. Boat excludes `~/.cache`; warming there alone
   does not make a warm image. Record cache paths, source SHA, successful commands,
   and toolchain in a manifest outside `~/.cache`.
5. Stop cache daemons cleanly before capture so database WALs are checkpointed.
   Stop Nix's service and sockets and remove stale socket files; startup will
   recreate them. Do not enroll a base builder in Tailscale or run agents with
   subscription credentials on it.
6. Inspect configs, agent shell snapshots, and logs for credentials. Even a
   failed agent run can save its environment in a shell snapshot. Prefer a
   fresh `--no-env` builder from a known clean base to cleaning an authenticated
   worker. If a published base contains a key, remove it and rotate that key.
7. Save under a new versioned name, such as `<project>-<short-main-sha>-warm`.
   Keep the previous image until the replacement passes restore checks.
8. Start a fresh clone without credentials. Wait for restoration, repair runtime
   sockets, verify caches exist, and repeat the warm-up commands. Check that
   Cargo reuses artifacts and Kache's persisted entries are available.
9. Update only the matching deployment JSON after validation. Keep the previous
   name in `previous_snapshot` for rollback. Stop builder and verification VMs.
   Do not delete old images without the user's authorization.

Updating a deployment does not require changing the plugin for every source
commit. Change the skill when the repeatable workflow changes.

## libxmtp cache warm-up

Preserve Determinate Nix, `/nix/store`, the XMTP Cachix settings in
`/etc/nix/nix.custom.conf`, and the repository's Nix wrappers. Before building,
run `sudo /usr/local/bin/boat-proxy-repair-nix` after restoration is complete.
Its final check must run as `user`, since root can connect to a socket whose
permissions block ordinary builds.

Run the bundled script as the regular user on a clean `main` checkout:

```sh
bash <skill-dir>/scripts/warm-libxmtp.sh /home/user/libxmtp
```

It fast-forwards `main`, uses `/home/user/libxmtp/target` for Cargo artifacts,
puts Kache in `/home/user/.local/share/code-factory/libxmtp/kache`, and configures
Kache so native agent shells use the same persistent store. It uses the
repository's Nix, Just, and agent-run commands:

```sh
dev/nix-shell 'just check'
dev/nix-shell 'just test workspace --no-run'
dev/nix-shell 'just test crate xmtp_common'
```

These warm default-member checks and workspace test binaries, then run real
crate tests. They do not cover every platform SDK, feature set, release profile,
or integration test. Warm and record additional commands for those workloads.
Full workspace tests need the backend in the repository's current instructions.

After success, `warm.json` and `warm.log` record the revision and commands. Keep
Cargo's target directory, Kache store, and Cargo registry/git caches in the
snapshot; verify `.boatignore` does not exclude them. Do not point every worktree
at one Cargo target directory: only the base checkout uses this target path.

Before saving, run `dev/nix-shell 'kache daemon stop'`, then stop
`nix-daemon.service`, `nix-daemon.socket`, and `determinate-nixd.socket` if
installed. Remove their stale Unix socket paths. Verify a fresh clone with the
same commands and inspect the compile/cache output, not only directory sizes.
