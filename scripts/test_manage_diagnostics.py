import ast
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest


def setup(root, action):
    path = Path(__file__).with_name("manage.py")
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_install_diagnostics")
    ns = dict(STATE=root / ".state", ROOT=root, Path=Path, os=os, time=time, json=json,
              sys=SimpleNamespace(argv=[str(path), action], version=sys.version), __file__=str(path))
    for name in ("main", "prepare", "ensure_free", "wait_ready", "spawn", "start_mysql", "start_auth",
                 "start_world", "watch_world", "stop_all", "terminate", "wait_stopped"):
        ns[name] = lambda *args, **kwargs: None
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), ns)
    return ns


class DiagnosticsTests(unittest.TestCase):
    def test_import_style_install_traces_failures_without_arguments_or_exception_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ns = setup(root, "start-all")
            def fail(*args):
                raise RuntimeError("sensitive exception text")
            ns["prepare"] = fail
            ns["_install_diagnostics"]()
            self.assertIs(ns["start_mysql"].__globals__, ns)
            with self.assertRaises(RuntimeError):
                ns["prepare"]({"rootPassword": "sensitive argument"})
            log = next((root / ".state/diagnostics").glob("*.jsonl")).read_text(encoding="utf-8")
            self.assertNotIn("sensitive", log)
            events = [json.loads(line)["event"] for line in log.splitlines()]
            self.assertEqual(events, ["diagnostics.started", "prepare.begin", "prepare.error"])

    def test_status_polling_does_not_create_logs_and_retention_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ns = setup(root, "status-json")
            ns["_install_diagnostics"]()
            self.assertFalse((root / ".state").exists())
            logs = root / ".state/diagnostics"
            logs.mkdir(parents=True)
            for index in range(25):
                (logs / f"manage-old-{index}.jsonl").write_text("{}\n")
            ns = setup(root, "start-all")
            ns["_install_diagnostics"]()
            self.assertEqual(len(list(logs.glob("*.jsonl"))), 20)
