import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from prime_core_cache import prime, REPOSITORY


class CoreCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cache = self.root / 'cache'
        self.cache.mkdir()
        self.run_git(self.cache, 'init')
        self.run_git(self.cache, 'config', 'user.email', 'fixture@example.invalid')
        self.run_git(self.cache, 'config', 'user.name', 'Fixture')
        (self.cache / 'source').write_text('frozen source')
        (self.cache / '.gitignore').write_text('ignored\n')
        self.run_git(self.cache, 'add', '.')
        self.run_git(self.cache, 'commit', '-m', 'frozen')
        self.sha = self.run_git(self.cache, 'rev-parse', 'HEAD')
        self.workspace = self.root / 'workspace'
        self.workspace.mkdir()

    def run_git(self, root, *args):
        return subprocess.check_output(['git', '-C', str(root), *args], encoding='utf-8', stderr=subprocess.DEVNULL).strip()

    def test_exact_complete_checkout_can_be_used_without_network(self):
        self.assertTrue(prime(self.cache, self.workspace, self.sha))
        self.assertEqual(self.run_git(self.workspace / '_core', 'rev-parse', 'HEAD'), self.sha)
        self.assertTrue(prime(self.cache, self.workspace, self.sha))

    def test_mutable_missing_and_shallow_inputs_are_rejected(self):
        with self.assertRaises(RuntimeError):
            prime(self.cache, self.workspace, 'main')
        with self.assertRaises(RuntimeError):
            prime(self.cache, self.workspace, 'f' * 40)
        (self.cache / '.git/shallow').write_text(self.sha + '\n')
        with self.assertRaisesRegex(RuntimeError, 'shallow'):
            prime(self.cache, self.workspace, self.sha)
        self.assertFalse((self.workspace / '_core').exists())

    def test_changed_ignored_and_wrong_repository_checkouts_are_rejected(self):
        prime(self.cache, self.workspace, self.sha)
        target = self.workspace / '_core'
        (target / 'source').write_text('changed')
        with self.assertRaises(RuntimeError): prime(self.cache, self.workspace, self.sha)
        self.run_git(target, 'checkout', '--', 'source')
        (target / 'ignored').write_text('unexpected')
        with self.assertRaises(RuntimeError): prime(self.cache, self.workspace, self.sha)
        (target / 'ignored').unlink()
        self.run_git(target, 'remote', 'set-url', 'origin', 'https://example.invalid/other')
        with self.assertRaises(RuntimeError): prime(self.cache, self.workspace, self.sha)

    def test_absent_cache_uses_ordinary_checkout(self):
        self.assertFalse(prime(None, self.workspace, self.sha))
        self.assertFalse((self.workspace / '_core').exists())
