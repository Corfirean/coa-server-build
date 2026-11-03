"""Exercise production dispatch without loading Windows DLLs on controller CI."""
import argparse
import ast
import re
import subprocess
import tempfile
from contextlib import nullcontext
from pathlib import Path
import unittest
from unittest.mock import Mock, patch


class ShutdownDispatchTests(unittest.TestCase):
    def dispatch(self, action, preparation_error):
        source = ast.parse(Path(__file__).with_name("manage.py").read_text(encoding="utf-8"))
        main = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == "main")
        config = {"mysqlPort": 13307, "authPort": 13724, "worldPort": 18085, "raPort": 13443}
        prepare = Mock(side_effect=preparation_error)
        stop = Mock()
        start = Mock()
        namespace = {"argparse": argparse, "settings": Mock(return_value=config),
                     "control_lock": nullcontext, "prepare": prepare,
                     "stop_all": stop, "start_mysql": start}
        exec(compile(ast.Module(body=[main], type_ignores=[]), "manage.py", "exec"), namespace)
        with patch("sys.argv", ["manage.py", action]):
            namespace["main"]()
        return config, prepare, stop, start

    def test_stop_does_not_render_invalid_or_missing_startup_templates(self):
        for error in [ValueError("An unresolved placeholder remains in a server configuration."),
                      FileNotFoundError("worldserver.conf.template"),
                      RuntimeError("Stop this repack before moving its folder or changing its ports.")]:
            with self.subTest(error=str(error)):
                config, prepare, stop, start = self.dispatch("stop-all", error)
                stop.assert_called_once_with(config)
                prepare.assert_not_called()
                start.assert_not_called()

    def test_start_still_rejects_an_invalid_template(self):
        with self.assertRaisesRegex(ValueError, "unresolved placeholder"):
            self.dispatch("start-mysql", ValueError("An unresolved placeholder remains in a server configuration."))

    def test_invalid_template_reports_placeholder_names_without_connection_credentials(self):
        source = ast.parse(Path(__file__).with_name("manage.py").read_text(encoding="utf-8"))
        prepare = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == "prepare")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "Settings").mkdir()
            (root / "Settings/authserver.conf.template").write_text("LoginDatabaseInfo=@LoginDatabaseInfo@\n")
            (root / "Settings/worldserver.conf.template").write_text("WorldDatabaseInfo=@WorldDatabaseInfo@\nUnknown=@MISSING_DATABASE@\nOther=@BROKEN_LOGIN@\n# @COMMENT_ONLY@\n")
            credentials = {"rootPassword": "a" * 48, "appPassword": "b" * 48}
            namespace = {"ROOT": root, "STATE": root / ".state", "re": re,
                         "native_root": lambda: root.as_posix(), "read_json": lambda _: credentials,
                         "process": lambda _: None, "atomic_json": Mock()}
            exec(compile(ast.Module(body=[prepare], type_ignores=[]), "manage.py", "exec"), namespace)
            config = {"mysqlPort": 13307, "authPort": 13724, "worldPort": 18085, "raPort": 13443}
            with self.assertRaises(ValueError) as raised:
                namespace["prepare"](config)
            message = str(raised.exception)
            self.assertIn("Settings/worldserver.conf.template", message)
            self.assertIn("@BROKEN_LOGIN@, @MISSING_DATABASE@", message)
            self.assertNotIn("@COMMENT_ONLY@", message)
            self.assertNotIn(credentials["appPassword"], message)


class StartingWorldShutdownTests(unittest.TestCase):
    def shutdown(self, console_error=None, stopped=True):
        source = ast.parse(Path(__file__).with_name("manage.py").read_text(encoding="utf-8"))
        stop = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == "stop_all")
        world = {"pid": 101, "created": 10}
        database = {"pid": 102, "created": 20}
        events = []
        namespace = {
            "subprocess": subprocess,
            "process": lambda name: {"world": world, "mysql": database}.get(name),
            "ra": Mock(side_effect=console_error, return_value="Shutdown requested"),
            "terminate": Mock(side_effect=lambda record: events.append(("terminate", record))),
            "wait_stopped": Mock(side_effect=lambda record, seconds: events.append(("wait", record)) or stopped),
            "mysql": Mock(side_effect=lambda **kwargs: events.append(("mysql", kwargs))),
        }
        exec(compile(ast.Module(body=[stop], type_ignores=[]), "manage.py", "exec"), namespace)
        return namespace, world, database, events

    def test_unavailable_console_stops_owned_world_before_database(self):
        for error in [RuntimeError("Start this repack's worldserver first."), OSError("Connection refused")]:
            with self.subTest(error=type(error).__name__):
                namespace, world, database, events = self.shutdown(error)
                namespace["stop_all"]({})
                self.assertEqual(events, [("terminate", world), ("wait", world), ("mysql", {"admin": "shutdown"}), ("wait", database)])

    def test_a_world_that_does_not_stop_keeps_database_running(self):
        namespace, world, _, events = self.shutdown(RuntimeError("Console unavailable"), False)
        with self.assertRaisesRegex(RuntimeError, "database has been left running"):
            namespace["stop_all"]({})
        namespace["mysql"].assert_not_called()
        self.assertEqual(events, [("terminate", world), ("wait", world)])

    def test_healthy_world_keeps_graceful_shutdown(self):
        namespace, world, database, events = self.shutdown()
        namespace["stop_all"]({})
        namespace["terminate"].assert_not_called()
        self.assertEqual(events, [("wait", world), ("mysql", {"admin": "shutdown"}), ("wait", database)])

    def test_database_shutdown_connection_loss_is_accepted_only_after_owned_process_exits(self):
        namespace, _, database, _ = self.shutdown()
        namespace["mysql"].side_effect = RuntimeError("Lost connection during shutdown")
        namespace["stop_all"]({})
        namespace["wait_stopped"].assert_any_call(database, 60)

    def test_failed_database_shutdown_does_not_hide_a_still_running_process(self):
        namespace, world, database, _ = self.shutdown()
        error = RuntimeError("Shutdown denied")
        namespace["mysql"].side_effect = error
        namespace["wait_stopped"].side_effect = lambda record, seconds: record == world
        with self.assertRaises(RuntimeError) as raised:
            namespace["stop_all"]({})
        self.assertIs(raised.exception, error)
        namespace["wait_stopped"].assert_any_call(database, 60)


if __name__ == "__main__":
    unittest.main()
