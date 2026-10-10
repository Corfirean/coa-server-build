import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("daily", Path(__file__).with_name("daily-release.py"))
daily = importlib.util.module_from_spec(spec)
spec.loader.exec_module(daily)


class IntegrationTests(unittest.TestCase):
    def lock(self):
        return {"components": {
            "core": {"repository": "owner/core", "sha": "candidate"},
            "upstream": {"sha": "upstream"}, "races": {"sha": "races"}}}

    def test_missing_upstream_blocks_release(self):
        with patch.object(daily, "gh", return_value={"status": "diverged"}):
            with self.assertRaisesRegex(RuntimeError, "upstream"):
                daily.check_integration(self.lock())

    def test_missing_races_blocks_release(self):
        with patch.object(daily, "gh", side_effect=[{"status": "ahead"}, {"status": "behind"}]):
            with self.assertRaisesRegex(RuntimeError, "races"):
                daily.check_integration(self.lock())

    def test_both_integrated(self):
        with patch.object(daily, "gh", return_value={"status": "ahead"}) as api:
            daily.check_integration(self.lock())
            self.assertEqual(api.call_count, 2)


if __name__ == "__main__":
    unittest.main()
