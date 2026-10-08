import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from core.frontend import Bridge, atomic_json, fingerprint, live_facts
from core.support import template, save_new, read_json
from core.launcher import Wizard

ROOT = Path(__file__).resolve().parents[1]
FACTS = {'distro_id': 'arch', 'distro_name': 'Fixture Linux', 'kernel': 'fixture-kernel', 'phase': 'live', 'uid': 0}


class FrontendTests(unittest.TestCase):
    def bridge(self, area):
        return Bridge(ROOT, Path(area) / 'work', FACTS)

    def test_preset_selection_is_editable_and_uses_shared_defaults(self):
        with tempfile.TemporaryDirectory() as area:
            bridge = self.bridge(area)
            state = bridge.select('hyprland')
            self.assertEqual(state['handoff']['choices']['appearance']['panel'], 'three-floating-islands')
            value = bridge.handoff()
            value['choices']['desktop'] = 'unlisted-owner-session'
            atomic_json(bridge.record, value)
            self.assertEqual(bridge.snapshot()['handoff']['choices']['desktop'], 'unlisted-owner-session')

    def test_replacing_choices_keeps_previous_work_and_requires_reverification(self):
        with tempfile.TemporaryDirectory() as area:
            bridge = self.bridge(area)
            bridge.select('familiar')
            value = bridge.handoff()
            value['checks'] = [{'name': 'Old check', 'status': 'pass', 'detail': 'Historical result'}]
            value['remaining'] = ['Review disk layout']
            atomic_json(bridge.record, value)
            result = bridge.select('custom')['handoff']
            self.assertEqual(result['choices'], {})
            self.assertEqual(result['remaining'], ['Review disk layout'])
            self.assertEqual(result['checks'][0]['status'], 'pending')
            self.assertEqual(read_json(bridge.work / 'handoff.previous.json'), value)

    def test_invalid_preset_preserves_active_record(self):
        with tempfile.TemporaryDirectory() as area:
            bridge = self.bridge(area)
            bridge.select('custom')
            before = bridge.record.read_bytes()
            with self.assertRaises(ValueError): bridge.select('missing')
            self.assertEqual(before, bridge.record.read_bytes())

    def test_export_requires_the_exact_reviewed_fingerprint(self):
        with tempfile.TemporaryDirectory() as area:
            bridge = self.bridge(area)
            bridge.select('familiar')
            old = bridge.snapshot()['fingerprint']
            bridge.select('minimal')
            target = Path(area) / 'export.json'
            with self.assertRaises(ValueError): bridge.export_record(target, old)
            self.assertFalse(target.exists())
            bridge.export_record(target, bridge.snapshot()['fingerprint'])
            self.assertEqual(read_json(target)['preset'], 'minimal')
            with self.assertRaises(FileExistsError): bridge.export_record(target, bridge.snapshot()['fingerprint'])

    def test_import_backs_up_local_record_and_marks_historical_checks_pending(self):
        with tempfile.TemporaryDirectory() as area:
            bridge = self.bridge(area)
            bridge.select('custom')
            old = bridge.handoff()
            value = template({'desktop': 'sway'})
            value['checks'] = [{'name': 'Disk boot', 'status': 'pass', 'detail': 'Another machine'}]
            source = Path(area) / 'saved.json'
            save_new(source, value)
            result = bridge.import_record(source)['handoff']
            self.assertEqual(result['checks'][0]['status'], 'pending')
            self.assertEqual(read_json(bridge.work / 'handoff.previous.json'), old)

    def test_recovery_selects_intent_without_executing_recovery(self):
        with tempfile.TemporaryDirectory() as area:
            bridge = self.bridge(area)
            result = bridge.intent('recover')
            self.assertEqual(result['handoff']['intent'], 'recover')
            self.assertEqual(result['handoff']['plan']['target_disks'], [])

    def test_invalid_edited_json_keeps_previous_choices(self):
        with tempfile.TemporaryDirectory() as area:
            bridge = self.bridge(area)
            bridge.select('custom')
            before = bridge.record.read_bytes()
            def edit(args):
                Path(args[-1]).write_text('{not JSON')
                return subprocess.CompletedProcess(args, 0)
            with patch('core.frontend.subprocess.run', side_effect=edit), patch.dict('os.environ', {'EDITOR': 'fixture-editor'}):
                with self.assertRaises(ValueError): bridge.edit()
            self.assertEqual(bridge.record.read_bytes(), before)

    def test_atomic_json_replaces_symlink_without_touching_its_target(self):
        with tempfile.TemporaryDirectory() as area:
            target = Path(area) / 'protected.json'
            target.write_text('Keep this')
            link = Path(area) / 'record.json'
            link.symlink_to(target)
            atomic_json(link, {'choices': {}})
            self.assertEqual(target.read_text(), 'Keep this')
            self.assertFalse(link.is_symlink())
            self.assertEqual(link.stat().st_mode & 0o777, 0o600)

    def test_nonlive_host_cannot_run_bridge_actions(self):
        with patch('core.frontend.discover', return_value={**FACTS, 'phase': 'unconfirmed'}):
            with self.assertRaises(ValueError): live_facts()

    def test_return_to_dashboard_still_requires_readiness(self):
        import contextlib, io
        checks, runtime, choose = Mock(), Mock(), Mock()
        checks.ready.return_value = True
        runtime.authenticated.return_value = True
        with contextlib.redirect_stdout(io.StringIO()):
            Wizard(checks, runtime, choose=choose, return_after_agent=True).run()
        runtime.start.assert_called_once()
        choose.assert_not_called()
        self.assertEqual(checks.ready.call_count, 2)
