import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('direct', Path(__file__).with_name('direct-upgrade-matrix.py'))
direct = importlib.util.module_from_spec(spec)
spec.loader.exec_module(direct)


class DirectUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sources = [{'role': role, 'version': version, 'manifestSha256': 'a' * 64} for role, version in
                        [('base', '0.2.0'), ('stable-1', '0.261015.58'), ('stable-2', '0.261013.54'), ('stable-3', '0.261005.0')]]

    def freeze(self, version='', prepared=None):
        with patch.object(direct.upgrades, 'resolve', return_value=self.sources), \
             patch.object(direct.subprocess, 'check_output', return_value=json.dumps({'sha': 'b' * 40})), \
             patch.dict(os.environ, {'GITHUB_OUTPUT': str(self.root / 'outputs')}):
            return direct.freeze('master', version, self.root / 'lock.json', prepared)

    def prepared(self, manager='b' * 40):
        folder = self.root / 'prepared'
        folder.mkdir(exist_ok=True)
        (folder / 'manifest.json').write_text(json.dumps({'kind': 'update', 'version': '0.261024.1'}))
        (folder / 'release-lock.json').write_text(json.dumps({'components': {'manager': {'sha': manager}}}))
        return folder

    def test_unpublished_prepared_target_freezes_every_source_and_self_update(self):
        folder = self.prepared()
        lock = self.freeze(prepared=folder)
        self.assertEqual(lock['targetVersion'], '0.261024.1')
        self.assertEqual(lock['targetRole'], 'stable-4')
        self.assertEqual(len(lock['testedRoles']), 5)
        self.assertEqual(lock['upgradeSources'][-1]['manifestSha256'],
                         direct.hashlib.sha256((folder / 'manifest.json').read_bytes()).hexdigest())

    def test_prepared_target_rejects_different_manager_or_requested_version(self):
        with self.assertRaisesRegex(RuntimeError, 'Manager differs'):
            self.freeze(prepared=self.prepared('c' * 40))
        with self.assertRaisesRegex(RuntimeError, 'version differs'):
            self.freeze('0.261024.99', self.prepared())

    def test_prepared_target_cannot_replace_different_published_bytes(self):
        folder = self.prepared()
        (folder / 'manifest.json').write_text(json.dumps({'kind': 'update', 'version': self.sources[1]['version']}))
        with self.assertRaisesRegex(RuntimeError, 'differs from the published'):
            self.freeze(prepared=folder)

    def test_latest_and_older_target_freeze_exact_manager_and_eligible_sources(self):
        lock = self.freeze()
        self.assertEqual(lock['manager'], 'b' * 40)
        self.assertEqual(len(lock['testedRoles']), 4)
        older = self.freeze('0.261013.54')
        self.assertEqual(older['testedRoles'], ['base', 'stable-2', 'stable-3'])
        self.assertEqual(older['targetRole'], 'stable-2')

    def test_unknown_target_is_rejected(self):
        for version in ('0.2.0', '0.261016.99'):
            with self.assertRaises(RuntimeError):
                self.freeze(version)

    def test_missing_or_mismatched_source_report_never_counts_as_passed(self):
        lock = self.freeze()
        for source in self.sources:
            (self.root / (source['role'] + '.json')).write_text(json.dumps({
                'result': 'passed', 'fromVersion': source['version'], 'toVersion': lock['targetVersion'],
                'fromManifestSha256': source['manifestSha256']}))
        self.assertEqual(direct.validate(lock, self.root), 4)
        path = self.root / 'stable-3.json'
        original = json.loads(path.read_text())
        for field, value in [('result', 'not-run'), ('fromVersion', 'wrong'),
                             ('toVersion', 'wrong'), ('fromManifestSha256', 'c' * 64)]:
            path.write_text(json.dumps(dict(original, **{field: value})))
            with self.assertRaises(RuntimeError):
                direct.validate(lock, self.root)
        path.unlink()
        with self.assertRaises(FileNotFoundError):
            direct.validate(lock, self.root)


if __name__ == '__main__':
    unittest.main()
