"""Exercise production dispatch without loading Windows DLLs on controller CI."""
import argparse
import ast
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


if __name__ == "__main__":
    unittest.main()
