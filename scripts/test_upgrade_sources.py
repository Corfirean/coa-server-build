import hashlib
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


if __name__ == '__main__':
    unittest.main()
