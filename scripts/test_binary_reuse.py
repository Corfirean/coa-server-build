import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('reuse', Path(__file__).with_name('validate-binary-reuse.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class BinaryReuse(unittest.TestCase):
    def test_cancelled_package_does_not_hide_successful_binary_job(self):
        jobs = [{'id': 1, 'name': 'binaries / source', 'conclusion': 'success'},
                {'id': 2, 'name': 'binaries / build', 'conclusion': 'success'},
                {'id': 3, 'name': 'package', 'conclusion': 'cancelled'}]
        self.assertEqual(module.verified_build_job(jobs)['id'], 2)
        for index in (0, 1):
            altered = [dict(job) for job in jobs]
            altered[index]['conclusion'] = 'cancelled'
            with self.assertRaises(RuntimeError):
                module.verified_build_job(altered)

    def test_identical_sources_reuse_verified_binaries_without_recompilation(self):
        module.validate_delta({'status': 'identical', 'files': []})

    def test_sql_only_delta_is_allowed(self):
        module.validate_delta({'status': 'ahead', 'files': [{'filename': 'data/sql/updates/pending_db_world/fix.sql'}]})

    def test_code_delta_is_rejected(self):
        with self.assertRaises(RuntimeError):
            module.validate_delta({'status': 'ahead', 'files': [{'filename': 'src/server/game/main.cpp'}]})

    def test_incomplete_or_divergent_diff_is_rejected(self):
        for value in ({'status': 'diverged', 'files': []}, {'status': 'ahead', 'files': [{}] * 300}):
            with self.assertRaises(RuntimeError):
                module.validate_delta(value)
