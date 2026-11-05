import importlib.util
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('health', Path(__file__).with_name('daily-health.py'))
health = importlib.util.module_from_spec(spec)
spec.loader.exec_module(health)


class HealthTests(unittest.TestCase):
    def exercise(self, step, issues=()):
        now = datetime.now(timezone.utc).isoformat()
        runs = {'workflow_runs': [{'id': 7, 'event': 'schedule'}]}
        jobs = {'jobs': [{'name': 'resolve', 'conclusion': 'success', 'completed_at': now,
                         'steps': [{'name': 'Resolve and check daily snapshot', 'conclusion': step}]}]}
        with tempfile.TemporaryDirectory() as directory, patch.dict(health.os.environ, {'GITHUB_REPOSITORY': 'owner/repo', 'RUNNER_TEMP': directory}), patch.object(health, 'api', side_effect=[runs, jobs, list(issues)]), patch.object(health.subprocess, 'run') as commands:
            health.main()
            return [call.args[0] for call in commands.call_args_list]

    def test_skipped_reconciliation_is_not_success(self):
        commands = self.exercise('skipped')
        self.assertEqual(commands[-1][2], 'create')

    def test_healthy_reconciliation_closes_existing_diagnostic(self):
        commands = self.exercise('success', [{'title': 'Daily reconciliation overdue', 'number': 9}])
        self.assertEqual(commands, [['gh', 'issue', 'close', '9', '--repo', 'owner/repo']])

    def test_failure_updates_existing_issue(self):
        commands = self.exercise('failure', [{'title': 'Daily reconciliation overdue', 'number': 9}])
        self.assertEqual(commands[-1][2:4], ['edit', '9'])


if __name__ == '__main__':
    unittest.main()
