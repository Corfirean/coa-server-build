import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('flags', Path(__file__).with_name('validate-msvc-cache.py'))
flags = importlib.util.module_from_spec(spec)
spec.loader.exec_module(flags)


class CacheFlagsTests(unittest.TestCase):
    def test_embedded_debug_is_cacheable(self):
        flags.validate('sccache cl.exe /c /Z7 /O2 sample.cpp /Fooutput.obj')

    def test_pch_and_program_database_flags_are_rejected(self):
        for option in ('/Fpfile.pch', '/Ycheader.h', '/Yuheader.h', '/Zi', '/ZI'):
            with self.assertRaises(RuntimeError):
                flags.validate('sccache cl.exe /c /Z7 ' + option + ' sample.cpp')

    def test_missing_embedded_debug_is_rejected(self):
        with self.assertRaises(RuntimeError):
            flags.validate('cl.exe /c /O2 sample.cpp')


if __name__ == '__main__':
    unittest.main()
