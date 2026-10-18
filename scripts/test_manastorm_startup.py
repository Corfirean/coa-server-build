import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location('startup', Path(__file__).with_name('verify-manastorm-startup.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ManastormStartup(unittest.TestCase):
    def test_enabled_backend_must_initialize(self):
        with self.assertRaises(RuntimeError):
            module.verify('Manastorm.Enable = 1', 'Worldserver ready')

    def test_successful_backend_is_accepted(self):
        self.assertTrue(module.verify('Manastorm.Enable = 1', 'Shared Manastorm backend initialized.'))

    def test_disabled_module_needs_no_backend(self):
        self.assertFalse(module.verify('Manastorm.Enable = 0', 'Worldserver ready'))

    def test_missing_setting_uses_the_enabled_server_default(self):
        with self.assertRaises(RuntimeError):
            module.verify('# Manastorm.Enable = 0', '')

    def test_ambiguous_setting_is_rejected(self):
        with self.assertRaises(RuntimeError):
            module.verify('Manastorm.Enable = perhaps', 'Shared Manastorm backend initialized.')
