import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(os.name == 'nt' and shutil.which('pwsh'), 'Windows PowerShell process integration')
class VerificationBudgetTests(unittest.TestCase):
    def run_fixture(self, body, budget):
        wrapper = Path(__file__).with_name('run-core-verification.ps1').resolve()
        with tempfile.TemporaryDirectory(prefix='coa-verification-budget-') as directory:
            root = Path(directory)
            (root / 'tools').mkdir()
            (root / 'tools' / 'verify_all.py').write_text(body, encoding='utf-8')
            return subprocess.run(
                ['pwsh', '-NoProfile', '-File', str(wrapper), '-CoreRoot', str(root),
                 '-MaximumSeconds', str(budget), '-Stages', 'build,unit'],
                capture_output=True, text=True, timeout=45)

    def test_completed_verification_preserves_exit_code(self):
        result = self.run_fixture('print("fixture completed", flush=True)\nraise SystemExit(7)\n', 30)
        self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
        self.assertIn('fixture completed', result.stdout)

    def test_budget_stops_verification_before_job_deadline(self):
        result = self.run_fixture('import time\nprint("fixture started", flush=True)\ntime.sleep(120)\n', 1)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('fixture started', result.stdout)
        self.assertIn('budget', result.stdout + result.stderr)

