import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(sys.platform == 'win32', 'Persistent checkout preflight runs in Windows PowerShell')
class CachedCheckoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'runner' / 'repo'
        self.root.mkdir(parents=True)
        self.git('init')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'user.name', 'Fixture')
        self.git('remote', 'add', 'origin', 'https://github.com/Corfirean/azerothcore-wotlk-coa.git')
        (self.root / 'tracked').write_text('original')
        (self.root / '.gitignore').write_text('ignored.txt\n')
        self.git('add', '.')
        self.git('commit', '-m', 'fixture')
        self.sha = self.git('rev-parse', 'HEAD').strip()
        workflow = (Path(__file__).parents[1] / '.github/workflows/server-binaries.yml').read_text(encoding='utf-8')
        section = workflow.split('id: cached-core', 1)[1].split('        run: |\n', 1)[1].split('      - uses:', 1)[0]
        self.script = self.base / 'preflight.ps1'
        self.script.write_text('\n'.join(line[10:] for line in section.splitlines()) + '\n', encoding='utf-8-sig')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], encoding='utf-8', stderr=subprocess.DEVNULL)

    def preflight(self, expected=None, runner=None):
        output = self.base / 'output'
        output.unlink(missing_ok=True)
        env = dict(os.environ, CORE_REF=expected or self.sha, GITHUB_WORKSPACE=str(self.root),
                   RUNNER_WORKSPACE=str(runner or self.root.parent), GITHUB_OUTPUT=str(output))
        result = subprocess.run(['powershell', '-NoLogo', '-NoProfile', '-NonInteractive',
                                 '-ExecutionPolicy', 'Bypass', '-File', str(self.script)],
                                env=env, capture_output=True, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
        return result.returncode, output.read_text(encoding='utf-8-sig').strip() if output.exists() else ''

    def test_only_exact_clean_immutable_checkout_is_reused(self):
        self.assertEqual(self.preflight(), (0, 'reuse=true'))
        self.assertEqual(self.preflight('f' * 40), (0, 'reuse=false'))
        self.assertEqual(self.preflight('coa-bots'), (0, 'reuse=false'))

    def test_tracked_changes_and_ignored_leftovers_prevent_reuse(self):
        (self.root / 'tracked').write_text('changed')
        self.assertEqual(self.preflight(), (0, 'reuse=false'))
        self.git('checkout', '--', 'tracked')
        (self.root / 'ignored.txt').write_text('unsafe leftover')
        self.assertEqual(self.preflight(), (0, 'reuse=false'))

    def test_wrong_repository_and_workspace_escape_are_rejected(self):
        self.git('remote', 'set-url', 'origin', 'https://example.invalid/other.git')
        self.assertEqual(self.preflight(), (0, 'reuse=false'))
        self.assertNotEqual(self.preflight(runner=self.base / 'outside')[0], 0)
