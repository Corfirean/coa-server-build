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
    def test_manual_stable_cannot_make_daily_candidate_a_downgrade(self):
        stable = {'version': '0.261012.800008'}
        self.assertEqual(decision.next_version('261012', 44, stable, []), '0.261012.800009')

    def test_existing_draft_and_published_tags_are_not_reused(self):
        tags = ['server-0.261012.800009', 'base', 'server-0.261011.900000']
        self.assertEqual(decision.next_version('261012', 44, {'version': '0.261012.800008'}, tags), '0.261012.800010')

    def test_next_day_retains_the_normal_daily_namespace(self):
        self.assertEqual(decision.next_version('261013', 44, {'version': '0.261012.800008'}, []), '0.261013.100044')

    def test_clock_skew_cannot_lower_the_signed_stable_version(self):
        self.assertEqual(decision.next_version('261011', 44, {'version': '0.261012.800008'}, []), '0.261012.800009')

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
