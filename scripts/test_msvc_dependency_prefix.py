import importlib.util
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('prefix', Path(__file__).with_name('msvc-dependency-prefix.py'))
prefix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prefix)


class PrefixTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt' and shutil.which('cl.exe') and shutil.which('ninja'),
                         'MSVC and Ninja are needed for real header dependency qualification')
    def test_hidden_msvc_build_records_header_and_rebuilds_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'probe.h').write_text('#define VALUE 7\n')
            (root / 'probe.cpp').write_text('#include "probe.h"\nint probe() { return VALUE; }\n')
            rules = root / 'CMakeFiles' / 'rules.ninja'
            rules.parent.mkdir()
            rules.write_bytes(b'msvc_deps_prefix = wrong\n')
            prefix.configure(root, prefix.detect('cl.exe'))
            (root / 'build.ninja').write_bytes(rules.read_bytes() + (
                b'rule compile\n  command = cl.exe /nologo /showIncludes /c probe.cpp /Foprobe.obj\n'
                b'  deps = msvc\nbuild probe.obj: compile probe.cpp\n'))
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = subprocess.SW_HIDE
            def ninja(*args):
                return subprocess.run(['ninja', *args], cwd=root, stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT, check=True,
                                      creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=startup).stdout
            ninja()
            self.assertIn(b'probe.h', ninja('-t', 'deps', 'probe.obj'))
            self.assertIn(b'no work to do', ninja())
            (root / 'probe.h').write_text('#define VALUE 9\n')
            self.assertNotIn(b'no work to do', ninja())

    def test_non_utf8_compiler_prefix_is_preserved_as_exact_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            build = Path(directory)
            rules = build / 'CMakeFiles' / 'rules.ninja'
            rules.parent.mkdir()
            rules.write_bytes(b'rule cxx\nmsvc_deps_prefix = wrong encoding\n  deps = msvc\n')
            actual = 'Примечание: включение файла: '.encode('cp866')
            prefix.configure(build, actual)
            self.assertIn(b'msvc_deps_prefix = ' + actual + b'\n', rules.read_bytes())
            modified = rules.stat().st_mtime_ns
            prefix.configure(build, actual)
            self.assertEqual(rules.stat().st_mtime_ns, modified)

    def test_unknown_ninja_layout_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            build = Path(directory)
            rules = build / 'CMakeFiles' / 'rules.ninja'
            rules.parent.mkdir()
            rules.write_bytes(b'rule cxx\n  deps = gcc\n')
            with self.assertRaises(RuntimeError):
                prefix.configure(build, b'Note: including file: ')
