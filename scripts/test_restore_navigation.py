import hashlib
import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

spec = importlib.util.spec_from_file_location('restore', Path(__file__).with_name('restore-navigation.py'))
restore = importlib.util.module_from_spec(spec)
spec.loader.exec_module(restore)


class NavigationTests(unittest.TestCase):
    def fixture(self, root, name='maps/0002828.map', payload=b'terrain', expected=None):
        digest = hashlib.sha256(payload if expected is None else expected).hexdigest()
        manifest = {'core': 'a' * 40, 'files': {name: digest}}
        raw = json.dumps(manifest).encode()
        downloads = root / 'download'
        downloads.mkdir()
        part = downloads / 'navigation.zip.001'
        with zipfile.ZipFile(part, 'w') as z:
            z.writestr('navigation-manifest.json', raw)
            z.writestr('Data/' + name, payload)
        archive_hash = hashlib.sha256(part.read_bytes()).hexdigest()
        component = {'sha': 'a' * 40, 'manifestSha256': hashlib.sha256(raw).hexdigest(),
                     'archiveSha256': archive_hash,
                     'assets': [{'name': part.name, 'size': part.stat().st_size, 'sha256': archive_hash,
                                 'url': 'https://github.com/Corfirean/coa-server-build/releases/download/nav/' + part.name}]}
        return component, downloads

    def test_restores_exact_payload_and_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            component, downloads = self.fixture(root)
            restore.restore(component, root / 'tree', downloads)
            self.assertEqual((root / 'tree/Data/maps/0002828.map').read_bytes(), b'terrain')
            self.assertEqual(hashlib.sha256((root / 'tree/Scripts/navigation-manifest.json').read_bytes()).hexdigest(), component['manifestSha256'])
            self.assertFalse((downloads / 'navigation.zip.001').exists())

    def test_corrupt_payload_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            component, downloads = self.fixture(root, expected=b'correct terrain')
            with self.assertRaisesRegex(RuntimeError, 'payload checksum'):
                restore.restore(component, root / 'tree', downloads)

    def test_path_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            component, downloads = self.fixture(root, name='maps/../../outside.txt')
            with self.assertRaisesRegex(RuntimeError, 'Unsafe navigation path'):
                restore.restore(component, root / 'tree', downloads)
            self.assertFalse((root / 'outside.txt').exists())

    def test_wrong_generator_revision_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            component, downloads = self.fixture(root)
            component['sha'] = 'b' * 40
            with self.assertRaisesRegex(RuntimeError, 'generator revision'):
                restore.restore(component, root / 'tree', downloads)


if __name__ == '__main__':
    unittest.main()
