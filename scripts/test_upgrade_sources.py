import hashlib
import io
import subprocess
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('sources', Path(__file__).with_name('upgrade-sources.py'))
sources = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sources)


class SourceTests(unittest.TestCase):
    def lock(self):
        return {'upgradeSources': [{'role': role, 'assets': {name: {
            'url': 'https://github.com/Corfirean/coa-server-build/releases/download/stable/' + name,
            'sha256': hashlib.sha256(b'original').hexdigest()}
            for name in ('manifest.json', 'manifest.json.sig')}} for role in sources.ROLES]}

    def test_overwritten_legacy_asset_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(sources, 'fetch', return_value=b'changed'):
            with self.assertRaises(RuntimeError):
                sources.download(self.lock(), Path(directory))
            self.assertFalse((Path(directory) / 'base/manifest.json').exists())

    def test_invalid_roles_are_rejected_before_network_or_writes(self):
        lock = self.lock()
        lock['upgradeSources'][0]['role'] = '../outside'
        with tempfile.TemporaryDirectory() as directory, patch.object(sources, 'fetch') as fetch:
            with self.assertRaises(RuntimeError):
                sources.download(lock, Path(directory))
            fetch.assert_not_called()

    def test_network_failure_is_not_a_legacy_fallback(self):
        result = type('Result', (), {'returncode': 1, 'stdout': '{"status":"500"}'})()
        with patch.object(sources.subprocess, 'run', return_value=result):
            with self.assertRaises(RuntimeError):
                sources.channel()

    def test_archive_hash_and_size_are_required_before_installing_the_download(self):
        url = 'https://github.com/Corfirean/coa-server-build/releases/download/stable/server.tar.zst.001'
        for raw in (b'short', b'wrong!', b'too-long'):
            with tempfile.TemporaryDirectory() as directory, patch.object(sources.urllib.request, 'urlopen', return_value=io.BytesIO(raw)):
                target = Path(directory) / 'server.tar.zst.001'
                with self.assertRaises(RuntimeError):
                    sources.download_part(url, target, 6, hashlib.sha256(b'correct').hexdigest())
                self.assertFalse(target.exists())
                self.assertFalse(target.with_name(target.name + '.partial').exists())

    def test_valid_archive_is_reused_only_after_verification(self):
        url = 'https://github.com/Corfirean/coa-server-build/releases/download/stable/part'
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'part'
            with patch.object(sources.urllib.request, 'urlopen', return_value=io.BytesIO(b'good')):
                sources.download_part(url, target, 4, hashlib.sha256(b'good').hexdigest())
            with patch.object(sources.urllib.request, 'urlopen') as fetch:
                sources.download_part(url, target, 4, hashlib.sha256(b'good').hexdigest())
                fetch.assert_not_called()
            target.write_bytes(b'bad!')
            with self.assertRaises(RuntimeError):
                sources.download_part(url, target, 4, hashlib.sha256(b'good').hexdigest())

    def test_an_existing_partial_download_is_not_deleted(self):
        url = 'https://github.com/Corfirean/coa-server-build/releases/download/stable/part'
        with tempfile.TemporaryDirectory() as directory, patch.object(sources.urllib.request, 'urlopen', return_value=io.BytesIO(b'good')):
            target = Path(directory) / 'part'
            partial = Path(directory) / 'part.partial'
            partial.write_bytes(b'other download')
            with self.assertRaises(FileExistsError):
                sources.download_part(url, target, 4, hashlib.sha256(b'good').hexdigest())
            self.assertEqual(partial.read_bytes(), b'other download')

    def test_invalid_signature_stops_before_archive_download(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(sources, 'download'), \
             patch.object(sources.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'verify-manifest')), \
             patch.object(sources, 'download_part') as fetch:
            with self.assertRaises(subprocess.CalledProcessError):
                sources.download_packages(self.lock(), Path(directory), Path('tool'))
            fetch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
