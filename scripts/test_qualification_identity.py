import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from migration_evidence import inventory_digest

spec = importlib.util.spec_from_file_location('identity', Path(__file__).with_name('qualification-identity.py'))
identity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(identity)


class IdentityTests(unittest.TestCase):
    def test_only_successful_report_for_unchanged_candidate_is_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            manifest = folder / 'manifest.json'
            manifest.write_text('{"version":"0.261016.1","migrations":[]}')
            expected = hashlib.sha256(manifest.read_bytes()).hexdigest()
            report = folder / 'report.json'
            for data in ({'result': 'failed', 'toVersion': '0.261016.1'},
                         {'result': 'passed', 'toVersion': 'other'}):
                report.write_text(json.dumps(data))
                with self.assertRaises(RuntimeError):
                    identity.bind(folder, report, expected)
            report.write_text(json.dumps({'result': 'passed', 'toVersion': '0.261016.1',
                'toManifestSha256': expected, 'checks': ['migration-ledger', 'legacy-race-start-data'],
                'migrationInventorySha256': inventory_digest({'migrations': []}),
                'migrations': {'CoA': {'total': 0, 'applied': 0, 'checksumVerified': 0, 'legacyUnknown': 0}}}))
            evidence = json.loads(report.read_text())
            evidence['toManifestSha256'] = '0' * 64
            report.write_text(json.dumps(evidence))
            with self.assertRaisesRegex(RuntimeError, 'different candidate'):
                identity.bind(folder, report, expected)
            evidence['toManifestSha256'] = expected
            report.write_text(json.dumps(evidence))
            identity.bind(folder, report, expected)
            self.assertEqual(json.loads(report.read_text())['candidateManifestSha256'], expected)
            manifest.write_text('{"version":"0.261016.1", "changed":true}')
            with self.assertRaisesRegex(RuntimeError, 'changed during'):
                identity.bind(folder, report, expected)
