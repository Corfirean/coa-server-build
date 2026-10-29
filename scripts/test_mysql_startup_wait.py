import ast
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock


class MysqlStartupWaitTests(unittest.TestCase):
    def run_start(self, existing):
        tree = ast.parse(Path(__file__).with_name('manage.py').read_text(encoding='utf8'))
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ('start_mysql', 'wait_ready')]
        clock = [0.0]
        def sleep(seconds):
            clock[0] += seconds
        time = Mock(monotonic=lambda: clock[0], sleep=sleep)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'mysql/data/mysql').mkdir(parents=True)
            process = Mock(return_value={'pid': 123} if existing else None)
            def spawn(*args):
                process.return_value = {'pid': 123}
            namespace = {'ROOT': root, 'time': time, 'ready': lambda name, port: clock[0] >= 162,
                         'process': process, 'spawn': Mock(side_effect=spawn), 'ensure_free': Mock(),
                         'mysql': Mock()}
            exec(compile(ast.Module(body=functions, type_ignores=[]), 'manage.py', 'exec'), namespace)
            namespace['start_mysql']({'mysqlPort': 12345, 'worldPort': 23456})
            self.assertEqual(clock[0], 162)
            self.assertEqual(namespace['spawn'].call_count, 0 if existing else 1)
            namespace['mysql'].assert_any_call(admin='ping')

    def test_fresh_mysql_can_finish_the_reported_162_second_startup(self):
        self.run_start(False)

    def test_already_starting_mysql_gets_the_same_wait_without_a_second_process(self):
        self.run_start(True)


if __name__ == '__main__':
    unittest.main()
