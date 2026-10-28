"""Regression checks for provider selection without destroying Boat's MCP config."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('vm_connect', Path(__file__).parents[1] / 'scripts/vm-connect.py')
vm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vm)
env_spec = importlib.util.spec_from_file_location('configure_environment', Path(__file__).parents[1] / 'scripts/configure-environment.py')
env = importlib.util.module_from_spec(env_spec)
env_spec.loader.exec_module(env)
controller_spec = importlib.util.spec_from_file_location('connect_vm', Path(__file__).parents[1] / 'scripts/connect-vm.py')
controller = importlib.util.module_from_spec(controller_spec)
controller_spec.loader.exec_module(controller)


class ConfigTests(unittest.TestCase):
    def test_ready_vm_waits_for_file_restoration(self):
        responses = [
            subprocess.CompletedProcess([], 0, stdout=json.dumps({'sandbox': {'state': 'ready', 'hydrated': False}})),
            subprocess.CompletedProcess([], 0, stdout=json.dumps({'sandbox': {'state': 'ready', 'hydrated': True}})),
        ]
        with patch.object(controller.subprocess, 'run', side_effect=responses) as run:
            with patch.object(controller.time, 'sleep') as sleep:
                controller.wait_for_restore('bx_test')
        self.assertEqual(run.call_count, 2)
        sleep.assert_called_once_with(5)

    def test_stopped_vm_cannot_be_prepared(self):
        response = subprocess.CompletedProcess([], 0, stdout=json.dumps({'sandbox': {'state': 'stopped', 'hydrated': False}}))
        with patch.object(controller.subprocess, 'run', return_value=response):
            with self.assertRaises(SystemExit):
                controller.wait_for_restore('bx_test')

    def test_credential_file_replacement_is_private(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'settings.json'
            target.write_text('old')
            target.chmod(0o644)
            vm.write_private(target, 'private-key', os.getuid(), os.getgid())
            self.assertEqual(target.read_text(), 'private-key')
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            self.assertEqual(list(Path(temporary).iterdir()), [target])
    def test_cloud_upload_keeps_key_out_of_process_arguments_and_errors(self):
        secret = 'sentinel-sensitive-gateway-key'
        failure = subprocess.CompletedProcess([], 1, stdout=secret, stderr=secret)
        with patch.object(env.subprocess, 'run', return_value=failure) as run:
            with self.assertRaises(SystemExit) as error:
                env.boat('env', 'set-var', 'boat-proxy', 'OPENAI_API_KEY', value=secret)
        self.assertNotIn(secret, str(error.exception))
        self.assertNotIn(secret, ' '.join(run.call_args.args[0]))
        self.assertEqual(run.call_args.kwargs['input'], secret)

    def test_host_rerun_keeps_client_key_and_existing_config(self):
        script = Path(__file__).parents[1] / 'scripts/configure-host.py'
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'gateway'
            command = [sys.executable, str(script), '--directory', str(root)]
            subprocess.run(command, check=True, capture_output=True)
            first_key = (root / 'client-key').read_bytes()
            first_config = (root / 'config.yaml').read_bytes()
            subprocess.run(command, check=True, capture_output=True)
            self.assertEqual((root / 'client-key').read_bytes(), first_key)
            self.assertEqual((root / 'config.yaml').read_bytes(), first_config)
            self.assertEqual((root / 'client-key').stat().st_mode & 0o777, 0o600)
            self.assertEqual((root / 'config.yaml').stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(first_config)['server']['host'], '127.0.0.1')

    def test_selects_proxy_preserves_mcp_and_other_provider(self):
        original = '''model_provider = "previous"
model_reasoning_effort = "high"
[mcp_servers.computer]
command = "/usr/bin/python3"
args = ["/home/user/.config/ascii/computer-mcp.py"]
[model_providers.previous]
base_url = "https://old.example/v1"
'''
        parsed = tomllib.loads(vm.codex_config(original, 'https://mac.example.ts.net'))
        self.assertEqual(parsed['model_provider'], 'boat_proxy')
        self.assertEqual(parsed['model_reasoning_effort'], 'high')
        self.assertEqual(parsed['mcp_servers'], tomllib.loads(original)['mcp_servers'])
        self.assertEqual(parsed['model_providers']['previous'], tomllib.loads(original)['model_providers']['previous'])
        proxy = parsed['model_providers']['boat_proxy']
        self.assertEqual(proxy['base_url'], 'https://mac.example.ts.net/v1')
        self.assertEqual(proxy['env_key'], 'BOAT_PROXY_API_KEY')
        self.assertFalse(proxy['requires_openai_auth'])

    def test_reconnection_replaces_endpoint_without_duplicate_tables(self):
        first = vm.codex_config('', 'https://first.example.ts.net')
        second = vm.codex_config(first, 'https://second.example.ts.net')
        parsed = tomllib.loads(second)
        self.assertEqual(parsed['model_providers']['boat_proxy']['base_url'], 'https://second.example.ts.net/v1')
        self.assertEqual(vm.codex_config(second, 'https://second.example.ts.net'), second)

    def test_native_agent_does_not_depend_on_inherited_environment(self):
        token = 'test-gateway-key'
        result = vm.codex_config('', 'https://mac.example.ts.net', token)
        provider = tomllib.loads(result)['model_providers']['boat_proxy']
        self.assertEqual(provider['experimental_bearer_token'], token)
        self.assertNotIn('env_key', provider)
        refreshed = vm.codex_config(result, 'https://mac.example.ts.net', 'rotated-key')
        self.assertNotIn(token, refreshed)
        self.assertEqual(tomllib.loads(refreshed)['model_providers']['boat_proxy']['experimental_bearer_token'], 'rotated-key')


if __name__ == '__main__':
    unittest.main()
