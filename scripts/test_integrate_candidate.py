import contextlib
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('integration', Path(__file__).with_name('integrate-candidate.py'))
integration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(integration)


class IntegrationDiagnosticsTests(unittest.TestCase):
    def test_real_merge_conflict_is_visible_and_preserved(self):
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                repo = Path('_integration')
                repo.mkdir()
                def git(*args):
                    subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True, text=True)
                git('init', '-q', '--initial-branch=main')
                git('config', 'user.name', 'Integration test')
                git('config', 'user.email', 'integration@example.invalid')
                file = repo / 'achievement.cpp'
                file.write_text('base\n')
                git('add', '.')
                git('commit', '-qm', 'base')
                git('checkout', '-qb', 'incoming')
                file.write_text('upstream\n')
                git('commit', '-qam', 'upstream')
                git('checkout', '-q', 'main')
                file.write_text('local\n')
                git('commit', '-qam', 'local')
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    with self.assertRaises(subprocess.CalledProcessError) as failure:
                        integration.git('merge', '--no-edit', 'incoming')
                integration.record_failure(failure.exception)
                diagnostic = json.loads(Path('integration-diagnostics.json').read_text())
                self.assertIn('CONFLICT', output.getvalue())
                self.assertIn('CONFLICT', diagnostic['output'])
                self.assertEqual(diagnostic['conflicts'], ['achievement.cpp'])
                self.assertIn('UU achievement.cpp', diagnostic['status'])
                self.assertFalse(Path('release-lock.json').exists())
            finally:
                os.chdir(previous)


if __name__ == '__main__':
    unittest.main()
