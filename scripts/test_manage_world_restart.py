import ast
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class WorldRestartTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.stop = self.root / 'stop-relay'
        self.stop.touch()
        self.clock = 0
        self.spawned = False
        self.release_supervisor = 0
        self.release_relay = 0
        path = Path(__file__).with_name('manage.py')
        tree = ast.parse(path.read_text(encoding='utf-8-sig'))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'start_world')
        self.bots = SimpleNamespace(validate_bots=Mock(), prepare_playerbots=Mock(), startup_timeout=lambda root: 180)
        self.ns = dict(ROOT=self.root, STATE=self.root, PYTHON='python', Path=Path, __file__=str(path),
                       start_mysql=Mock(), process=self.process, ensure_free=Mock(), mysql=Mock(),
                       spawn=Mock(side_effect=self.spawn), wait_ready=Mock(), wait_relay=Mock(),
                       time=SimpleNamespace(monotonic=lambda: self.clock, sleep=self.sleep))
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), self.ns)

    def sleep(self, seconds):
        self.clock += seconds

    def process(self, name):
        if self.spawned:
            return {'pid': 20} if name in ('world', 'supervisor') else None
        release = {'supervisor': self.release_supervisor, 'relay': self.release_relay}.get(name, 0)
        return {'pid': 10} if self.clock < release else None

    def spawn(self, *args):
        self.assertFalse(self.process('supervisor'))
        self.assertFalse(self.process('relay'))
        self.spawned = True

    def start(self):
        with patch.dict('sys.modules', squid_playerbots=self.bots):
            self.ns['start_world']({'worldPort': 8085, 'raPort': 3443}, 0)

    def test_restart_waits_for_both_old_processes_before_preparing_or_starting(self):
        self.release_supervisor = 0.5
        self.release_relay = 40
        def ensure_free(port):
            self.assertGreaterEqual(self.clock, 40)
            self.assertTrue(self.stop.exists())
        self.ns['ensure_free'].side_effect = ensure_free
        self.start()
        self.assertEqual(self.clock, 40)
        self.assertEqual(self.ns['spawn'].call_count, 1)
        self.bots.prepare_playerbots.assert_called_once()
        self.assertFalse(self.stop.exists())
        self.assertEqual(self.ns['wait_ready'].call_count, 2)

    def test_stuck_old_process_times_out_without_new_world_or_removing_stop_marker(self):
        for name in ('release_supervisor', 'release_relay'):
            with self.subTest(process=name):
                self.clock = 0
                self.release_supervisor = self.release_relay = 0
                setattr(self, name, 100)
                with self.assertRaisesRegex(RuntimeError, '45 seconds'):
                    self.start()
                self.assertEqual(self.clock, 45)
                self.ns['spawn'].assert_not_called()
                self.ns['ensure_free'].assert_not_called()
                self.bots.prepare_playerbots.assert_not_called()
                self.assertTrue(self.stop.exists())

    def test_normal_start_has_no_shutdown_delay(self):
        self.start()
        self.assertEqual(self.clock, 0)
        self.ns['spawn'].assert_called_once()


if __name__ == '__main__':
    unittest.main()
