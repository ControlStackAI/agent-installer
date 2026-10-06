import copy
import hashlib
import io
import json
import sys
import tarfile
import tempfile
import unittest
import urllib.error
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from inputs import ROOT, kernel_from_db, validate
from build import download


class InputsTests(unittest.TestCase):
    def setUp(self):
        self.lock = json.loads((ROOT / 'inputs.lock.json').read_text())

    def test_current_inputs_are_supported(self):
        validate(self.lock)

    def test_new_unsupported_kernel_rejected(self):
        self.lock['arch']['kernel_package_version'] = '7.3.1.arch1-1'
        self.lock['arch']['kernel_release'] = '7.3.1-arch1-1'
        with self.assertRaisesRegex(ValueError, 'OpenZFS support'):
            validate(self.lock)

    def test_mismatched_module_rejected(self):
        self.lock['zfs']['packages'][0]['name'] = 'zfs-linux-2.4.4_7.2.7.arch1.1-1-x86_64.pkg.tar.zst'
        with self.assertRaisesRegex(ValueError, 'does not match'):
            validate(self.lock)

    def test_signer_rotation_requires_review(self):
        self.lock['zfs']['signer'] = 'A' * 40
        with self.assertRaisesRegex(ValueError, 'rotation'):
            validate(self.lock)

    def test_signature_mismatch_rejected(self):
        self.lock['zfs']['packages'][0]['signature']['name'] = 'wrong.sig'
        with self.assertRaisesRegex(ValueError, 'signature'):
            validate(self.lock)

    def test_path_traversal_rejected(self):
        self.lock['codex']['package']['name'] = '../../auth.json'
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            validate(self.lock)

    def test_unpinned_or_insecure_download_rejected(self):
        for field, value in [('sha256', ''), ('url', 'http://example.org/file')]:
            candidate = copy.deepcopy(self.lock)
            candidate['arch']['iso'][field] = value
            with self.assertRaisesRegex(ValueError, 'HTTPS and SHA256'):
                validate(candidate)

    def test_mutable_builder_rejected(self):
        self.lock['builder_image'] = 'archlinux:latest'
        with self.assertRaisesRegex(ValueError, 'pinned'):
            validate(self.lock)

    def test_corrupt_cache_is_not_silently_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            (cache / 'input.iso').write_bytes(b'corrupt')
            item = {'name': 'input.iso', 'sha256': '0' * 64, 'url': 'https://unused.invalid/'}
            with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                download(item, cache)

    def test_release_update_can_reuse_filename_without_old_bytes(self):
        old, new = b'old release', b'new release'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'old-lock').mkdir()
            (root / 'new-lock').mkdir()
            (root / 'old-lock' / 'codex.tar.gz').write_bytes(old)
            item = {'name': 'codex.tar.gz', 'url': 'https://example.org/codex.tar.gz', 'sha256': hashlib.sha256(new).hexdigest()}
            with patch('build.urllib.request.urlopen', return_value=io.BytesIO(new)):
                path = download(item, root / 'new-lock', root)
            self.assertEqual(path.read_bytes(), new)
            self.assertEqual((root / 'old-lock' / 'codex.tar.gz').read_bytes(), old)

    def test_unchanged_inputs_reused_across_locks_without_network(self):
        content = b'verified package'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'old-lock').mkdir()
            (root / 'new-lock').mkdir()
            (root / 'old-lock' / 'input.iso').write_bytes(content)
            item = {'name': 'input.iso', 'url': 'https://unused.invalid/', 'sha256': hashlib.sha256(content).hexdigest()}
            with patch('build.urllib.request.urlopen') as request:
                path = download(item, root / 'new-lock', root)
            self.assertEqual(path.read_bytes(), content)
            request.assert_not_called()

    def test_pruned_mirror_falls_back_to_frozen_archive(self):
        content = b'verified fixture package'
        item = copy.deepcopy(self.lock['arch']['linux'])
        item['sha256'] = hashlib.sha256(content).hexdigest()
        missing = urllib.error.HTTPError('https://geo.mirror.pkgbuild.com/', 404, 'pruned', {}, None)
        with tempfile.TemporaryDirectory() as directory, patch('build.urllib.request.urlopen', side_effect=[missing, io.BytesIO(content)]) as request:
            path = download(item, Path(directory))
            self.assertEqual(path.read_bytes(), content)
            self.assertEqual(request.call_args_list[-1].args[0].full_url, item['url'])

    def test_wrong_mirror_bytes_are_rejected_before_cache_reuse(self):
        item = copy.deepcopy(self.lock['arch']['linux'])
        with tempfile.TemporaryDirectory() as directory, patch('build.urllib.request.urlopen', return_value=io.BytesIO(b'wrong bytes')) as request:
            with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                download(item, Path(directory))
            self.assertFalse((Path(directory) / item['name']).exists())
            self.assertEqual(request.call_count, 1)

    def test_kernel_database_ignores_headers(self):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w:gz') as archive:
            for name in ['linux-headers-7.2.8.arch1-2', 'linux-7.2.8.arch1-2']:
                content = b'%NAME%\nlinux\n\n%VERSION%\n7.2.8.arch1-2\n'
                member = tarfile.TarInfo(name + '/desc')
                member.size = len(content)
                archive.addfile(member, io.BytesIO(content))
        self.assertEqual(kernel_from_db(stream.getvalue())['VERSION'], '7.2.8.arch1-2')


if __name__ == '__main__':
    unittest.main()
