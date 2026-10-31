import ast
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import socket
import struct
from types import SimpleNamespace
import unittest

FIXED = Path(__file__).with_name('manage.py')

def load(path):
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef)
             and n.name in ('listeners', 'ensure_free')]
    ns = dict(ctypes=ctypes, wintypes=wintypes, socket=socket, struct=struct,
              time=__import__('time'))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), ns)
    return ns

@unittest.skipUnless(os.name == "nt", "Windows TCP listener and exclusive bind integration tests")
class PortTests(unittest.TestCase):
    def setUp(self):
        self.ns = load(FIXED)
        self.s = socket.socket()
        self.s.bind(('127.0.0.1', 0))
        self.port = self.s.getsockname()[1]
        self.addCleanup(self.s.close)

    def fast_clock(self, sleep_callback=None):
        clock = [0]
        def sleep(seconds):
            clock[0] += seconds
            if sleep_callback:
                sleep_callback()
        self.ns['time'] = SimpleNamespace(monotonic=lambda: clock[0], sleep=sleep)
        return clock

    def test_native_free_port(self):
        self.s.close()
        self.ns['ensure_free'](self.port)

    def test_native_real_listener_blocked_with_pid(self):
        self.s.listen()
        self.assertIn((self.port, os.getpid()), self.ns['listeners']())
        with self.assertRaisesRegex(RuntimeError, str(os.getpid())):
            self.ns['ensure_free'](self.port)


    def test_fixed_pid_zero_free_port_and_no_probe_leak(self):
        self.s.close()
        self.ns['listeners'] = lambda: [(self.port, 0)]
        self.ns['ensure_free'](self.port)
        with socket.socket() as check:
            check.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            check.bind(('0.0.0.0', self.port))
            check.listen()

    def test_pid_zero_real_listener_never_bypassed(self):
        self.s.listen()
        self.ns['listeners'] = lambda: [(self.port, 0)]
        clock = self.fast_clock()
        with self.assertRaisesRegex(RuntimeError, 'remains unavailable'):
            self.ns['ensure_free'](self.port)
        self.assertGreaterEqual(clock[0], 30)
        self.assertEqual(self.s.getsockname()[1], self.port)

    def test_pid_zero_bound_not_listening_still_blocked(self):
        self.ns['listeners'] = lambda: [(self.port, 0)]
        self.fast_clock()
        with self.assertRaisesRegex(RuntimeError, 'remains unavailable'):
            self.ns['ensure_free'](self.port)

    def test_pid_zero_reusable_socket_not_hijacked(self):
        self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.s.listen()
        self.ns['listeners'] = lambda: [(self.port, 0)]
        self.fast_clock()
        with self.assertRaises(RuntimeError):
            self.ns['ensure_free'](self.port)

    def test_pid_zero_transient_released_after_wait(self):
        self.s.listen()
        self.ns['listeners'] = lambda: [(self.port, 0)]
        clock = self.fast_clock(self.s.close)
        self.ns['ensure_free'](self.port)
        self.assertEqual(clock[0], .25)

    def test_pid_zero_changes_to_real_owner_blocks(self):
        self.s.listen()
        attempts = [0]
        def listeners():
            attempts[0] += 1
            return [(self.port, 0 if attempts[0] == 1 else os.getpid())]
        self.ns['listeners'] = listeners
        self.fast_clock()
        with self.assertRaisesRegex(RuntimeError, str(os.getpid())):
            self.ns['ensure_free'](self.port)

    def test_mixed_owners_fail_immediately(self):
        self.s.close()
        self.ns['listeners'] = lambda: [(self.port, 0), (self.port, 98765)]
        clock = self.fast_clock()
        with self.assertRaisesRegex(RuntimeError, '98765'):
            self.ns['ensure_free'](self.port)
        self.assertEqual(clock[0], 0)

    def test_unrelated_pid_zero_port_ignored(self):
        self.ns['listeners'] = lambda: [(self.port + 1, 0)]
        self.ns['ensure_free'](self.port)

    def test_unexpected_socket_failure_not_hidden(self):
        self.ns['listeners'] = lambda: [(self.port, 0)]
        def broken(*args):
            raise OSError(10055, 'simulated resource exhaustion')
        self.ns['socket'] = SimpleNamespace(socket=broken, AF_INET=socket.AF_INET, SOCK_STREAM=socket.SOCK_STREAM)
        with self.assertRaises(OSError):
            self.ns['ensure_free'](self.port)

    def test_100_real_start_stop_cycles(self):
        self.s.close()
        for _ in range(100):
            with socket.socket() as server:
                server.bind(('127.0.0.1', 0)); server.listen()
                port = server.getsockname()[1]
                with self.assertRaises(RuntimeError):
                    self.ns['ensure_free'](port)
            self.ns['ensure_free'](port)

if __name__ == '__main__':
    unittest.main(verbosity=2)
