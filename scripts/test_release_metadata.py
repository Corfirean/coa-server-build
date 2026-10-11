import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


metadata = load('release-metadata')
daily = load('daily-release')
promote = load('promote-channel')


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.lock = {'schema': 1, 'components': {name: {'sha': 'a' * 40} for name in ('core', 'bots', 'scaling', 'squid', 'races')}}
        self.lock['snapshot'] = daily.snapshot(self.lock['components'])
        self.manifest = {'version': '0.261012.1', 'core': {'commit': 'a' * 40}, 'bots': {'commit': 'a' * 40},
                         'archive': {'parts': [{'sha256': 'b' * 64}]}, 'minManagerVersion': '0.6.13',
                         'compatibility': {'platform': 'windows-x86_64', 'moduleCommits': {
                             name: 'a' * 40 for name in ('bots', 'scaling', 'squid', 'races')}}}
        self.report = {'schema': 1, 'version': self.manifest['version'], 'snapshot': self.lock['snapshot'],
                       'archive': self.manifest['archive'], 'platforms': {'windows-x86_64': {
                           gate: {'result': 'passed', 'evidence': 'https://github.com/owner/repo/actions/runs/1'}
                           for gate in metadata.WINDOWS_GATES}}}
        self.matrix = {'schema': 1, 'version': self.manifest['version'], 'snapshot': self.lock['snapshot'],
                       'minManagerVersion': '0.6.13', 'platforms': {'windows-x86_64': self.manifest['compatibility']}}

    def write(self):
        for name, value in zip(metadata.FILES, (self.lock, self.report, self.matrix)):
            (self.folder / name).write_text(json.dumps(value))
        self.manifest['releaseMetadata'] = {name: metadata.digest(self.folder / name) for name in metadata.FILES}
        (self.folder / 'manifest.json').write_text(json.dumps(self.manifest))

    def test_verified_metadata_matches_candidate(self):
        self.write()
        metadata.validate(self.folder)

    def test_missing_or_modified_metadata_blocks_publication(self):
        self.write()
        (self.folder / 'qualification.json').write_text('{}')
        with self.assertRaisesRegex(RuntimeError, 'changed release metadata'):
            metadata.validate(self.folder)

    def test_other_archive_or_snapshot_is_rejected_even_with_updated_hash(self):
        for field in ('archive', 'snapshot'):
            original = self.report[field]
            self.report[field] = {} if field == 'archive' else 'different'
            self.write()
            with self.assertRaises(RuntimeError):
                metadata.validate(self.folder)
            self.report[field] = original

    def test_skipped_upgrade_blocks_candidate(self):
        self.report['platforms']['windows-x86_64']['upgrade-stable-1']['result'] = 'not-run'
        self.write()
        with self.assertRaisesRegex(RuntimeError, 'upgrade-stable-1'):
            metadata.validate(self.folder)

    def test_partial_candidate_still_cannot_be_promoted(self):
        self.write()
        metadata.validate(self.folder)
        with self.assertRaises(RuntimeError):
            promote.validate_report(self.report, self.lock['snapshot'], self.manifest['version'])

    def test_failed_or_ambiguous_steps_never_become_passed(self):
        for jobs in ([], [{'html_url': 'url', 'steps': [{'name': 'compile', 'conclusion': 'failure', 'number': 1}]}]):
            with patch.object(metadata, 'api', return_value={'jobs': jobs}):
                with self.assertRaises(RuntimeError):
                    metadata.evidence_steps('owner/repo', '1', {'build': 'compile'})

    def test_linux_config_smoke_does_not_claim_database_startup(self):
        self.lock['upgradeSources'] = []
        self.manifest['compatibility']['platform'] = 'linux-x86_64'
        (self.folder / 'manifest.json').write_text(json.dumps(self.manifest))
        lock_path = self.folder / 'input-lock.json'
        lock_path.write_text(json.dumps(self.lock))
        def steps(repo, run, names):
            return {name: {'result': 'passed', 'evidence': 'https://github.com/owner/repo/actions/runs/1'} for name in names}
        with patch.dict('os.environ', {'GITHUB_REPOSITORY': 'owner/repo', 'GITHUB_RUN_ID': '1'}), patch.object(metadata, 'evidence_steps', side_effect=steps):
            metadata.collect(self.folder, lock_path, 'linux-x86_64', self.folder, '')
        report = metadata.read(self.folder / 'qualification.json')
        self.assertEqual(report['platforms']['linux-x86_64']['world-startup']['result'], 'not-run')
        self.assertEqual(report['platforms']['linux-x86_64']['auth-startup']['result'], 'not-run')
        self.assertEqual(report['platforms']['linux-x86_64']['module-config-layout']['result'], 'passed')


class SnapshotTests(unittest.TestCase):
    def test_refs_do_not_change_source_identity_but_revision_does(self):
        components = {'core': {'sha': 'a' * 40, 'ref': 'main'}}
        first = daily.snapshot(components)
        components['core']['ref'] = 'a' * 40
        self.assertEqual(first, daily.snapshot(components))
        components['core']['sha'] = 'b' * 40
        self.assertNotEqual(first, daily.snapshot(components))


if __name__ == '__main__':
    unittest.main()
