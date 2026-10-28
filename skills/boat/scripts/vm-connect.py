#!/usr/bin/env python3
"""Consume a transient connection file on a dedicated Boat proxy VM."""
import json
import os
from pathlib import Path
import pwd
import re
import shlex
import subprocess
import sys
import tempfile
import urllib.request
from urllib.parse import urlparse


def write_private(path, content, uid, gid, mode=0o600):
    """Replace a credential file without ever creating a world-readable copy."""
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name + '.')
    try:
        with os.fdopen(descriptor, 'w') as stream:
            os.fchown(stream.fileno(), uid, gid)
            os.fchmod(stream.fileno(), mode)
            stream.write(content)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def codex_config(content, url, token=None):
    """Replace only our provider and the root provider selector."""
    content = re.sub(r'(?ms)^# BEGIN BOAT PROXY.*?^# END BOAT PROXY\n?', '', content)
    parts = re.split(r'(?m)(?=^\[)', content, maxsplit=1)
    parts[0] = re.sub(r'(?m)^\s*model_provider\s*=.*\n?', '', parts[0])
    authentication = ('experimental_bearer_token = ' + json.dumps(token) + '\n'
                      if token is not None else 'env_key = "BOAT_PROXY_API_KEY"\n')
    provider = ('# BEGIN BOAT PROXY\n[model_providers.boat_proxy]\n'
                'name = "Boat local gateway"\n'
                f'base_url = {json.dumps(url + "/v1")}\n'
                + authentication + 'wire_api = "responses"\n'
                'requires_openai_auth = false\nsupports_websockets = true\n'
                '# END BOAT PROXY\n')
    return 'model_provider = "boat_proxy"\n' + ''.join(parts).rstrip() + '\n\n' + provider


def main():
    if os.geteuid() != 0 or len(sys.argv) != 2:
        raise SystemExit('Usage: sudo boat-proxy-connect /tmp/connection.json')
    source = Path(sys.argv[1])
    settings = json.loads(source.read_text())
    source.unlink()
    url = settings['url'].rstrip('/')
    parsed = urlparse(url)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username
            or parsed.path or parsed.query or parsed.fragment):
        raise SystemExit('Expected an HTTPS gateway origin without a path or credentials.')
    name = settings['hostname']
    if not re.fullmatch(r'[a-z0-9-]{1,63}', name):
        raise SystemExit('Invalid Tailscale hostname.')
    # Boat can restore /etc overlays after systemd has loaded the stock units.
    # Re-read the restored override before enrolling; never use disk-backed state.
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    subprocess.run(['/usr/local/bin/boat-proxy-repair-nix'], check=True)
    subprocess.run(['systemctl', 'restart', 'tailscaled'], check=True)
    user = pwd.getpwnam('user')
    root = Path('/run/boat-proxy')
    root.mkdir(mode=0o750, exist_ok=True)
    os.chown(root, 0, user.pw_gid)
    key = root / 'tailscale-key'
    write_private(key, settings['tailscale_key'], 0, 0)
    try:
        # Read the credential from a file; never expose it in process arguments.
        subprocess.run(['tailscale', 'up', '--auth-key=file:' + str(key),
                        '--hostname=' + name, '--accept-routes=false',
                        '--accept-dns=true', '--timeout=60s'], check=True)
    finally:
        key.unlink(missing_ok=True)
    token = settings['proxy_key']
    env = {'BOAT_PROXY_API_KEY': token, 'OPENAI_API_KEY': token,
           'CODEX_API_KEY': token, 'ANTHROPIC_AUTH_TOKEN': token,
           'ANTHROPIC_API_KEY': '', 'CLAUDE_CODE_OAUTH_TOKEN': '',
           'ANTHROPIC_BASE_URL': url, 'OPENAI_BASE_URL': url + '/v1',
           'CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY': '1',
           'CLAUDE_CODE_PROMPT_CACHE_TTL': '1h'}
    env_file = root / 'agent.env'
    write_private(env_file, ''.join(k + '=' + shlex.quote(v) + '\n' for k, v in env.items()),
                  0, user.pw_gid, 0o640)

    config = Path(user.pw_dir) / '.codex/config.toml'
    config.parent.mkdir(exist_ok=True)
    content = config.read_text() if config.exists() else ''
    backup = config.with_name('config.toml.before-boat-proxy')
    if config.exists() and not backup.exists():
        write_private(backup, content, user.pw_uid, user.pw_gid)
    # Global keys must precede every table. Preserve Boat's computer MCP table.
    # Boat's native agents do not inherit arbitrary named-environment variables.
    # Both native client config files therefore need the scoped gateway key.
    write_private(config, codex_config(content, url, token), user.pw_uid, user.pw_gid)

    claude = Path(user.pw_dir) / '.claude/settings.json'
    claude.parent.mkdir(exist_ok=True)
    claude_settings = json.loads(claude.read_text()) if claude.exists() else {}
    claude_backup = claude.with_name('settings.json.before-boat-proxy')
    if claude.exists() and not claude_backup.exists():
        write_private(claude_backup, claude.read_text(), user.pw_uid, user.pw_gid)
    claude_settings.setdefault('env', {}).update({key: env[key] for key in (
        'ANTHROPIC_BASE_URL', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_API_KEY',
        'CLAUDE_CODE_OAUTH_TOKEN', 'CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY')})
    claude_settings.setdefault('promptCacheTtl', '1h')
    write_private(claude, json.dumps(claude_settings, indent=2) + '\n', user.pw_uid, user.pw_gid)

    request = urllib.request.Request(url + '/v1/models', headers={'Authorization': 'Bearer ' + token})
    with urllib.request.urlopen(request, timeout=30) as response:
        models = [entry['id'] for entry in json.load(response)['data']]
    if not models:
        raise SystemExit('Gateway is reachable but has no authenticated provider models.')
    # Boat may warm native client processes before Tailscale is connected and
    # before these files exist. Start fresh processes with the connected config.
    subprocess.run(['systemctl', 'restart', 'ascii-agent.service'], check=True)
    print(json.dumps({'connected': True, 'models': models}))


if __name__ == '__main__':
    main()
