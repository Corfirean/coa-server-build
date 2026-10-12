import json
import os
from pathlib import Path
import runpy
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


@unittest.skipUnless(os.name == "nt", "Windows launcher")
class WorldExitTests(unittest.TestCase):
    def test_supervisor_records_normal_and_abnormal_exit_with_process_identity(self):
        for code in (0, 1, 3221225477):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                state = root / ".state"
                state.mkdir()
                record = {"pid": 42, "created": 123, "exe": str(root / "Core/worldserver.exe")}
                (state / "world.json").write_text(json.dumps(record))
                launcher = runpy.run_path(str(Path(__file__).with_name("manage.py")))
                watch = launcher["watch_world"]
                watch.__globals__.update(ROOT=root, STATE=state,
                                         spawn=lambda *args: SimpleNamespace(poll=lambda: code))
                with patch("squid_playerbots.validate_bots"):
                    watch()
                self.assertEqual(json.loads((state / "world-exit.json").read_text()),
                                 {"process": record, "exit_code": code})
                self.assertTrue((state / "stop-relay").exists())

    def test_explicit_restart_is_handled_by_supervisor_without_crash_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / ".state"
            state.mkdir()
            spawned = []
            def spawn(*args):
                number = len(spawned) + 1
                record = {"pid": number, "created": number, "exe": str(root / "Core/worldserver.exe")}
                (state / "world.json").write_text(json.dumps(record))
                spawned.append(record)
                return SimpleNamespace(poll=lambda: 2 if number == 1 else 0)
            launcher = runpy.run_path(str(Path(__file__).with_name("manage.py")))
            watch = launcher["watch_world"]
            watch.__globals__.update(ROOT=root, STATE=state, spawn=spawn)
            with patch("squid_playerbots.validate_bots"):
                watch()
            self.assertEqual(len(spawned), 2)
            self.assertEqual(json.loads((state / "world-exit.json").read_text()),
                             {"process": spawned[1], "exit_code": 0})


if __name__ == "__main__":
    unittest.main()
