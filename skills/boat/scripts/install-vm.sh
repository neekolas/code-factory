#!/usr/bin/env bash
# Run as root on a dedicated image builder. Installs no credentials.
set -euo pipefail
[[ $(id -u) == 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if ! command -v tailscaled >/dev/null; then
  # Official signed Ubuntu/Debian repository, selected from the guest OS.
  # shellcheck disable=SC1091
  . /etc/os-release
  case "$ID" in ubuntu|debian) ;; *) echo 'Expected Ubuntu or Debian.' >&2; exit 1;; esac
  curl -fsSL "https://pkgs.tailscale.com/stable/$ID/$VERSION_CODENAME.noarmor.gpg" \
    -o /usr/share/keyrings/tailscale-archive-keyring.gpg
  curl -fsSL "https://pkgs.tailscale.com/stable/$ID/$VERSION_CODENAME.tailscale-keyring.list" \
    -o /etc/apt/sources.list.d/tailscale.list
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y tailscale
fi
install -m 755 "$script_dir/vm-connect.py" /usr/local/bin/boat-proxy-connect
install -m 755 "$script_dir/repair-nix.sh" /usr/local/bin/boat-proxy-repair-nix
mkdir -p /etc/systemd/system/tailscaled.service.d
cat >/etc/systemd/system/tailscaled.service.d/boat-proxy.conf <<'EOF'
[Service]
ExecStart=
ExecStart=/usr/sbin/tailscaled --state=mem: --socket=/run/tailscale/tailscaled.sock
EOF
# Boat regenerates its agent service. Configure native agent credentials through
# a named Boat environment, not an agent-service override.
rm -f /etc/systemd/system/ascii-agent.service.d/90-boat-proxy.conf
# Runtime env is in /run, which is not captured in a filesystem snapshot.
cat >/etc/profile.d/boat-proxy.sh <<'EOF'
if [ -r /run/boat-proxy/agent.env ]; then
  set -a
  . /run/boat-proxy/agent.env
  set +a
fi
EOF
systemctl daemon-reload
systemctl enable tailscaled
systemctl restart tailscaled
echo 'Installed. Connect this VM with connect-vm.py before prompting an agent.'
