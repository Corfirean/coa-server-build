import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('cache', Path(__file__).with_name('cache-release-assets.py'))
cache = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cache)


class AssetCacheTests(unittest.TestCase):
    def test_only_matching_bytes_are_reused(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'part'
            path.write_bytes(b'good')
            asset = {'size': 4, 'digest': 'sha256:' + hashlib.sha256(b'good').hexdigest()}
            self.assertTrue(cache.matches(path, asset))
            path.write_bytes(b'evil')
            self.assertFalse(cache.matches(path, asset))
            path.write_bytes(b'partial')
            self.assertFalse(cache.matches(path, asset))

    def test_missing_checksum_does_not_trust_same_sized_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'part'
            path.write_bytes(b'good')
            self.assertFalse(cache.matches(path, {'size': 4, 'digest': None}))


if __name__ == '__main__':
    unittest.main()
