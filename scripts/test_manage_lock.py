import ast
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest


def load_lock(state):
    import msvcrt
    path = Path(__file__).with_name("manage.py")
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef)
             and node.name in ("atomic_json", "read_json", "control_lock")]
    namespace = dict(STATE=Path(state), contextmanager=contextmanager,
                     msvcrt=msvcrt, json=json, os=os, sys=sys, time=time)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace["control_lock"]


@unittest.skipUnless(os.name == "nt", "Windows byte-range locks")
class ControlLockTests(unittest.TestCase):
    def test_contention_reports_owner_then_recovers_after_holder_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            holder = subprocess.Popen(
                [sys.executable, __file__, "hold", directory],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                self.assertEqual(holder.stdout.readline().strip(), "locked")
                with self.assertRaisesRegex(RuntimeError, f"PID {holder.pid}, action hold"):
                    with load_lock(directory)(seconds=0):
                        self.fail("Concurrent action entered the lock")
            finally:
                holder.terminate()
                holder.communicate(timeout=10)
            with load_lock(directory)(seconds=0):
                owner = json.loads((Path(directory) / "control-owner.json").read_text())
                self.assertEqual(owner["pid"], os.getpid())
            self.assertFalse((Path(directory) / "control-owner.json").exists())

    def test_exception_releases_lock_and_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            lock = load_lock(directory)
            with self.assertRaisesRegex(ValueError, "failure"):
                with lock():
                    raise ValueError("failure")
            with lock(seconds=0):
                pass


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "hold":
        with load_lock(sys.argv[2])():
            print("locked", flush=True)
            time.sleep(30)
    else:
        unittest.main()
