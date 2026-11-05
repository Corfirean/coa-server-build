import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('lease', Path(__file__).with_name('daily-lease.py'))
lease = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lease)


class LeaseTests(unittest.TestCase):
    def holder(self, owner=1):
        return {'message': json.dumps({'schema': 1, 'repository': 'owner/repo', 'runId': owner}),
                'tree': {'sha': 'tree'}}

    def test_bootstrap_creates_one_ref(self):
        with patch.object(lease, 'api', side_effect=[lease.ApiError(404), {'tree': {'sha': 'tree'}}, {'sha': 'new'}, {}]) as api:
            self.assertTrue(lease.acquire('owner/repo', 2, 'source'))
            self.assertEqual(api.call_args.args[2]['ref'], 'refs/' + lease.REF)

    def test_active_owner_skips_without_mutation(self):
        with patch.object(lease, 'api', side_effect=[{'object': {'sha': 'old'}}, self.holder(), {'status': 'in_progress'}]) as api:
            self.assertFalse(lease.acquire('owner/repo', 2, 'source'))
            self.assertEqual(api.call_count, 3)

    def test_completed_owner_uses_compare_and_swap(self):
        with patch.object(lease, 'api', side_effect=[{'object': {'sha': 'old'}}, self.holder(), {'status': 'completed'}, {'sha': 'new'}, {}]) as api:
            self.assertTrue(lease.acquire('owner/repo', 2, 'source'))
            self.assertEqual(api.call_args.args[2], {'sha': 'new', 'force': False})
            self.assertEqual(api.call_args_list[3].args[2]['parents'], ['old'])

    def test_concurrent_bootstrap_loser_skips(self):
        with patch.object(lease, 'api', side_effect=[lease.ApiError(404), {'tree': {'sha': 'tree'}}, {'sha': 'new'}, lease.ApiError(422), {'object': {'sha': 'winner'}}]):
            self.assertFalse(lease.acquire('owner/repo', 2, 'source'))

    def test_concurrent_takeover_loser_skips(self):
        with patch.object(lease, 'api', side_effect=[{'object': {'sha': 'old'}}, self.holder(), {'status': 'completed'}, {'sha': 'new'}, lease.ApiError(422), {'object': {'sha': 'winner'}}]):
            self.assertFalse(lease.acquire('owner/repo', 2, 'source'))

    def test_network_failure_never_means_no_owner(self):
        with patch.object(lease, 'api', side_effect=lease.ApiError(500)):
            with self.assertRaises(lease.ApiError):
                lease.acquire('owner/repo', 2, 'source')

    def test_retry_by_the_same_run_is_idempotent(self):
        with patch.object(lease, 'api', side_effect=[{'object': {'sha': 'old'}}, self.holder(2)]):
            self.assertTrue(lease.acquire('owner/repo', 2, 'source'))


if __name__ == '__main__':
    unittest.main()
