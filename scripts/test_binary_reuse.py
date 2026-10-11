import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('reuse', Path(__file__).with_name('validate-binary-reuse.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class BinaryReuse(unittest.TestCase):
    def test_sql_only_delta_is_allowed(self):
        module.validate_delta({'status': 'ahead', 'files': [{'filename': 'data/sql/updates/pending_db_world/fix.sql'}]})

    def test_code_delta_is_rejected(self):
        with self.assertRaises(RuntimeError):
            module.validate_delta({'status': 'ahead', 'files': [{'filename': 'src/server/game/main.cpp'}]})

    def test_incomplete_or_divergent_diff_is_rejected(self):
        for value in ({'status': 'diverged', 'files': []}, {'status': 'ahead', 'files': [{}] * 300}):
            with self.assertRaises(RuntimeError):
                module.validate_delta(value)
