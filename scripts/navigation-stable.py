"""One-time navigation-only stable release, explicitly requested by the maintainer."""
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import tarfile
from pathlib import Path, PurePosixPath

REPO = 'Corfirean/coa-server-build'
VERSION = '0.261012.800007'
PREVIOUS = '0.261011.800006'
PREVIOUS_MANIFEST = 'c18c58d1f82f627c7e5fb466583a86b7bfd4f5253283c3df35e2b03ac2aafb3b'
NAVIGATION_MANIFEST = '7f28600735f115792e79a5e8d1c8d78a83a8f5ed14a090c6d87268e49c2bb683'


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def run(*args):
    subprocess.run([str(a) for a in args], check=True)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def extract_previous(package, tree):
    import zstandard
    manifest = read(package / 'manifest.json')
    if manifest['version'] != PREVIOUS or sha(package / 'manifest.json') != PREVIOUS_MANIFEST:
        raise RuntimeError('Navigation-only release must extend the approved stable package')
    entries = {f['path']: f for f in manifest['files']}
    if len(manifest['archive']['parts']) != 1:
        raise RuntimeError('Unexpected previous stable archive layout')
    seen = set()
    with (package / manifest['archive']['parts'][0]['name']).open('rb') as compressed:
        with zstandard.ZstdDecompressor().stream_reader(compressed) as stream:
            with tarfile.open(fileobj=stream, mode='r|') as tar:
                for item in tar:
                    name = item.name.removeprefix('./')
                    if item.isdir():
                        continue
                    path = PurePosixPath(name)
                    if not item.isfile() or name not in entries or name in seen or path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name:
                        raise RuntimeError('Invalid previous stable archive path')
                    expected = entries[name]
                    if item.size != expected['size']:
                        raise RuntimeError('Previous archive entry size differs from signed manifest')
                    destination = tree / path
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    h = hashlib.sha256()
                    with tar.extractfile(item) as source, destination.open('xb') as target:
                        while block := source.read(1024 * 1024):
                            h.update(block)
                            target.write(block)
                    if h.hexdigest() != expected['sha256']:
                        raise RuntimeError('Previous stable file checksum mismatch')
                    seen.add(name)
    if seen != set(entries):
        raise RuntimeError('Previous stable archive is incomplete')
    return manifest


def prepare(tool):
    previous = Path('_sources/stable-1')
    tree = Path('_tree')
    tree.mkdir()
    run(tool, 'verify', '--dir', previous)
    manifest = extract_previous(previous, tree)
    navigation = read('navigation-source.json')
    if navigation['manifestSha256'] != NAVIGATION_MANIFEST:
        raise RuntimeError('Navigation identity differs from the approved candidate')
    components = {
        'core': {'repository': 'Corfirean/azerothcore-wotlk-coa', 'sha': manifest['core']['commit'], 'ref': manifest['core']['commit']},
        'bots': {'repository': 'Corfirean/mod-coa-playerbots', 'sha': manifest['bots']['commit'], 'ref': manifest['bots']['commit']},
        'scaling': {'repository': 'Corfirean/mod-coa-content-scaling', 'sha': 'de2003f210955c4048e627adf302d89280c606a0', 'ref': 'de2003f210955c4048e627adf302d89280c606a0'},
        'squid': {'repository': 'Zyth45/mod-playerbots', 'sha': 'e0d64ad06d878501f20d41001a5414c39643533f', 'ref': 'v2.0'},
        'races': {'repository': 'ilusixn/azerothcore-wotlk-coa', 'sha': 'e69c0bf748633c1820c8a2bba415ed5915d86f27', 'ref': 'coa-custom-1.5.1'},
        'upstream': {'repository': 'jealous-sound/azerothcore-wotlk-coa', 'sha': '8f1f175e5e48c0106e75b8245694b0d3ba28c1ef', 'ref': '8f1f175e5e48c0106e75b8245694b0d3ba28c1ef'},
        'manager': {'repository': 'Corfirean/coa-server-manager', 'sha': os.environ['MANAGER_SHA'], 'ref': os.environ['MANAGER_SHA']},
        'build': {'repository': REPO, 'sha': os.environ['GITHUB_SHA'], 'ref': os.environ['GITHUB_SHA']},
        'navigation': navigation,
    }
    lock = read('_release-lock/release-lock.json')
    lock.update(schema=1, components=components, snapshot=module('daily-release').snapshot(components),
                excludedBranches=['feat/portable-characters', 'feat/portable-session-bridge'])
    Path('_release-lock/release-lock.json').write_text(json.dumps(lock, indent=2))
    module('restore-navigation').restore(navigation, tree, Path('_navigation-download'))
    # Every existing binary, SQL script and config remains byte-identical to released stable.
    for entry in manifest['files']:
        if sha(tree / entry['path']) != entry['sha256']:
            raise RuntimeError('Navigation release changed a previously released file: ' + entry['path'])
    run(tool, 'pack-base', '--tree', tree, '--out', '_out', '--version', VERSION,
        '--core-commit', manifest['core']['commit'], '--bots-commit', manifest['bots']['commit'])
    packed = read('_out/manifest.json')
    packed.update(kind='update', migrations=manifest['migrations'], minManagerVersion='0.6.13')
    # Preserve all existing policies and compatible migration checksums, not just the SQL text.
    policies = {f['path']: f for f in manifest['files']}
    for entry in packed['files']:
        if entry['path'] in policies:
            entry.update(policies[entry['path']])
    Path('_out/manifest.json').write_text(json.dumps(packed, indent=2))
    module('release-compatibility').apply(Path('_out'), Path('_release-lock/release-lock.json'), Path('_sources'),
                                       'windows-x86_64', tool, Path('_sources/base'))
    run(tool, 'sign', '--dir', '_out')
    run(tool, 'verify', '--dir', '_out')


def finalize(tool):
    folder = Path('_out')
    manifest = read(folder / 'manifest.json')
    lock = read('_release-lock/release-lock.json')
    evidence = module('release-metadata')
    current_run = os.environ['GITHUB_RUN_ID']
    checks = {gate: {'result': 'not-run'} for gate in module('promote-channel').GATES | {'build'}}
    checks.update(evidence.evidence_steps(REPO, '38144636048', {
        'source': 'Verify source and harness infrastructure on POSIX',
        'build': 'Build worldserver and authserver', 'unit': 'Build worldserver and authserver'}))
    checks.update(evidence.evidence_steps(REPO, current_run, {
        'schema-contract': 'Qualify Manager upgrades with the new navigation set',
        'auth-startup': 'Qualify Manager upgrades with the new navigation set',
        'world-startup': 'Qualify Manager upgrades with the new navigation set',
        'manager-update': 'Qualify Manager upgrades with the new navigation set'}))
    for source in lock['upgradeSources']:
        report = read('_upgrade-reports/' + source['role'] + '.json')
        if report['result'] != 'passed' or report['toVersion'] != VERSION or report['fromVersion'] != source['version']:
            raise RuntimeError('Navigation upgrade qualification did not pass the exact source')
        gate = 'upgrade-' + source['role']
        checks[gate] = dict(checks['manager-update'], fromVersion=source['version'],
                            fromManifestSha256=source['manifestSha256'], fromSchemaSha256=report.get('fromSchemaSha256'))
    qualification = {'schema': 1, 'snapshot': lock['snapshot'], 'version': VERSION,
                     'archive': manifest['archive'], 'platforms': {'windows-x86_64': checks},
                     'navigationOnly': {'previousVersion': PREVIOUS, 'previousManifestSha256': PREVIOUS_MANIFEST,
                                        'navigationManifestSha256': NAVIGATION_MANIFEST,
                                        'maintainerRequestedStableWithoutGameplayQualification': True,
                                        'gameplay': 'not-run', 'linux': 'not-run',
                                        'binariesAndSqlUnchanged': True}}
    matrix = {'schema': 1, 'snapshot': lock['snapshot'], 'version': VERSION,
              'minManagerVersion': manifest['minManagerVersion'],
              'platforms': {'windows-x86_64': manifest['compatibility']}}
    for name, value in [('release-lock.json', lock), ('qualification.json', qualification), ('compatibility-matrix.json', matrix)]:
        (folder / name).write_text(json.dumps(value, indent=2) + '\n')
    manifest['releaseMetadata'] = {name: sha(folder / name) for name in evidence.FILES}
    (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    evidence.validate(folder)
    run(tool, 'sign', '--dir', folder)
    run(tool, 'verify', '--dir', folder)


def promote(tool, expected):
    # This scoped authorization does not weaken the ordinary release gates or authorize other candidates.
    folder = Path('_downloaded')
    module('release-metadata').validate(folder)
    report = read(folder / 'qualification.json')
    approved = report.get('navigationOnly', {})
    if report['version'] != VERSION or approved.get('previousManifestSha256') != PREVIOUS_MANIFEST or approved.get('navigationManifestSha256') != NAVIGATION_MANIFEST or not approved.get('binariesAndSqlUnchanged'):
        raise RuntimeError('One-time navigation promotion authorization does not match')
    run(tool, 'verify', '--dir', folder)
    current = module('upgrade-sources').channel()
    if current[1]['version'] != PREVIOUS:
        raise RuntimeError('Stable has advanced; do not overwrite it')
    pointer = folder / 'stable-pointer.json'
    run(tool, 'sign-channel', '--channel', 'stable', '--version', VERSION,
        '--snapshot', report['snapshot'], '--out', pointer)
    run(tool, 'verify-channel', '--file', pointer, '--channel', 'stable')
    module('promote-channel').publish(REPO, expected, pointer.read_bytes())
    run('gh', 'release', 'edit', 'server-' + VERSION, '--repo', REPO, '--prerelease=false')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=('prepare', 'finalize', 'promote'))
    parser.add_argument('--tool', required=True)
    parser.add_argument('--expected')
    args = parser.parse_args()
    if args.stage == 'prepare': prepare(args.tool)
    elif args.stage == 'finalize': finalize(args.tool)
    else: promote(args.tool, args.expected)
