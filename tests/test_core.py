import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from core.environment import os_release, phase
from core.checks import Readiness
from core.launcher import Wizard, read_profile, identity
from core.runtime import load_runtime
from runtimes.codex.runtime import CodexRuntime

ROOT = Path(__file__).resolve().parents[1]


class CoreTests(unittest.TestCase):
    def wizard(self, checks, runtime, answers, key=lambda _: 'fixture-key-never-valid'):
        choose = Mock(side_effect=answers)
        with contextlib.redirect_stdout(io.StringIO()) as output:
            Wizard(checks, runtime, choose=choose, key=key, shell=Mock()).run()
        return choose, output.getvalue()

    def test_offline_never_offers_signin_or_calls_runtime(self):
        checks, runtime = Mock(), Mock()
        checks.ready.return_value = False
        _, text = self.wizard(checks, runtime, ['0'])
        runtime.login.assert_not_called()
        runtime.start.assert_not_called()
        runtime.authenticated.assert_not_called()
        self.assertNotIn('Step 2', text)
        self.assertIn('Wi-Fi', text)

    def test_wifi_then_login_and_start_in_same_flow(self):
        checks, runtime = Mock(), Mock()
        checks.ready.side_effect = [False, True, True, True]
        runtime.authenticated.return_value = False
        runtime.login.return_value = True
        self.wizard(checks, runtime, ['1', '1', '0'])
        checks.connect.assert_called_once()
        runtime.login.assert_called_once_with('device', None)
        runtime.start.assert_called_once()

    def test_disconnect_while_choosing_prevents_login(self):
        checks, runtime = Mock(), Mock()
        checks.ready.side_effect = [True, False, False]
        runtime.authenticated.return_value = False
        self.wizard(checks, runtime, ['1', '0'])
        runtime.login.assert_not_called()
        runtime.start.assert_not_called()

    def test_disconnect_after_login_prevents_agent_start(self):
        checks, runtime = Mock(), Mock()
        checks.ready.side_effect = [True, True, False, False]
        runtime.authenticated.return_value = False
        runtime.login.return_value = True
        self.wizard(checks, runtime, ['1', '0'])
        runtime.start.assert_not_called()

    def test_existing_login_still_requires_readiness(self):
        checks, runtime = Mock(), Mock()
        checks.ready.side_effect = [True, False]
        runtime.authenticated.return_value = True
        self.wizard(checks, runtime, ['0'])
        runtime.start.assert_not_called()

    def test_authentication_methods_use_same_guard(self):
        for answer, method in [('1','device'), ('2','browser'), ('3','key')]:
            with self.subTest(method=method):
                checks, runtime = Mock(), Mock()
                checks.ready.return_value = True
                runtime.authenticated.return_value = False
                runtime.login.return_value = True
                self.wizard(checks, runtime, [answer,'0'])
                runtime.login.assert_called_once_with(method, 'fixture-key-never-valid' if method == 'key' else None)
                runtime.start.assert_called_once()

    def test_network_failure_does_not_run_clock_or_zfs(self):
        run = Mock(return_value=subprocess.CompletedProcess([], 6, '000', 'DNS failure'))
        checks = Readiness({'package_endpoints':['https://fixture.invalid/'], 'default_filesystem':'zfs'}, run=run)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(checks.ready())
        self.assertEqual(run.call_args.args[0][0], 'curl')
        self.assertEqual(run.call_count, 1)

    def test_https_auth_denial_is_reachability_not_login(self):
        checks = Readiness({'package_endpoints':['https://fixture.invalid/']}, run=Mock(return_value=subprocess.CompletedProcess([],0,'403','')))
        self.assertTrue(checks.internet()[0])

    def test_server_failure_is_not_ready(self):
        checks = Readiness({'package_endpoints':['https://fixture.invalid/']}, run=Mock(return_value=subprocess.CompletedProcess([],0,'503','')))
        self.assertFalse(checks.internet()[0])

    def test_missing_module_is_failure_not_exception(self):
        run = Mock(side_effect=[subprocess.CompletedProcess([],0,'7.2.8',''), subprocess.CompletedProcess([],0,'','')])
        self.assertFalse(Readiness({'default_filesystem':'zfs'}, run=run).storage()[0])

    def test_chroot_never_claims_live_or_installed_boot(self):
        self.assertEqual(phase(in_chroot=True, live_marker=True, root_type='overlay'), 'chroot')
        self.assertEqual(phase(in_chroot=False, live_marker=True, root_type='overlay'), 'live')
        self.assertEqual(phase(in_chroot=False, live_marker=False, root_type='zfs'), 'unconfirmed')
        self.assertEqual(phase(in_chroot=False, live_marker=True, root_type='ext4'), 'unconfirmed')

    def test_os_release_is_parsed_without_executing_shell(self):
        with tempfile.TemporaryDirectory() as area:
            path = Path(area)/'os-release'
            path.write_text('ID=nixos\nPRETTY_NAME="NixOS Linux"\nEXTRA="$(id)"\n')
            self.assertEqual(os_release(path)['ID'], 'nixos')
            self.assertEqual(os_release(path)['EXTRA'], '$(id)')

    def test_profiles_keep_runtime_and_target_separate(self):
        for distro in ['arch','nixos']:
            profile = read_profile(ROOT, distro)
            text = identity(ROOT, profile, {'distro_id':distro,'phase':'live'})
            self.assertIn('ControlStackAI Installer', text)
            self.assertIn('new to Linux', text)
            self.assertFalse(profile['capabilities']['physical_disk_executor'])
            self.assertIn('default_target', text)
        with self.assertRaises(ValueError): read_profile(ROOT, '../../auth')

    def test_unknown_runtime_cannot_fall_back(self):
        with self.assertRaises(ValueError): load_runtime('openclaw-not-integrated')

    def test_codex_key_only_on_stdin_with_private_identity(self):
        run = Mock(return_value=subprocess.CompletedProcess([],0,''))
        with tempfile.TemporaryDirectory() as area, patch.dict(os.environ, {'OPENAI_API_KEY':'inherited-fixture-never-valid'}):
            runtime = CodexRuntime(Path(area)/'session', '# Fixture identity\n', run)
            self.assertTrue(runtime.login('key','fixture-key-never-valid'))
            args, kwargs = run.call_args_list[0]
            self.assertEqual(args[0], ['codex','login','--with-api-key'])
            self.assertEqual(kwargs['input'], 'fixture-key-never-valid')
            self.assertNotIn('OPENAI_API_KEY',kwargs['env'])
            self.assertEqual(runtime.home.stat().st_mode & 0o777, 0o700)
            self.assertEqual((runtime.home/'config.toml').stat().st_mode & 0o777, 0o600)
            self.assertEqual((runtime.home/'AGENTS.md').read_text(),'# Fixture identity\n')
            self.assertFalse((runtime.home/'auth.json').exists())

    def test_forget_preserves_work_but_clears_auth_and_reloads_identity(self):
        run = Mock(return_value=subprocess.CompletedProcess([],0,''))
        with tempfile.TemporaryDirectory() as area:
            runtime = CodexRuntime(Path(area)/'session', '# Fixture identity\n', run)
            (runtime.home/'auth.json').write_text('{"fixture":true}')
            (runtime.work/'plan.md').write_text('Nonsecret plan')
            runtime.forget()
            self.assertFalse((runtime.home/'auth.json').exists())
            self.assertTrue((runtime.home/'AGENTS.md').exists())
            self.assertEqual((runtime.work/'plan.md').read_text(),'Nonsecret plan')
