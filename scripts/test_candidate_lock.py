import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('candidate', Path(__file__).with_name('candidate-lock.py'))
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)


class CandidateLockTests(unittest.TestCase):
    def test_new_and_shared_locks_keep_history_out_of_sequential_packaging(self):
        sources = [{'role': role, 'version': str(index)} for index, role in enumerate(
            ['base', 'stable-1', 'stable-2', 'stable-3', 'stable-4'])]
        components = {name: {'sha': 'a' * 40} for name in ('core', 'bots', 'scaling', 'squid', 'manager')}
        for shared in (False, True):
            with self.subTest(shared=shared), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                lock = {'schema': 1, 'snapshot': 'frozen', 'components': components}
                if shared:
                    lock['upgradeSources'] = sources
                    (root / 'lock.json').write_text(json.dumps(lock))
                daily = SimpleNamespace(snapshot=lambda _: 'frozen', resolve=lambda *args, **kwargs: lock,
                                        check_integration=lambda _: None, freeze_external=lambda _: None)
                upgrades = SimpleNamespace(resolve=lambda: sources)
                env = {name.upper() + '_REF': 'a' * 40 for name in components}
                env['GITHUB_OUTPUT'] = str(root / 'output')
                with patch.object(candidate, 'load', side_effect=lambda name: daily if name == 'daily-release' else upgrades), \
                     patch.dict(os.environ, env):
                    candidate.freeze(root / 'lock.json')
                result = json.loads((root / 'lock.json').read_text())
                self.assertEqual(result['upgradeSources'], sources[:3])
                self.assertEqual(result['upgradePolicy'], 'recent-stable')
                self.assertEqual(result['historicalUpgradeSources'], sources)


if __name__ == '__main__':
    unittest.main()
