import base64
import importlib.util
import json
import unittest
from pathlib import Path
from subprocess import CompletedProcess, CalledProcessError
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('decision', Path(__file__).with_name('daily-decision.py'))
decision = importlib.util.module_from_spec(spec)
spec.loader.exec_module(decision)


class DecisionTests(unittest.TestCase):
    def test_only_a_real_404_allows_legacy_bootstrap(self):
        with patch.object(decision.subprocess, 'run', return_value=CompletedProcess([], 1, '{"status":"404"}')) as run:
            self.assertEqual(decision.previous_snapshot('manager'), '')
            self.assertEqual(run.call_count, 1)

    def test_network_and_permission_errors_block_the_decision(self):
        for output in ('', '{"status":"500"}', '{"status":"403"}'):
            with patch.object(decision.subprocess, 'run', return_value=CompletedProcess([], 1, output)):
                with self.assertRaises(RuntimeError):
                    decision.previous_snapshot('manager')

    def verify_case(self, error=None):
        response = json.dumps({'content': base64.b64encode(b'signed bytes').decode()})
        with patch.object(decision.subprocess, 'run', side_effect=[CompletedProcess([], 0, response), CompletedProcess([], 0)]), \
             patch.object(decision.Path, 'write_bytes'), \
             patch.object(decision.subprocess, 'check_output', return_value='{"snapshot":"verified"}', side_effect=error) as verify:
            result = decision.previous_snapshot('manager')
            self.assertIn('verify-channel', verify.call_args.args[0])
            return result

    def test_snapshot_comes_from_the_signature_verifier(self):
        self.assertEqual(self.verify_case(), 'verified')

    def test_a_bad_signature_cannot_suppress_compilation(self):
        with self.assertRaises(CalledProcessError):
            self.verify_case(CalledProcessError(1, 'verify-channel'))


if __name__ == '__main__':
    unittest.main()
