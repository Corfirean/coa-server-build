import copy
import unittest
from migration_evidence import inventory_digest, validate


class MigrationEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.manifest = {'migrations': [{'db': 'world', 'id': 'one', 'sha256': 'a' * 64}]}
        self.report = {'checks': ['migration-ledger', 'legacy-race-start-data'],
                       'migrationInventorySha256': inventory_digest(self.manifest),
                       'migrations': {'CoA': {'total': 1, 'applied': 1, 'checksumVerified': 1, 'legacyUnknown': 0}}}

    def test_complete_evidence_and_explicit_legacy_unknown_are_accepted(self):
        validate(self.report, self.manifest)
        self.report['migrations']['CoA'].update(checksumVerified=0, legacyUnknown=1)
        validate(self.report, self.manifest)

    def test_missing_stale_or_incomplete_evidence_is_rejected(self):
        for field, value in [('checks', []), ('migrationInventorySha256', '0' * 64), ('migrations', {})]:
            report = copy.deepcopy(self.report)
            report[field] = value
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                validate(report, self.manifest)
        for field, value in [('total', 0), ('applied', 0), ('applied', True),
                             ('checksumVerified', 0), ('legacyUnknown', -1)]:
            report = copy.deepcopy(self.report)
            report['migrations']['CoA'][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(RuntimeError):
                validate(report, self.manifest)

    def test_inventory_binds_order_database_checksum_compatibility_and_destructive_flag(self):
        original = inventory_digest(self.manifest)
        for field, value in [('db', 'auth'), ('id', 'other'), ('sha256', 'b' * 64),
                             ('compatible_sha256', ['c' * 64]), ('destructive', True)]:
            manifest = copy.deepcopy(self.manifest)
            manifest['migrations'][0][field] = value
            self.assertNotEqual(original, inventory_digest(manifest))
