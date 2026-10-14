"""Exercise production dispatch without loading Windows DLLs on controller CI."""
import argparse
import ast
import re
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


if __name__ == "__main__":
    unittest.main()
