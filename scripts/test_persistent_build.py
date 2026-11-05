import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('persistent', Path(__file__).with_name('persistent-build.py'))
persistent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(persistent)


class PersistentBuildTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('ninja'), 'Ninja is needed for dependency graph integration')
    def test_real_ninja_reuses_rechecked_out_sources_but_rebuilds_changed_header(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'src'
            source.mkdir()
            cpp = source / 'sample.cpp'
            header = source / 'sample.h'
            cpp.write_text('source')
            header.write_text('header')
            build = root / 'build'
            build.mkdir()
            script = build / 'compile.py'
            script.write_text('from pathlib import Path\nPath("sample.obj").write_bytes(Path("../src/sample.cpp").read_bytes()+Path("../src/sample.h").read_bytes())\n')
            (build / 'build.ninja').write_text(
                f'rule compile\n  command = "{Path(sys.executable).as_posix()}" compile.py\n'
                'build sample.obj: compile ../src/sample.cpp | ../src/sample.h\n')
            state = root / 'state' / 'inputs.json'
            persistent.prepare(root, state)
            def ninja():
                return subprocess.run(['ninja'], cwd=build, capture_output=True, text=True, check=True).stdout
            ninja()
            original = cpp.stat().st_mtime_ns
            for path in (cpp, header):
                os.utime(path, ns=(original + 2_000_000_000, original + 2_000_000_000))
            persistent.prepare(root, state)
            self.assertIn('no work to do', ninja())
            header.write_text('edited')
            persistent.prepare(root, state)
            self.assertNotIn('no work to do', ninja())
            self.assertEqual((build / 'sample.obj').read_bytes(), b'sourceedited')

    def test_recheckout_preserves_only_byte_identical_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'modules' / 'example'
            source.mkdir(parents=True)
            unchanged = source / 'unchanged.cpp'
            changed = source / 'changed.h'
            removed = source / 'removed.cpp'
            for path in (unchanged, changed, removed):
                path.write_text('original')
            state = root / 'state' / 'inputs.json'
            persistent.prepare(root, state)
            original = unchanged.stat().st_mtime_ns
            for path in (unchanged, changed):
                os.utime(path, ns=(original + 2_000_000_000, original + 2_000_000_000))
            changed.write_text('modified')
            removed.unlink()
            result = persistent.prepare(root, state)
            self.assertEqual(unchanged.stat().st_mtime_ns, original)
            self.assertNotEqual(changed.stat().st_mtime_ns, original)
            self.assertEqual(result, {'unchanged': 1, 'changed_or_new': 1, 'removed': 1})

    def test_state_cannot_be_reused_for_another_source_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / 'inputs.json'
            persistent.prepare(root, state)
            other = root / 'other'
            other.mkdir()
            with self.assertRaisesRegex(RuntimeError, 'different source checkout'):
                persistent.prepare(other, state)

    def test_nested_git_and_build_outputs_are_not_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for folder in ('modules/example/.git', 'modules/example/build'):
                path = root / folder
                path.mkdir(parents=True)
                (path / 'ignored').write_text('ignored')
            self.assertEqual(list(persistent.inputs(root)), [])
