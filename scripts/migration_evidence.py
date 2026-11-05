import hashlib
import json


def inventory_digest(manifest):
    inventory = [[m['db'], m['id'], m['sha256'], m.get('compatible_sha256', []),
                  m.get('destructive', False)] for m in manifest['migrations']]
    return hashlib.sha256(json.dumps(inventory, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def validate(report, manifest):
    if (not {'migration-ledger', 'legacy-race-start-data'} <= set(report.get('checks', []))
            or report.get('migrationInventorySha256') != inventory_digest(manifest)):
        raise RuntimeError('Migration qualification inventory is missing or changed')
    audits = report.get('migrations')
    if not isinstance(audits, dict) or not audits:
        raise RuntimeError('Migration qualification has no realm evidence')
    total = len(manifest['migrations'])
    for realm, audit in audits.items():
        values = [audit.get(key) for key in ('total', 'applied', 'checksumVerified', 'legacyUnknown')]
        if (any(type(value) is not int or value < 0 for value in values)
                or values[0] != total or values[1] != total or sum(values[2:]) != total):
            raise RuntimeError('Incomplete migration qualification for realm: ' + realm)
