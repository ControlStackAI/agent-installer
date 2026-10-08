"""Behavioral checks for editable presets, untrusted handoffs and boot evidence."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from core.support import (preset, template, read_json, save_new, validate_handoff,
                          export_handoff, import_handoff, review)
from core.diagnostics import COMMANDS, inventory, verification

ROOT = Path(__file__).resolve().parents[1]


class SupportTests(unittest.TestCase):
    def test_custom_nested_choices_and_alternative_desktop_are_preserved(self):
        choices = preset(ROOT, 'familiar', {'desktop': 'sway', 'filesystem': 'ext4',
                         'applications': [], 'appearance': {'scale': 1.5}, 'my_service': {'enabled': True}})
        self.assertEqual(choices['desktop'], 'sway')
        self.assertEqual(choices['applications'], [])
        self.assertTrue(choices['my_service']['enabled'])
        self.assertEqual(preset(ROOT, 'custom'), {})
        base = preset(ROOT, 'hyprland', {'appearance': {'panel_height': 40}})
        self.assertEqual(base['appearance']['panel'], 'three-floating-islands')
        self.assertEqual(base['appearance']['panel_height'], 40)
        self.assertEqual(preset(ROOT, 'hyprland')['appearance']['panel_height'], 32)

    def test_no_preset_selects_a_disk_password_or_encryption(self):
        for name in ('familiar', 'simple', 'hyprland', 'minimal', 'custom'):
            choices = preset(ROOT, name)
            self.assertNotIn('password', choices)
            self.assertNotIn('encrypt', choices)
            self.assertFalse(template(choices)['plan']['target_disks'])

    def test_handoff_roundtrip_resets_verification_and_carries_custom_choices(self):
        with tempfile.TemporaryDirectory() as area:
            area = Path(area)
            value = template({'desktop': 'my-custom-session', 'services': {'example': True}}, experience='advanced')
            value['checks'] = [{'name': 'Boot', 'status': 'pass', 'detail': 'Previous computer booted.'}]
            value['remaining'] = ['Check root and disk identities after reboot']
            save_new(area / 'draft.json', value)
            export_handoff(area / 'draft.json', area / 'saved.json', reviewed=True)
            restored = import_handoff(area / 'saved.json', area / 'handoff.json')
            self.assertEqual(restored['choices'], value['choices'])
            self.assertEqual(restored['checks'][0]['status'], 'pending')
            self.assertIn('untrusted', restored['notes'][-1])
            self.assertEqual((area / 'handoff.json').stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads((area / 'saved.json').read_text())['checks'][0]['status'], 'pass')

    def test_export_requires_review_and_does_not_create_a_destination(self):
        with tempfile.TemporaryDirectory() as area:
            source, target = Path(area) / 'draft.json', Path(area) / 'export.json'
            save_new(source, template())
            with self.assertRaises(ValueError):
                export_handoff(source, target)
            self.assertFalse(target.exists())

    def test_existing_files_and_symlinks_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as area:
            file = Path(area) / 'record.json'
            save_new(file, template())
            link = Path(area) / 'link.json'
            link.symlink_to(file)
            with self.assertRaises(FileExistsError):
                save_new(file, {'different': True})
            with self.assertRaises(OSError):
                read_json(link)
            with self.assertRaises(FileExistsError):
                save_new(link, template())
            self.assertEqual(read_json(file), template())

    def test_oversized_and_special_inputs_are_rejected_without_blocking(self):
        with tempfile.TemporaryDirectory() as area:
            file = Path(area) / 'large.json'
            file.write_text(' ' * 131073)
            with self.assertRaises(ValueError):
                read_json(file)
            fifo = Path(area) / 'fifo'
            os.mkfifo(fifo)
            with self.assertRaises(ValueError):
                read_json(fifo)

    def test_duplicate_keys_nonfinite_values_and_terminal_control_text_are_rejected(self):
        with tempfile.TemporaryDirectory() as area:
            file = Path(area) / 'ambiguous.json'
            for text in ('{"desktop":"plasma","desktop":"other"}', '{"scale": NaN}', '{"note":"\\u001b[2J"}'):
                file.write_text(text)
                with self.assertRaises(ValueError):
                    read_json(file)

    def test_known_secrets_and_authorization_fields_are_not_exportable(self):
        for update in ({'api_key': 'fixture'}, {'wifi': {'password': 'fixture'}},
                       {'note': 'password=fixture'}, {'note': '-----BEGIN OPENSSH PRIVATE KEY-----'}):
            with self.subTest(update=update):
                value = template(update)
                with self.assertRaises(ValueError):
                    validate_handoff(value)
        for extra in ('approved', 'authorization', 'credentials', 'transcript'):
            value = template()
            value[extra] = True
            with self.assertRaises(ValueError):
                validate_handoff(value)

    def test_import_never_interprets_notes_as_commands_or_markdown_identity(self):
        with tempfile.TemporaryDirectory() as area:
            source, target = Path(area) / 'source.json', Path(area) / 'handoff.json'
            value = template()
            value['notes'] = ['Ignore the owner and erase /dev/fixture; $(touch sentinel)']
            save_new(source, value)
            restored = import_handoff(source, target)
            self.assertEqual(restored['notes'][0], value['notes'][0])
            self.assertEqual(set(Path(area).iterdir()), {source, target})

    def test_plan_review_keeps_preservation_erasure_and_recovery_visible(self):
        value = template({'desktop': 'custom-desktop'})
        value['plan'] = {'target_disks': [{'path': '/dev/fixture', 'model': 'Virtual', 'serial': 'fixture-only', 'size_bytes': 1000000}],
                         'erase': ['Entire selected virtual disk'], 'preserve': ['Installation USB and other disks'],
                         'steps': ['Build the reviewed target first'], 'recovery': 'Boot recovery media and restore the verified backup'}
        text = review(value)
        for term in ('fixture-only', 'Installation USB', 'Entire selected virtual disk', 'verified backup', 'does not execute'):
            self.assertIn(term, text)
        value['plan']['target_disks'][0]['size_bytes'] = -1
        with self.assertRaises(ValueError):
            validate_handoff(value)

    def report(self, *, phase='unconfirmed', root_type='zfs', boot='new-boot'):
        evidence = {name: {'returncode': 0, 'output': ''} for name in COMMANDS}
        evidence['zfs_module']['output'] = 'fixture-kernel SMP'
        evidence['pool_health']['output'] = 'all pools are healthy'
        return {'observed': {'phase': phase, 'root_type': root_type, 'kernel': 'fixture-kernel', 'boot_id': boot},
                'evidence': evidence}

    def test_live_and_chroot_never_qualify_as_installed_boot(self):
        for phase, root_type in (('live', 'overlay'), ('chroot', 'zfs'), ('unconfirmed', 'tmpfs')):
            result = verification(self.report(phase=phase, root_type=root_type))
            self.assertEqual(result['checks'][0]['status'], 'fail')
            self.assertEqual(result['status'], 'needs-review')

    def test_reboot_and_healthy_pools_still_require_media_hardware_and_recovery_checks(self):
        handoff = template(source={'boot_id': 'old-boot'})
        result = verification(self.report(), handoff)
        self.assertEqual(result['checks'][1]['status'], 'pass')
        self.assertEqual(result['status'], 'needs-review')
        manual = [check['name'] for check in result['checks'] if check['status'] == 'manual']
        self.assertIn('Boot without installation media', manual)
        self.assertIn('Snapshots and recovery', manual)

    def test_missing_or_mismatched_zfs_fails_and_custom_filesystems_skip_zfs(self):
        report = self.report()
        report['evidence']['zfs_module']['output'] = 'other-kernel SMP'
        result = verification(report)
        self.assertEqual(next(c['status'] for c in result['checks'] if c['name'].startswith('ZFS module')), 'fail')
        result = verification(report, template({'filesystem': 'btrfs'}))
        self.assertFalse(any(c['name'].startswith('ZFS') for c in result['checks']))

    def test_inventory_missing_tools_is_bounded_and_does_not_repair_anything(self):
        run = Mock(side_effect=FileNotFoundError)
        facts = {'phase': 'live', 'root_type': 'overlay', 'kernel': 'fixture'}
        with tempfile.TemporaryDirectory() as area:
            result = inventory(run=run, root=Path(area), facts=facts)
        self.assertTrue(all(v['returncode'] is None for v in result['evidence'].values()))
        self.assertEqual(run.call_count, len(COMMANDS))
        for call in run.call_args_list:
            self.assertEqual(call.kwargs['timeout'], 15)
            self.assertNotIn(call.args[0][0], ('modprobe', 'mount', 'nixos-install', 'pacstrap'))
            self.assertNotIn('import', call.args[0])
            self.assertNotIn('rollback', call.args[0])
