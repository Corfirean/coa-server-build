import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('promote', Path(__file__).with_name('promote-channel.py'))
promote = importlib.util.module_from_spec(spec)
spec.loader.exec_module(promote)


class QualificationTests(unittest.TestCase):
    def report(self):
        return {'schema': 1, 'snapshot': 'candidate', 'version': 'version', 'platforms': {
            platform: {name: {'result': 'passed', 'evidence': 'https://github.com/owner/repo/actions/runs/7'}
                       for name in promote.GATES | {'build'}}
            for platform in ('windows-x86_64', 'linux-x86_64')}}

    def test_complete_report(self):
        promote.validate_report(self.report(), 'candidate', 'version')

    def test_unrun_local_acceptance_is_not_claimed_as_a_pass(self):
        report = self.report()
        report['platforms']['windows-x86_64']['login-relog'] = {'result': 'not-run'}
        promote.validate_report(report, 'candidate', 'version')
        self.assertEqual(report['platforms']['windows-x86_64']['login-relog']['result'], 'not-run')

    def test_windows_package_does_not_require_linux_acceptance(self):
        report = self.report()
        del report['platforms']['linux-x86_64']
        promote.validate_report(report, 'candidate', 'version')

    def test_windows_automated_gate_cannot_be_skipped(self):
        report = self.report()
        del report['platforms']['windows-x86_64']['fresh-install']
        with self.assertRaises(RuntimeError):
            promote.validate_report(report, 'candidate', 'version')

    def test_other_snapshot_blocks_promotion(self):
        with self.assertRaises(RuntimeError):
            promote.validate_report(self.report(), 'another', 'version')

    def test_owner_approval_preserves_unrun_results_and_requires_core_checks(self):
        report = self.report()
        del report['platforms']['linux-x86_64']
        report['platforms']['windows-x86_64']['login-relog'] = {'result': 'not-run'}
        promote.validate_report(report, 'candidate', 'version', owner_approved_snapshot='candidate')
        self.assertEqual(report['platforms']['windows-x86_64']['login-relog']['result'], 'not-run')
        del report['platforms']['windows-x86_64']['schema-contract']
        with self.assertRaises(RuntimeError):
            promote.validate_report(report, 'candidate', 'version', owner_approved_snapshot='candidate')

    def test_owner_approval_cannot_change_snapshot_or_ignore_a_failure(self):
        with self.assertRaises(RuntimeError):
            promote.validate_report(self.report(), 'candidate', 'version', owner_approved_snapshot='other')
        report = self.report()
        report['platforms']['windows-x86_64']['login-relog'] = {'result': 'failed'}
        with self.assertRaises(RuntimeError):
            promote.validate_report(report, 'candidate', 'version', owner_approved_snapshot='candidate')
        with self.assertRaises(RuntimeError):
            promote.validate_report(report, 'candidate', 'version')

    def test_upgrade_must_test_the_declared_source_version(self):
        report = self.report()
        sources = ['0.2.0', '0.261010.32', '0.261006.1']
        for checks in report['platforms'].values():
            for name, version in zip(('upgrade-base', 'upgrade-stable-1', 'upgrade-stable-2'), sources):
                checks[name]['fromVersion'] = version
        promote.validate_report(report, 'candidate', 'version', sources)
        report['platforms']['windows-x86_64']['upgrade-stable-2']['fromVersion'] = '0.0.0'
        with self.assertRaises(RuntimeError):
            promote.validate_report(report, 'candidate', 'version', sources)

    def test_same_version_with_different_manifest_cannot_qualify(self):
        report = self.report()
        sources = ['0.2.0', '0.261010.32', '0.261006.1']
        databases = {v: {'manifestSha256': 'a' * 64, 'schemaSha256': None} for v in sources}
        for checks in report['platforms'].values():
            for name, version in zip(('upgrade-base', 'upgrade-stable-1', 'upgrade-stable-2'), sources):
                checks[name].update(fromVersion=version, fromManifestSha256='a' * 64, fromSchemaSha256=None)
        promote.validate_report(report, 'candidate', 'version', sources, databases)
        report['platforms']['windows-x86_64']['upgrade-base']['fromManifestSha256'] = 'b' * 64
        with self.assertRaises(RuntimeError):
            promote.validate_report(report, 'candidate', 'version', sources, databases)

    def test_an_older_source_cannot_be_claimed_without_a_passing_upgrade(self):
        report = self.report()
        sources = ['0.2.0', '0.261013.54', '0.261006.1', '0.261005.0']
        names = ['upgrade-base', 'upgrade-stable-1', 'upgrade-stable-2', 'upgrade-stable-3']
        for checks in report['platforms'].values():
            for name, version in zip(names, sources):
                checks[name] = {'result': 'passed', 'evidence': 'https://github.com/o/r/actions/runs/7',
                                'fromVersion': version}
        promote.validate_report(report, 'candidate', 'version', sources)
        for result in ('not-run', 'failed'):
            report['platforms']['windows-x86_64']['upgrade-stable-3']['result'] = result
            with self.assertRaises(RuntimeError):
                promote.validate_report(report, 'candidate', 'version', sources,
                                        owner_approved_snapshot='candidate')


class AtomicPublicationTests(unittest.TestCase):
    def test_stale_parent_makes_no_writes(self):
        with patch.object(promote, 'api', return_value={'object': {'sha': 'b' * 40}}) as api:
            with self.assertRaises(RuntimeError):
                promote.publish('owner/repo', 'a' * 40, b'signed')
            self.assertEqual(api.call_count, 1)

    def test_concurrent_reference_change_is_never_forced(self):
        responses = [{'object': {'sha': 'a' * 40}}, {'tree': {'sha': 'tree'}},
                     {'sha': 'blob'}, {'sha': 'new-tree'}, {'sha': 'new-commit'},
                     subprocess.CalledProcessError(1, 'gh')]
        with patch.object(promote, 'api', side_effect=responses) as api:
            with self.assertRaises(subprocess.CalledProcessError):
                promote.publish('owner/repo', 'a' * 40, b'signed')
            self.assertEqual(api.call_args.args[2], {'sha': 'new-commit', 'force': False})
            self.assertEqual(api.call_args_list[-2].args[2]['parents'], ['a' * 40])


if __name__ == '__main__':
    unittest.main()
