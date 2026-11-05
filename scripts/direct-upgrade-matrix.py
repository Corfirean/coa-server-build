"""Freeze and validate independent direct upgrades to an already signed release."""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
from pathlib import Path

spec = importlib.util.spec_from_file_location('upgrade_sources', Path(__file__).with_name('upgrade-sources.py'))
upgrades = importlib.util.module_from_spec(spec)
spec.loader.exec_module(upgrades)


def freeze(manager_ref, version, output, prepared=None):
    sources = upgrades.resolve()
    upgrades.validate_roles(sources)
    prepared_manager = None
    if prepared is not None:
        raw = (prepared / 'manifest.json').read_bytes()
        manifest = json.loads(raw)
        release = json.loads((prepared / 'release-lock.json').read_text(encoding='utf-8-sig'))
        prepared_manager = release['components']['manager']['sha']
        if version and version != manifest['version']:
            raise RuntimeError('Prepared version differs from requested target')
        version = manifest['version']
        if not re.fullmatch(r'\d+\.\d+\.\d+', version) or manifest.get('kind') != 'update':
            raise RuntimeError('Prepared target must be a versioned update package')
        digest = hashlib.sha256(raw).hexdigest()
        existing = next((s for s in sources if s['version'] == version), None)
        if existing and existing['manifestSha256'] != digest:
            raise RuntimeError('Prepared target differs from the published version')
        if existing is None:
            sources.append({'role': f'stable-{len(sources)}', 'version': version,
                            'manifestSha256': digest, 'assets': {}, 'prepared': True})
    target = next((s for s in sources if s['version'] == version), None) if version else sources[1]
    if target is None or target['role'] == 'base':
        raise RuntimeError('Target must be an available signed server release')
    manager = json.loads(subprocess.check_output(
        ['gh', 'api', 'repos/Corfirean/coa-server-manager/commits/' + manager_ref], encoding='utf-8'))['sha']
    if not re.fullmatch('[0-9a-f]{40}', manager):
        raise RuntimeError('Manager must resolve to an exact revision')
    if prepared_manager is not None and manager != prepared_manager:
        raise RuntimeError('Manager differs from the prepared candidate lock')
    eligible = [s for s in sources if tuple(map(int, s['version'].split('.'))) <= tuple(map(int, target['version'].split('.')))]
    lock = {'upgradeSources': sources, 'manager': manager, 'targetRole': target['role'],
            'targetVersion': target['version'], 'testedRoles': [s['role'] for s in eligible]}
    output.write_text(json.dumps(lock, indent=2) + '\n', encoding='utf-8')
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
        stream.write('manager=' + manager + '\n')
        stream.write('target_role=' + target['role'] + '\n')
        stream.write('matrix=' + json.dumps({'include': [{'role': s['role'], 'version': s['version']} for s in eligible]}) + '\n')
    return lock


def validate(lock, reports):
    sources = {s['role']: s for s in lock['upgradeSources']}
    for role in lock['testedRoles']:
        source = sources[role]
        report = json.loads((reports / (role + '.json')).read_text(encoding='utf-8-sig'))
        if (report.get('result') != 'passed' or report.get('fromVersion') != source['version']
                or report.get('toVersion') != lock['targetVersion']
                or report.get('fromManifestSha256') != source['manifestSha256']):
            raise RuntimeError('Direct upgrade report differs from the frozen source: ' + role)
    return len(lock['testedRoles'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--lock', type=Path, default=Path('direct-upgrade-lock.json'))
    parser.add_argument('--manager-ref', default=os.environ.get('MANAGER_REF', 'master'))
    parser.add_argument('--target-version', default=os.environ.get('TARGET_VERSION', ''))
    parser.add_argument('--reports', type=Path)
    parser.add_argument('--prepared', type=Path)
    args = parser.parse_args()
    if args.reports:
        count = validate(json.loads(args.lock.read_text(encoding='utf-8-sig')), args.reports)
        print(f'{count} direct upgrades passed to the exact frozen target version')
    else:
        freeze(args.manager_ref, args.target_version, args.lock, args.prepared)
