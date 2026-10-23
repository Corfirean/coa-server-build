import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('identity', Path(__file__).with_name('qualification-identity.py'))
identity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(identity)


class IdentityTests(unittest.TestCase):
    def test_only_successful_report_for_unchanged_candidate_is_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            manifest = folder / 'manifest.json'
            manifest.write_text('{"version":"0.261016.1"}')
            expected = hashlib.sha256(manifest.read_bytes()).hexdigest()
            report = folder / 'report.json'
            for data in ({'result': 'failed', 'toVersion': '0.261016.1'},
                         {'result': 'passed', 'toVersion': 'other'}):
                report.write_text(json.dumps(data))
                with self.assertRaises(RuntimeError):
                    identity.bind(folder, report, expected)
            report.write_text('{"result":"passed","toVersion":"0.261016.1"}')
            identity.bind(folder, report, expected)
            self.assertEqual(json.loads(report.read_text())['candidateManifestSha256'], expected)
            manifest.write_text('{"version":"0.261016.1", "changed":true}')
            with self.assertRaisesRegex(RuntimeError, 'changed during'):
                identity.bind(folder, report, expected)
