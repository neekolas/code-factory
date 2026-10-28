#!/usr/bin/env python3
"""Create a private CLIProxyAPI configuration and optional macOS login service."""
import argparse
import json
import os
from pathlib import Path
import plistlib
import secrets
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=Path.home() / '.config/code-factory/boat-proxy')
    parser.add_argument('--install-service', action='store_true')
    args = parser.parse_args()
    root = args.directory.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    (root / 'auth').mkdir(exist_ok=True, mode=0o700)
    key_path = root / 'client-key'
    if not key_path.exists():
        with key_path.open('x') as stream:
            os.chmod(key_path, 0o600)
            stream.write('cf-boat-' + secrets.token_urlsafe(32) + '\n')
    key = key_path.read_text().strip()
    config = root / 'config.yaml'
    if not config.exists():
        # JSON is valid YAML. Avoid an extra YAML dependency and escaping bugs.
        data = {
            'config-version': 8,
            'server': {'host': '127.0.0.1', 'port': 8317},
            'management': {'allow-remote': False, 'secret-key': '', 'disable-control-panel': True},
            'access': {'api-keys': [key]},
            'oauth': {'auth-dir': str(root / 'auth')},
            'routing': {'strategy': 'round-robin', 'session-affinity': True,
                        'session-affinity-ttl': '24h',
                        'retry': {'request-retry': 2, 'max-retry-credentials': 3}},
            'upstream': {'claude': {'disable-claude-cloak-mode': True,
                                    'disable-cloaking-model-list': True},
                         'codex': {'disable-codex-cloaking': True}},
            'observability': {'logs': {'request-log': False, 'error-logs-max-files': 0}},
        }
        with config.open('x') as stream:
            os.chmod(config, 0o600)
            json.dump(data, stream, indent=2)
            stream.write('\n')
    print(f'Configuration: {config}')
    print(f'Client key file: {key_path} (value not displayed)')
    if args.install_service:
        binary = shutil.which('cliproxyapi')
        if not binary:
            raise SystemExit('Install cliproxyapi with Homebrew first.')
        label = 'local.code-factory.boat-proxy'
        target = Path.home() / 'Library/LaunchAgents' / (label + '.plist')
        target.parent.mkdir(parents=True, exist_ok=True)
        data = {'Label': label, 'ProgramArguments': [binary, '-config', str(config)],
                'RunAtLoad': True, 'KeepAlive': True, 'WorkingDirectory': str(root),
                'StandardOutPath': str(root / 'service.log'),
                'StandardErrorPath': str(root / 'service.log')}
        if target.exists():
            if plistlib.loads(target.read_bytes()) != data:
                raise SystemExit(f'Refusing to replace a different service: {target}')
        else:
            target.write_bytes(plistlib.dumps(data))
            os.chmod(target, 0o600)
        service = f'gui/{os.getuid()}/{label}'
        if subprocess.run(['launchctl', 'print', service], capture_output=True).returncode:
            subprocess.run(['launchctl', 'bootstrap', f'gui/{os.getuid()}', str(target)], check=True)
        print(f'Login service: {label}')


if __name__ == '__main__':
    main()
