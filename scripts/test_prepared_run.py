import copy
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('prepared', Path(__file__).with_name('validate-prepared-run.py'))
prepared = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepared)


class PreparedRunTests(unittest.TestCase):
    def setUp(self):
        self.repo = 'owner/build'
        self.run = {'repository': {'full_name': self.repo}, 'head_repository': {'full_name': self.repo},
                    'path': '.github/workflows/build.yml', 'event': 'workflow_dispatch', 'status': 'completed',
                    'conclusion': 'success', 'head_sha': 'a' * 40}
        self.lock = {'components': {'build': {'sha': 'a' * 40}}}

    def test_only_completed_manual_build_for_this_snapshot_is_publishable(self):
        prepared.validate(self.run, self.repo, self.lock)
        for field, value in (('conclusion', 'failure'), ('status', 'in_progress'), ('event', 'pull_request'),
                             ('path', '.github/workflows/verify-server.yml'), ('head_sha', 'b' * 40),
                             ('head_repository', {'full_name': 'fork/build'})):
            with self.subTest(field=field):
                run = copy.deepcopy(self.run)
                run[field] = value
                with self.assertRaises(RuntimeError):
                    prepared.validate(run, self.repo, self.lock)
