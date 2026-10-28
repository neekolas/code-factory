#!/usr/bin/env bash
# Repair sockets restored from a Nix-equipped Boat snapshot, before starting work.
set -euo pipefail
nix_bin=/nix/var/nix/profiles/default/bin/nix
[[ -x "$nix_bin" ]] || exit 0
[[ $(id -u) == 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
systemctl daemon-reload
sockets=(nix-daemon.socket)
if systemctl cat determinate-nixd.socket >/dev/null 2>&1; then
  sockets+=(determinate-nixd.socket)
fi
# Stop the service first. Starting its socket while it is active is refused.
systemctl stop nix-daemon.service
systemctl stop "${sockets[@]}"
systemctl start "${sockets[@]}"
systemctl start nix-daemon.service
runuser -u user -- "$nix_bin" store info --store daemon
