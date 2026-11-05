import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
import sys
from check_fragment_changes import check

spec = importlib.util.spec_from_file_location('shared_parser', Path(__file__).parents[1] / 'changelog/changelog.py')
parser = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = parser
spec.loader.exec_module(parser)


class FragmentChangesTests(unittest.TestCase):
    def test_historical_invalid_bytes_are_preserved_but_new_and_changed_errors_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                return subprocess.check_output(['git', '-C', str(root), *args], encoding='utf-8', stderr=subprocess.DEVNULL).strip()
            git('init')
            git('config', 'user.email', 'fixture@example.invalid')
            git('config', 'user.name', 'Fixture')
            folder = root / 'changelog.d'
            folder.mkdir()
            old = folder / '20261001-old.md'
            old.write_text('historically published malformed fragment')
            git('add', '.')
            git('commit', '-m', 'baseline')
            base = git('rev-parse', 'HEAD')
            fresh = folder / '20261030-new.md'
            fresh.write_text('---\narea: bots\ntype: fixed\naudience: players\ntitle: Companions can log in again\n---\n')
            git('add', '.')
            git('commit', '-m', 'valid new fragment')
            self.assertEqual(check(root, base, 'HEAD', parser, 'fixture'), 0)
            fresh.write_text('invalid new fragment')
            git('add', '.')
            git('commit', '-m', 'invalid new fragment')
            self.assertEqual(check(root, base, 'HEAD', parser, 'fixture'), 1)
            fresh.unlink()
            old.write_text('changed historical invalid fragment')
            git('add', '-A')
            git('commit', '-m', 'invalid historical edit')
            self.assertEqual(check(root, base, 'HEAD', parser, 'fixture'), 1)
