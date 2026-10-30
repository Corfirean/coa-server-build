import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from migration_evidence import inventory_digest

spec = importlib.util.spec_from_file_location('installer', Path(__file__).with_name('installer-package.py'))
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def write_image(folder, release):
    image = dict(release, kind='base', files=[{'path': name} for name in (
        'Settings/database.bootstrap.json', 'Settings/install-source.json', 'Scripts/database-schema.json',
        'Core/worldserver.exe', 'Core/authserver.exe', 'mysql/data/world.ibd', 'Data/dbc/test.dbc', 'Runtime/python/python.exe')])
    (folder / 'base.tar.zst.001').write_bytes(b'full clean server image')
    image['archive'] = {'parts': [{'name': 'base.tar.zst.001', 'size': 23,
                                 'sha256': installer.digest(folder / 'base.tar.zst.001')}]}
    (folder / 'manifest.json').write_text(json.dumps(image))


def qualify(folder, report):
    (folder / 'manifest.json.sig').write_text('verified separately by the release tool')
    report.write_text(json.dumps({'schema': 1, 'result': 'passed', 'version': installer.read(folder / 'manifest.json')['version'],
                                 'manifestSha256': installer.digest(folder / 'manifest.json'),
                                 'checks': ['migration-ledger', 'legacy-race-start-data'], 'migrationInventorySha256': inventory_digest(installer.read(folder / 'manifest.json')),
                                 'migrations': {'CoA': {'total': 0, 'applied': 0, 'checksumVerified': 0, 'legacyUnknown': 0}}}))


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.image, self.release = root / 'image', root / 'release'
        self.image.mkdir()
        self.release.mkdir()
        self.manifest = {'kind': 'update', 'version': '0.261014.1', 'core': {'commit': 'a' * 40},
                         'bots': {'commit': 'b' * 40}, 'minManagerVersion': '0.6.16', 'compatibility': {}, 'migrations': []}
        (self.release / 'manifest.json').write_text(json.dumps(self.manifest))
        write_image(self.image, self.manifest)
        self.report = root / 'report.json'

    def test_qualified_full_image_is_bound_without_overwriting_update_assets(self):
        (self.release / 'base.tar.zst.001').write_bytes(b'update archive')
        installer.prepare(self.image, self.release)
        qualify(self.image, self.report)
        installer.embed(self.image, self.release, self.report)
        installer.validate(self.release)
        self.assertEqual((self.release / 'base.tar.zst.001').read_bytes(), b'update archive')
        self.assertEqual((self.release / 'install-base.tar.zst.001').read_bytes(), b'full clean server image')
        (self.release / 'install-manifest.json').write_text('{}')
        with self.assertRaises((RuntimeError, KeyError)):
            installer.validate(self.release)

    def test_missing_migration_evidence_blocks_embedding_before_any_asset_is_copied(self):
        installer.prepare(self.image, self.release)
        qualify(self.image, self.report)
        evidence = installer.read(self.report)
        evidence.pop('migrations')
        self.report.write_text(json.dumps(evidence))
        with self.assertRaisesRegex(RuntimeError, 'realm evidence'):
            installer.embed(self.image, self.release, self.report)
        self.assertFalse((self.release / 'install-manifest.json').exists())

    def test_old_or_incomplete_images_and_stale_qualification_are_rejected(self):
        image = installer.read(self.image / 'manifest.json')
        image['version'] = '0.2.0'
        with self.assertRaisesRegex(RuntimeError, 'version'):
            installer.validate_identity(image, self.manifest)
        image['version'] = self.manifest['version']
        image['files'] = []
        with self.assertRaisesRegex(RuntimeError, 'missing'):
            installer.validate_identity(image, self.manifest)
        installer.prepare(self.image, self.release)
        qualify(self.image, self.report)
        evidence = installer.read(self.report)
        evidence['manifestSha256'] = '0' * 64
        self.report.write_text(json.dumps(evidence))
        with self.assertRaisesRegex(RuntimeError, 'exact package'):
            installer.embed(self.image, self.release, self.report)


if __name__ == '__main__':
    unittest.main()
