#!/usr/bin/env python3
"""Inject gateway access and a fresh Tailscale enrollment into one Boat VM."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time
import uuid


def wait_for_restore(sandbox_id, timeout=600):
    """A ready VM can still be restoring file contents and permissions."""
    deadline = time.monotonic() + timeout
    announced = False
    while True:
        result = subprocess.run(['boat', '--no-update', 'info', sandbox_id, '--json'],
                                check=True, capture_output=True, text=True)
        state = json.loads(result.stdout)['sandbox']
        if state.get('hydrated') is True:
            return
        if state.get('state') in ('stopped', 'stopping', 'deleted', 'failed'):
            raise SystemExit('The VM must be running before preparing it.')
        if time.monotonic() >= deadline:
            raise SystemExit('Snapshot restore did not finish within 10 minutes; inspect boat info.')
        if not announced:
            print('Waiting for snapshot files and permissions to finish restoring...', flush=True)
            announced = True
        time.sleep(5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sandbox_id')
    parser.add_argument('--auth-key-file', type=Path,
                        help='Local file containing a reusable, ephemeral, tagged Tailscale auth key')
    parser.add_argument('--wait-only', action='store_true',
                        help='Wait for complete file restoration without sending any credentials')
    parser.add_argument('--directory', type=Path, default=Path.home() / '.config/code-factory/boat-proxy')
    parser.add_argument('--url', help='Private HTTPS Tailscale Serve origin; auto-detected on the gateway Mac')
    args = parser.parse_args()
    if not re.fullmatch(r'bx_[a-z0-9]+', args.sandbox_id):
        parser.error('Use an explicit bx_ sandbox ID.')
    if not args.wait_only and args.auth_key_file is None:
        parser.error('--auth-key-file is required unless using --wait-only')
    wait_for_restore(args.sandbox_id)
    if args.wait_only:
        print('Snapshot restoration complete.')
        return
    url = args.url
    if not url:
        result = subprocess.run(['tailscale', 'status', '--json'], check=True, capture_output=True, text=True)
        status = json.loads(result.stdout)
        if status['BackendState'] != 'Running':
            raise SystemExit('Tailscale must be running on the gateway Mac.')
        url = 'https://' + status['Self']['DNSName'].rstrip('.')
    data = {'url': url, 'proxy_key': (args.directory / 'client-key').read_text().strip(),
            'tailscale_key': args.auth_key_file.read_text().strip(),
            'hostname': 'boat-' + args.sandbox_id.replace('_', '-')}
    remote = '/tmp/boat-proxy-' + uuid.uuid4().hex + '.json'
    # NamedTemporaryFile is mode 0600. JSON goes over SCP, never through argv or logs.
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json') as file:
        json.dump(data, file)
        file.flush()
        subprocess.run(['boat', '--no-update', 'scp', file.name, args.sandbox_id + ':' + remote], check=True)
    try:
        subprocess.run(['boat', '--no-update', 'ssh', args.sandbox_id, '--',
                        'sudo', '/usr/local/bin/boat-proxy-connect', remote], check=True)
    finally:
        subprocess.run(['boat', '--no-update', 'ssh', args.sandbox_id, '--', 'rm', '-f', remote],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == '__main__':
    main()
