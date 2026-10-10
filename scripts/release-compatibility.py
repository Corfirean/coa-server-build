import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


def matrix(manifest, lock, sources, platform):
    if platform not in ('windows-x86_64', 'linux-x86_64'):
        raise RuntimeError('Unsupported release platform')
    revisions = lock['components']
    for name in ('core', 'bots', 'scaling', 'squid', 'races'):
        if not re.fullmatch('[0-9a-f]{40}', revisions[name]['sha']):
            raise RuntimeError(f'Invalid locked revision: {name}')
    if manifest['core']['commit'] != revisions['core']['sha'] or manifest['bots']['commit'] != revisions['bots']['sha']:
        raise RuntimeError('Packaged revisions differ from the daily lock')
    version = revisions['races']['ref'].removeprefix('coa-custom-')
    if not re.fullmatch(r'\d+\.\d+(?:\.\d+)?', version):
        raise RuntimeError('Unknown custom race release version')
    versions = [source['version'] for source in sources]
    if len(versions) != 3 or len(set(versions)) != 3 or any(not re.fullmatch(r'\d+\.\d+\.\d+', v) for v in versions):
        raise RuntimeError('Three distinct upgrade sources are required: base and two stable versions')
    if sources[0]['kind'] != 'base' or any(s['kind'] != 'update' for s in sources[1:]):
        raise RuntimeError('Upgrade sources must contain a signed base and two updates')
    databases = {}
    for source in sources:
        digest = source.get('_signedManifestSha256', '')
        if not re.fullmatch('[0-9a-f]{64}', digest):
            raise RuntimeError('Signed source manifest digest is required')
        schema = next((file['sha256'] for file in source.get('files', []) if file['path'] == 'Scripts/database-schema.json'), None)
        if source['kind'] == 'update' and (not isinstance(schema, str) or not re.fullmatch('[0-9a-f]{64}', schema)):
            raise RuntimeError('Published update fixture needs a signed database schema contract')
        databases[source['version']] = {'manifestSha256': digest, 'schemaSha256': schema}
    return {'schema': 1, 'platform': platform, 'coreCommit': revisions['core']['sha'],
            'moduleCommits': {name: revisions[name]['sha'] for name in ('bots', 'scaling', 'squid', 'races')},
            'clientPatchVersion': version, 'sourceVersions': versions, 'sourceDatabases': databases}


def apply(folder, lock_path, sources_folder, platform, tool, schema_base=None):
    lock = json.loads(lock_path.read_text(encoding='utf-8-sig'))
    if [s['role'] for s in lock['upgradeSources']] != ['base', 'stable-1', 'stable-2']:
        raise RuntimeError('Invalid upgrade fixture roles')
    if schema_base is not None:
        if hashlib.sha256((schema_base / 'manifest.json').read_bytes()).hexdigest() != lock['upgradeSources'][0]['manifestSha256']:
            raise RuntimeError('Database acceptance used a different base package from the source lock')
    sources = []
    for source in lock['upgradeSources']:
        package = sources_folder / source['role']
        raw = (package / 'manifest.json').read_bytes()
        if hashlib.sha256(raw).hexdigest() != source['manifestSha256']:
            raise RuntimeError('Upgrade source changed after daily reconciliation')
        if 'channelPointer' in source:
            pointer_file = package / 'stable-pointer.json'
            pointer_file.write_text(json.dumps(source['channelPointer']), encoding='utf-8')
            pointer = json.loads(subprocess.check_output([tool, 'verify-channel', '--file', str(pointer_file), '--channel', 'stable'], text=True))
            if pointer['releaseTag'] != source['tag'] or pointer['version'] != json.loads(raw)['version']:
                raise RuntimeError('Upgrade fixture differs from its signed stable pointer')
        subprocess.run([tool, 'verify-manifest', '--dir', str(package)], check=True)
        parsed = json.loads(raw)
        parsed['_signedManifestSha256'] = hashlib.sha256(raw).hexdigest()
        sources.append(parsed)
    path = folder / 'manifest.json'
    manifest = json.loads(path.read_text(encoding='utf-8-sig'))
    compatibility = matrix(manifest, lock, sources, platform)
    manifest['compatibility'] = compatibility
    manifest['minManagerVersion'] = '0.6.13'
    path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', required=True, type=Path)
    parser.add_argument('--lock', required=True, type=Path)
    parser.add_argument('--sources', required=True, type=Path)
    parser.add_argument('--platform', required=True)
    parser.add_argument('--tool', required=True)
    parser.add_argument('--schema-base', required=True, type=Path)
    args = parser.parse_args()
    apply(args.dir, args.lock, args.sources, args.platform, args.tool, args.schema_base)
