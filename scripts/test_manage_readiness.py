import ast
import ctypes
import os
from pathlib import Path
import socket
import struct
import subprocess
import unittest
from unittest.mock import Mock
from ctypes import wintypes


@unittest.skipUnless(os.name == 'nt', 'Windows listener integration')
class ReadinessTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).with_name('manage.py')
        tree = ast.parse(path.read_text(encoding='utf-8-sig'))
        names = {'listeners', 'netstat_listeners', 'ready', 'ensure_free', 'tcp_rows', 'accept_owner', 'owner_confirms'}
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        self.ns = dict(ctypes=ctypes, wintypes=wintypes, socket=socket, os=os,
                       LOOPBACK_PEERS=('127.0.0.1', '::ffff:127.0.0.1'),
                       struct=struct, subprocess=subprocess, Path=Path,
                       kernel=ctypes.WinDLL('kernel32'), time=__import__('time'),
                       process=Mock(return_value={'pid': os.getpid()}),
                       same_process=Mock(return_value=True))
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), self.ns)
        self.server = socket.socket()
        self.addCleanup(self.server.close)
        self.server.bind(('127.0.0.1', 0))
        self.port = self.server.getsockname()[1]

    def test_native_primary_path_does_not_spawn(self):
        self.server.listen()
        self.ns['netstat_listeners'] = Mock(side_effect=AssertionError('unexpected fallback'))
        self.assertTrue(self.ns['ready']('auth', self.port))

    def test_real_listener_missing_from_primary_table(self):
        self.server.listen()
        self.ns['listeners'] = lambda: []
        self.assertTrue(self.ns['ready']('auth', self.port))

    def test_denied_primary_uses_real_fallback_for_all_services(self):
        self.server.listen()
        for error in (PermissionError(5, 'Access denied'), RuntimeError('table changed')):
            self.ns['listeners'] = Mock(side_effect=error)
            for service in ('auth', 'mysql', 'world'):
                self.assertTrue(self.ns['ready'](service, self.port))

    def test_denied_primary_still_rejects_wrong_owner_and_reused_pid(self):
        self.server.listen()
        self.ns['listeners'] = Mock(side_effect=PermissionError(5, 'Access denied'))
        self.ns['process'].return_value = {'pid': 1}
        self.assertFalse(self.ns['ready']('auth', self.port))
        self.ns['process'].return_value = {'pid': os.getpid()}
        self.ns['same_process'].return_value = False
        self.assertFalse(self.ns['ready']('auth', self.port))

    def test_blind_tables_confirmed_by_accepted_connection_owner(self):
        # Affected systems: neither table shows the listener, yet the tracked process accepts on the port.
        self.server.listen()
        self.ns['listeners'] = lambda: []
        self.ns['netstat_listeners'] = lambda: []
        self.assertTrue(self.ns['ready']('auth', self.port))
        self.assertTrue(self.ns['ready']('world', self.port))

    def test_blind_tables_reject_foreign_acceptor_and_mysql(self):
        self.server.listen()
        self.ns['listeners'] = lambda: []
        self.ns['netstat_listeners'] = lambda: []
        self.ns['process'].return_value = {'pid': 1}
        self.assertFalse(self.ns['ready']('auth', self.port))
        self.ns['process'].return_value = {'pid': os.getpid()}
        # MySQL never takes the connection path.
        self.assertFalse(self.ns['ready']('mysql', self.port))
        self.ns['same_process'].return_value = False
        self.assertFalse(self.ns['ready']('auth', self.port))

    def test_owner_rows_identify_accepting_process(self):
        self.server.listen()
        evidence = self.ns['accept_owner'](self.port)
        rows = evidence['server_rows']
        self.assertEqual([(r['state'], r['local_port'], r['pid']) for r in rows], [(5, self.port, os.getpid())])
        self.assertIsNone(self.ns['accept_owner'](self._closed_port()))

    def _closed_port(self):
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            return s.getsockname()[1]

    def test_ipv6_only_loopback_listener_is_not_ready(self):
        # A [::1]-only server cannot serve IPv4 game clients on 127.0.0.1.
        server = socket.socket(socket.AF_INET6)
        self.addCleanup(server.close)
        server.bind(('::1', 0)); server.listen()
        port = server.getsockname()[1]
        self.ns['listeners'] = lambda: []
        self.ns['netstat_listeners'] = lambda: []
        self.assertFalse(self.ns['ready']('auth', port))

    def test_both_queries_denied_never_means_ready_or_free(self):
        self.ns['listeners'] = Mock(side_effect=PermissionError(5, 'Access denied'))
        self.ns['netstat_listeners'] = Mock(side_effect=PermissionError(5, 'Access denied'))
        self.assertFalse(self.ns['ready']('auth', self.port))
        with self.assertRaises(PermissionError):
            self.ns['ensure_free'](self.port)

    def test_prestart_denied_primary_still_detects_real_owner(self):
        self.server.listen()
        self.ns['listeners'] = Mock(side_effect=PermissionError(5, 'Access denied'))
        with self.assertRaisesRegex(RuntimeError, str(os.getpid())):
            self.ns['ensure_free'](self.port)

    def test_prestart_denied_primary_allows_exclusively_bindable_port(self):
        self.server.close()
        self.ns['listeners'] = Mock(side_effect=PermissionError(5, 'Access denied'))
        self.ns['ensure_free'](self.port)

    def test_bound_but_not_listening_rejected(self):
        self.ns['listeners'] = lambda: []
        self.assertFalse(self.ns['ready']('auth', self.port))

    def test_wrong_owner_rejected(self):
        self.server.listen()
        self.ns['listeners'] = lambda: []
        self.ns['process'].return_value = {'pid': 1}
        self.assertFalse(self.ns['ready']('auth', self.port))

    def test_closed_listener_rejected(self):
        self.server.listen()
        self.server.close()
        self.ns['listeners'] = lambda: []
        self.assertFalse(self.ns['ready']('auth', self.port))

    def test_process_exit_or_pid_reuse_during_query_rejected(self):
        self.server.listen()
        self.ns['listeners'] = lambda: []
        self.ns['same_process'].return_value = False
        self.assertFalse(self.ns['ready']('auth', self.port))

    def test_no_record_never_uses_external_query(self):
        self.ns['process'].return_value = None
        self.ns['netstat_listeners'] = Mock(side_effect=AssertionError('unexpected fallback'))
        self.assertFalse(self.ns['ready']('auth', self.port))

    def test_failed_or_hung_query_never_means_ready(self):
        self.ns['listeners'] = lambda: []
        for error in (OSError('unavailable'), subprocess.TimeoutExpired('netstat', 3),
                      subprocess.CalledProcessError(1, 'netstat')):
            self.ns['netstat_listeners'] = Mock(side_effect=error)
            self.assertFalse(self.ns['ready']('auth', self.port))


if __name__ == '__main__':
    unittest.main()
