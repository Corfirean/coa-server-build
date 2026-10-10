import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('compatibility', Path(__file__).with_name('release-compatibility.py'))
compatibility = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compatibility)


class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.lock = {'components': {name: {'sha': str(index) * 40} for index, name in enumerate(('core', 'bots', 'scaling', 'squid', 'races'), 1)}}
        self.lock['components']['races']['ref'] = 'coa-custom-1.5.1'
        self.manifest = {'core': {'commit': '1' * 40}, 'bots': {'commit': '2' * 40}}
        self.sources = [{'kind': kind, 'version': version, '_signedManifestSha256': 'a' * 64} for kind, version in
                        [('base', '0.2.0'), ('update', '0.261010.32'), ('update', '0.261006.1')]]
        for source in self.sources[1:]:
            source['files'] = [{'path': 'Scripts/database-schema.json', 'sha256': 'b' * 64}]

    def test_matrix_binds_all_revisions_and_upgrade_sources(self):
        result = compatibility.matrix(self.manifest, self.lock, self.sources, 'windows-x86_64')
        self.assertEqual(result['moduleCommits']['squid'], '4' * 40)
        self.assertEqual(result['clientPatchVersion'], '1.5.1')
        self.assertEqual(result['sourceVersions'], ['0.2.0', '0.261010.32', '0.261006.1'])
        self.assertIsNone(result['sourceDatabases']['0.2.0']['schemaSha256'])
        self.assertEqual(result['sourceDatabases']['0.261010.32']['schemaSha256'], 'b' * 64)

    def test_missing_update_schema_contract_is_rejected(self):
        self.sources[1]['files'] = []
        with self.assertRaises(RuntimeError):
            compatibility.matrix(self.manifest, self.lock, self.sources, 'windows-x86_64')

    def test_different_packaged_revision_is_rejected(self):
        self.manifest['bots']['commit'] = 'a' * 40
        with self.assertRaises(RuntimeError):
            compatibility.matrix(self.manifest, self.lock, self.sources, 'windows-x86_64')

    def test_duplicate_or_missing_source_is_rejected(self):
        for sources in (self.sources[:2], [self.sources[0], self.sources[1], self.sources[1]]):
            with self.assertRaises(RuntimeError):
                compatibility.matrix(self.manifest, self.lock, sources, 'linux-x86_64')

    def test_changed_signed_source_never_changes_candidate_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / 'candidate'
            candidate.mkdir()
            original = json.dumps(self.manifest)
            (candidate / 'manifest.json').write_text(original)
            source = root / 'sources/base'
            source.mkdir(parents=True)
            (source / 'manifest.json').write_text('changed')
            lock = copy.deepcopy(self.lock)
            lock['upgradeSources'] = [{'role': role, 'manifestSha256': '0' * 64} for role in ('base', 'stable-1', 'stable-2')]
            lock_path = root / 'lock.json'
            lock_path.write_text(json.dumps(lock))
            with patch.object(compatibility.subprocess, 'run') as verify:
                with self.assertRaises(RuntimeError):
                    compatibility.apply(candidate, lock_path, root / 'sources', 'windows-x86_64', 'tool')
                verify.assert_not_called()
            self.assertEqual((candidate / 'manifest.json').read_text(), original)


if __name__ == '__main__':
    unittest.main()
