#!/usr/bin/env python3
"""Store only gateway client credentials in a dedicated Boat environment."""
import argparse
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlparse


def boat(*arguments, value=None):
    result = subprocess.run(['boat', '--no-update', *arguments, '--json'],
                            input=value, text=True, capture_output=True)
    if result.returncode:
        # Do not display configuration responses, which may contain secret values.
        raise SystemExit(f'Boat command failed: {" ".join(arguments[:3])}. Check account permissions.')
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', default='boat-proxy')
    parser.add_argument('--directory', type=Path, default=Path.home() / '.config/code-factory/boat-proxy')
    parser.add_argument('--url', required=True)
    args = parser.parse_args()
    url = urlparse(args.url)
    if (url.scheme != 'https' or not url.hostname or url.username
            or url.path not in ('', '/') or url.query or url.fragment):
        parser.error('Use an HTTPS gateway origin without credentials or a path.')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', args.name) or args.name.startswith('-'):
        parser.error('Invalid Boat environment name.')
    existing = json.loads(boat('env', 'list'))['environments']
    if not any(e['name'] == args.name for e in existing):
        boat('env', 'new', args.name)
    boat('env', 'set', args.name, '--agents-credentials', 'false',
         '--boat-credentials', 'false', '--github', 'false', '--secrets', 'true',
         '--safe-for-third-parties', 'false')
    key = (args.directory / 'client-key').read_text().strip()
    variables = {'BOAT_PROXY_API_KEY': key, 'OPENAI_API_KEY': key, 'CODEX_API_KEY': key,
                 'ANTHROPIC_AUTH_TOKEN': key, 'ANTHROPIC_API_KEY': '',
                 'CLAUDE_CODE_OAUTH_TOKEN': '', 'ANTHROPIC_BASE_URL': args.url.rstrip('/'),
                 'OPENAI_BASE_URL': args.url.rstrip('/') + '/v1',
                 'CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY': '1',
                 'CLAUDE_CODE_PROMPT_CACHE_TTL': '1h'}
    for name, value in variables.items():
        boat('env', 'set-var', args.name, name, value=value + '\n')
    print(f'Configured Boat environment {args.name}. No subscription OAuth tokens uploaded.')


if __name__ == '__main__':
    main()
