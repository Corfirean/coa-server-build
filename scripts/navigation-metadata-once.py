"""Correct only the minimum Manager on an identical, fully qualified navigation payload."""
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
from pathlib import Path

REPO = 'Corfirean/coa-server-build'
SOURCE = '0.261012.800007'
VERSION = '0.261012.800008'
SOURCE_MANIFEST = '67a77cceb2d7fd9333c2b213e998acaa7ec1f1d7b00d4cc06289fd170836f899'


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(*args):
    subprocess.run([str(arg) for arg in args], check=True)


def prepare(tool):
    old = Path('_old')
    run('gh', 'release', 'download', 'server-' + SOURCE, '--repo', REPO, '--dir', old)
    if digest(old / 'manifest.json') != SOURCE_MANIFEST:
        raise RuntimeError('Qualified source manifest changed')
    run(tool, 'verify', '--dir', old)
    metadata = module('release-metadata')
    metadata.validate(old)
    manifest = read(old / 'manifest.json')
    report = read(old / 'qualification.json')
    lock = read(old / 'release-lock.json')
    if manifest['version'] != SOURCE or not report['navigationOnly']['binariesAndSqlUnchanged']:
        raise RuntimeError('Not the exact qualified navigation payload')
    source_snapshot = lock['snapshot']
    out = Path('_out')
    out.mkdir()
    for part in manifest['archive']['parts']:
        (old / part['name']).rename(out / part['name'])
    lock['components']['build'].update(sha=os.environ['GITHUB_SHA'], ref=os.environ['GITHUB_SHA'])
    lock['snapshot'] = module('daily-release').snapshot(lock['components'])
    manifest['version'] = VERSION
    manifest['minManagerVersion'] = module('release-compatibility').minimum_manager('0.6.15')
    compatibility = manifest['compatibility']
    # A briefly published source also remains supported. Its archive and schema are identical.
    compatibility['sourceVersions'].append(SOURCE)
    compatibility['sourceDatabases'][SOURCE] = {
        'manifestSha256': SOURCE_MANIFEST,
        'schemaSha256': next(file['sha256'] for file in manifest['files'] if file['path'] == 'Scripts/database-schema.json')}
    report.update(version=VERSION, snapshot=lock['snapshot'])
    for check in report['platforms']['windows-x86_64'].values():
        if check.get('result') == 'passed':
            check['qualifiedVersion'] = SOURCE
    report['metadataOnly'] = {'qualifiedVersion': SOURCE, 'qualifiedManifestSha256': SOURCE_MANIFEST,
                              'qualifiedSnapshot': source_snapshot, 'qualificationRun': '38182065657',
                              'archiveFilesMigrationsAndPoliciesUnchanged': True,
                              'changedFields': ['version', 'minManagerVersion', 'compatibility.sourceVersions', 'releaseMetadata'],
                              'reason': 'Preserve the optimized Manager requirement; no server payload changed'}
    matrix = {'schema': 1, 'version': VERSION, 'snapshot': lock['snapshot'],
              'minManagerVersion': manifest['minManagerVersion'], 'platforms': {'windows-x86_64': compatibility}}
    for name, value in [('release-lock.json', lock), ('qualification.json', report), ('compatibility-matrix.json', matrix)]:
        (out / name).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    manifest['releaseMetadata'] = {name: digest(out / name) for name in metadata.FILES}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    original = read(old / 'manifest.json')
    if any(manifest[key] != original[key] for key in ('archive', 'files', 'migrations', 'core', 'bots')):
        raise RuntimeError('Metadata correction changed server payload or update policies')
    metadata.validate(out)
    run(tool, 'sign', '--dir', out)
    run(tool, 'verify', '--dir', out)


def promote(tool, expected):
    folder = Path('_downloaded')
    module('release-metadata').validate(folder)
    manifest = read(folder / 'manifest.json')
    report = read(folder / 'qualification.json')
    if manifest['version'] != VERSION or manifest['minManagerVersion'] != '0.6.15' or report['metadataOnly']['qualifiedManifestSha256'] != SOURCE_MANIFEST:
        raise RuntimeError('Correction authorization does not match')
    run(tool, 'verify', '--dir', folder)
    if module('upgrade-sources').channel()[1]['version'] != '0.261011.800006':
        raise RuntimeError('Previous stable advanced')
    manager = json.loads(subprocess.check_output(['gh', 'release', 'view', 'v0.6.15', '--repo', 'Corfirean/coa-server-manager', '--json', 'isDraft,isPrerelease,assets'], text=True))
    names = {asset['name'] for asset in manager['assets']}
    if manager['isDraft'] or manager['isPrerelease'] or 'latest.json' not in names or not any(name.endswith('.exe.sig') for name in names):
        raise RuntimeError('Optimized Manager is not publicly available')
    pointer = folder / 'stable-pointer.json'
    run(tool, 'sign-channel', '--channel', 'stable', '--version', VERSION, '--snapshot', report['snapshot'], '--out', pointer)
    run(tool, 'verify-channel', '--file', pointer, '--channel', 'stable')
    module('promote-channel').publish(REPO, expected, pointer.read_bytes())
    run('gh', 'release', 'edit', 'server-' + VERSION, '--repo', REPO, '--prerelease=false')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=('prepare', 'promote'))
    parser.add_argument('--tool', required=True)
    parser.add_argument('--expected')
    args = parser.parse_args()
    if args.stage == 'prepare': prepare(args.tool)
    else: promote(args.tool, args.expected)
