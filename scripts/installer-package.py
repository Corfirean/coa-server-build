import argparse
import hashlib
import json
import shutil
from pathlib import Path
from migration_evidence import validate as validate_migrations


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def validate_identity(installer, candidate):
    if installer['kind'] != 'base' or candidate['kind'] != 'update':
        raise RuntimeError('A full base image and a server update are required')
    for key in ('version', 'core', 'bots'):
        if installer.get(key) != candidate.get(key):
            raise RuntimeError('Installation image differs from server release: ' + key)
    paths = {file['path'] for file in installer['files']}
    if not {'Settings/database.bootstrap.json', 'Settings/install-source.json',
            'Scripts/database-schema.json', 'Core/worldserver.exe', 'Core/authserver.exe'} <= paths:
        raise RuntimeError('Installation image is missing required runtime or database provenance')
    for prefix in ('mysql/data/', 'Data/', 'Runtime/'):
        if not any(path.startswith(prefix) for path in paths):
            raise RuntimeError('Installation image is incomplete: ' + prefix)


def prepare(installer, candidate):
    manifest = read(installer / 'manifest.json')
    release = read(candidate / 'manifest.json')
    validate_identity(manifest, release)
    if (installer / 'manifest.json.sig').exists():
        raise RuntimeError('Prepare the installation image before signing it')
    for part in manifest['archive']['parts']:
        name = part['name']
        if Path(name).name != name or any(char in name for char in ('/', '\\')) or name.startswith('install-'):
            raise RuntimeError('Unexpected installation archive name')
        source = installer / name
        if source.stat().st_size != part['size'] or digest(source) != part['sha256']:
            raise RuntimeError('Installation archive is incomplete or changed')
        target = installer / ('install-' + name)
        if target.exists():
            raise RuntimeError('Installation archive destination already exists')
        source.rename(target)
        part['name'] = target.name
    manifest['minManagerVersion'] = release['minManagerVersion']
    manifest['compatibility'] = release['compatibility']
    (installer / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')


def embed(installer, candidate, report):
    manifest = read(installer / 'manifest.json')
    release = read(candidate / 'manifest.json')
    validate_identity(manifest, release)
    evidence = read(report)
    if (evidence.get('result') != 'passed' or evidence.get('version') != manifest['version']
            or evidence.get('manifestSha256') != digest(installer / 'manifest.json')):
        raise RuntimeError('Clean installation did not qualify these exact package bytes')
    validate_migrations(evidence, release)
    files = {'install-manifest.json': installer / 'manifest.json',
             'install-manifest.json.sig': installer / 'manifest.json.sig',
             'install-qualification.json': report}
    for part in manifest['archive']['parts']:
        name = part['name']
        if Path(name).name != name or any(char in name for char in ('/', '\\')) or not name.startswith('install-'):
            raise RuntimeError('Installation archive must have its own asset name')
        source = installer / name
        if source.stat().st_size != part['size'] or digest(source) != part['sha256']:
            raise RuntimeError('Installation archive changed after qualification')
        files[name] = source
    for name, source in files.items():
        if (candidate / name).exists():
            raise RuntimeError('Installation asset already exists: ' + name)
        shutil.copyfile(source, candidate / name)
    release.setdefault('releaseMetadata', {}).update({name: digest(candidate / name)
        for name in ('install-manifest.json', 'install-manifest.json.sig', 'install-qualification.json')})
    (candidate / 'manifest.json').write_text(json.dumps(release, indent=2) + '\n', encoding='utf-8')


def validate(folder):
    release = read(folder / 'manifest.json')
    manifest = read(folder / 'install-manifest.json')
    validate_identity(manifest, release)
    for name in ('install-manifest.json', 'install-manifest.json.sig', 'install-qualification.json'):
        if release.get('releaseMetadata', {}).get(name) != digest(folder / name):
            raise RuntimeError('Installation asset is missing or changed: ' + name)
    report = read(folder / 'install-qualification.json')
    if (report.get('result') != 'passed' or report.get('version') != release['version']
            or report.get('manifestSha256') != digest(folder / 'install-manifest.json')):
        raise RuntimeError('Installation qualification does not match the signed image')
    validate_migrations(report, release)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('prepare', 'embed'))
    parser.add_argument('--installer', required=True, type=Path)
    parser.add_argument('--candidate', required=True, type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if args.mode == 'prepare':
        prepare(args.installer, args.candidate)
    else:
        embed(args.installer, args.candidate, args.report)
