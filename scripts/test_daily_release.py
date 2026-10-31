import importlib.util
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("daily", Path(__file__).with_name("daily-release.py"))
daily = importlib.util.module_from_spec(spec)
spec.loader.exec_module(daily)


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        override = patch.object(daily, 'freeze_external')
        override.start()
        self.addCleanup(override.stop)

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

    def test_experimental_portable_is_explicit_in_candidate_metadata(self):
        def api(endpoint):
            if '/releases/' in endpoint:
                return {'tag_name': 'coa-custom-1.8', 'assets': []}
            if '/tags?' in endpoint:
                return [{'name': 'v2.6', 'commit': {'sha': 'squid-sha'}}]
            raise AssertionError(endpoint)
        with patch.object(daily, 'gh', side_effect=api), patch.object(daily, 'revision', return_value='frozen'):
            normal = daily.resolve()
            experimental = daily.resolve(experimental_portable=True)
        self.assertEqual(normal['excludedBranches'], ['feat/portable-characters', 'feat/portable-session-bridge'])
        self.assertEqual(experimental['excludedBranches'], [])
        self.assertEqual(experimental['experimentalFeatures'], ['portable-characters'])

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


class ExternalLockTests(unittest.TestCase):
    def test_external_patch_and_dungeon_revision_are_part_of_snapshot(self):
        config = json.loads((Path(__file__).resolve().parents[1] / 'external-modules.json').read_text())
        components = {'squid': {'sha': config['modules']['squid']['sha']}}
        daily.freeze_external(components)
        self.assertEqual(components['dungeon-clear']['sha'], config['modules']['dungeon-clear']['sha'])
        before = daily.snapshot(components)
        changed = copy.deepcopy(components)
        changed['squid']['patchSha256'] = 'f' * 64
        self.assertNotEqual(before, daily.snapshot(changed))

    def test_unreviewed_squid_revision_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'compatibility review'):
            daily.freeze_external({'squid': {'sha': 'a' * 40}})


if __name__ == "__main__":
    unittest.main()
