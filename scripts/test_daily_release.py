import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("daily", Path(__file__).with_name("daily-release.py"))
daily = importlib.util.module_from_spec(spec)
spec.loader.exec_module(daily)


class IntegrationTests(unittest.TestCase):
    def test_resolve_freezes_selected_upstream_and_checks_its_ancestry(self):
        def api(endpoint):
            if endpoint.endswith('/releases/latest'):
                return {'tag_name': 'coa-custom-1.7', 'assets': []}
            if '/tags?' in endpoint:
                return [{'name': 'v1.0', 'commit': {'sha': 'squid-sha'}}]
            return {'status': 'ahead'}

        with patch.object(daily, 'gh', side_effect=api) as calls, \
                patch.object(daily, 'revision', side_effect=lambda repo, ref: ref):
            lock = daily.resolve(upstream_ref='tested-upstream-sha')
            self.assertEqual(lock['components']['upstream']['sha'], 'tested-upstream-sha')
            daily.check_integration(lock)
            calls.assert_any_call('repos/Corfirean/azerothcore-wotlk-coa/compare/tested-upstream-sha...coa-bots')

    def test_explicit_race_release_does_not_follow_the_latest_release(self):
        def api(endpoint):
            if endpoint.endswith('/releases/tags/coa-custom-1.8'):
                return {'tag_name': 'coa-custom-1.8', 'assets': []}
            if '/tags?' in endpoint:
                return [{'name': 'v2.5', 'commit': {'sha': 'squid-sha'}}]
            raise AssertionError(endpoint)
        with patch.object(daily, 'gh', side_effect=api), \
                patch.object(daily, 'revision', side_effect=lambda repo, ref: ref):
            lock = daily.resolve(races_ref='coa-custom-1.8')
        self.assertEqual(lock['components']['races']['sha'], 'refs/tags/coa-custom-1.8')

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
