import argparse
import base64
import json
import re
import subprocess
from pathlib import Path

GATES = {'source', 'unit', 'auth-startup', 'world-startup', 'schema-contract',
         'upgrade-base', 'upgrade-stable-1', 'upgrade-stable-2', 'login-relog',
         'companions', 'squid', 'races-enabled', 'races-disabled', 'hidearmor',
         'client-assets', 'manager-update', 'rollback-interruption', 'locked-dll',
         'disk-full', 'corrupt-download', 'sql-failure', 'startup-failure',
         'headless-console', 'server-bots-pages'}


def api(path, method='GET', body=None):
    args = ['gh', 'api', path, '--method', method]
    if body is not None:
        args.extend(['--input', '-'])
    result = subprocess.run(args, input=json.dumps(body) if body is not None else None,
                            text=True, check=True, capture_output=True)
    return json.loads(result.stdout)


def validate_report(report, snapshot, version, source_versions=None, source_databases=None):
    if report.get('schema') != 1 or report.get('snapshot') != snapshot or report.get('version') != version:
        raise RuntimeError('Qualification report does not match the candidate')
    for platform in ('windows-x86_64', 'linux-x86_64'):
        checks = report.get('platforms', {}).get(platform, {})
        for name in GATES | {'build'}:
            check = checks.get(name, {})
            if check.get('result') != 'passed' or not re.fullmatch(r'https://github\.com/[^/]+/[^/]+/actions/runs/\d+(?:/.*)?', check.get('evidence', '')):
                raise RuntimeError(f'Mandatory qualification missing or unsuccessful: {platform}/{name}')
        if source_versions is not None:
            if len(source_versions) != 3:
                raise RuntimeError('Three upgrade sources must qualify')
            for name, source in zip(('upgrade-base', 'upgrade-stable-1', 'upgrade-stable-2'), source_versions):
                if checks[name].get('fromVersion') != source:
                    raise RuntimeError(f'Upgrade qualification differs from compatibility matrix: {platform}/{name}')
                if source_databases is not None:
                    expected = source_databases[source]
                    if (checks[name].get('fromManifestSha256') != expected['manifestSha256']
                            or checks[name].get('fromSchemaSha256') != expected['schemaSha256']):
                        raise RuntimeError(f'Upgrade tested a different signed source: {platform}/{name}')


def publish(repo, expected, envelope):
    if not re.fullmatch(r'[0-9a-f]{40}', expected):
        raise RuntimeError('An exact previous channels commit is required')
    ref = api(f'repos/{repo}/git/ref/heads/channels')
    if ref['object']['sha'] != expected:
        raise RuntimeError('Channels changed during qualification; refusing stale promotion')
    previous = api(f'repos/{repo}/git/commits/{expected}')
    blob = api(f'repos/{repo}/git/blobs', 'POST', {
        'encoding': 'base64', 'content': base64.b64encode(envelope).decode()})
    tree = api(f'repos/{repo}/git/trees', 'POST', {'base_tree': previous['tree']['sha'],
        'tree': [{'path': 'stable.json', 'mode': '100644', 'type': 'blob', 'sha': blob['sha']}]})
    commit = api(f'repos/{repo}/git/commits', 'POST', {
        'message': 'Promote verified immutable server release', 'tree': tree['sha'], 'parents': [expected]})
    # A competing update makes this commit a sibling, so GitHub rejects it as non-fast-forward.
    return api(f'repos/{repo}/git/refs/heads/channels', 'PATCH', {
        'sha': commit['sha'], 'force': False})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--expected', required=True)
    parser.add_argument('--dir', required=True, type=Path)
    parser.add_argument('--tool', required=True)
    args = parser.parse_args()
    folder = args.dir
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8-sig'))
    lock = json.loads((folder / 'release-lock.json').read_text(encoding='utf-8-sig'))
    if manifest['version'] != args.version or not manifest.get('compatibility'):
        raise RuntimeError('Candidate version or compatibility matrix is missing')
    if manifest['compatibility']['platform'] != 'windows-x86_64':
        raise RuntimeError('Stable requires a signed Windows package')
    if manifest['compatibility']['coreCommit'] != lock['components']['core']['sha']:
        raise RuntimeError('Compatibility matrix differs from the source lock')
    for name in ('bots', 'scaling', 'squid', 'races'):
        if manifest['compatibility']['moduleCommits'].get(name) != lock['components'][name]['sha']:
            raise RuntimeError(f'Module compatibility differs from source lock: {name}')
    validate_report(json.loads((folder / 'qualification.json').read_text()), lock['snapshot'], args.version,
                    manifest['compatibility']['sourceVersions'], manifest['compatibility']['sourceDatabases'])
    subprocess.run([args.tool, 'verify', '--dir', str(folder)], check=True)
    pointer = folder / 'stable-pointer.json'
    subprocess.run([args.tool, 'sign-channel', '--channel', 'stable', '--version', args.version,
                    '--snapshot', lock['snapshot'], '--out', str(pointer)], check=True)
    publish(args.repo, args.expected, pointer.read_bytes())


if __name__ == '__main__':
    main()
