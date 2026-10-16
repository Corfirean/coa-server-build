import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
from pathlib import Path


FILES = ('release-lock.json', 'qualification.json', 'compatibility-matrix.json')
WINDOWS_GATES = {'source', 'build', 'unit', 'schema-contract', 'auth-startup', 'world-startup',
                 'upgrade-base', 'upgrade-stable-1', 'upgrade-stable-2', 'manager-update', 'fresh-install'}
LINUX_GATES = {'build', 'schema-contract', 'binary-version', 'module-config-layout'}


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def api(path):
    return json.loads(subprocess.check_output(['gh', 'api', path], text=True))


def evidence_steps(repo, run_id, step_names):
    jobs = api(f'repos/{repo}/actions/runs/{run_id}/jobs?per_page=100')['jobs']
    evidence = {}
    for gate, step_name in step_names.items():
        matches = [(job, step) for job in jobs for step in job.get('steps', [])
                   if step['name'] == step_name and step['conclusion'] == 'success']
        if len(matches) != 1:
            raise RuntimeError('Missing or ambiguous successful step: ' + step_name)
        job, step = matches[0]
        evidence[gate] = {'result': 'passed', 'evidence': job['html_url'] + '#step:' + str(step['number']) + ':1'}
    return evidence


def collect(folder, lock_path, platform, reports, binary_run):
    manifest = read(folder / 'manifest.json')
    lock = read(lock_path)
    if manifest.get('compatibility', {}).get('platform') != platform:
        raise RuntimeError('Compatibility matrix is missing or for a different platform')
    repo, run_id = os.environ['GITHUB_REPOSITORY'], os.environ['GITHUB_RUN_ID']
    spec = importlib.util.spec_from_file_location('promotion', Path(__file__).with_name('promote-channel.py'))
    promotion = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(promotion)
    checks = {name: {'result': 'not-run'} for name in promotion.GATES | {'build'}}
    if platform == 'windows-x86_64':
        checks.update(evidence_steps(repo, binary_run or run_id, {
            'source': 'Verify source and harness infrastructure on POSIX',
            'build': 'Build worldserver and authserver', 'unit': 'Build worldserver and authserver'}))
        checks.update(evidence_steps(repo, run_id, {
            'schema-contract': 'Apply release SQL on an isolated database and capture the expected schema',
            'auth-startup': 'Start auth and world from the candidate in a disposable isolated server',
            'world-startup': 'Start auth and world from the candidate in a disposable isolated server',
            'manager-update': 'Qualify representative direct Manager upgrades',
            'fresh-install': 'Build and qualify full clean installation'}))
        if binary_run:
            checks.update(evidence_steps(repo, run_id, {
                'sql-only-binary-reuse': 'Validate verified binaries and SQL-only source delta'}))
        for source in lock['upgradeSources']:
            report = read(reports / (source['role'] + '.json'))
            if (report['result'] != 'passed' or report['toVersion'] != manifest['version']
                    or report['fromVersion'] != source['version']
                    or report['fromManifestSha256'] != source['manifestSha256']):
                raise RuntimeError('Upgrade evidence differs from frozen source: ' + source['role'])
            gate = 'upgrade-' + source['role']
            expected_database = manifest['compatibility']['sourceDatabases'][source['version']]
            if report['fromSchemaSha256'] != expected_database['schemaSha256']:
                raise RuntimeError('Upgrade tested a different database schema: ' + source['role'])
            checks[gate] = dict(checks['manager-update'], fromVersion=report['fromVersion'],
                                fromManifestSha256=report['fromManifestSha256'],
                                fromSchemaSha256=report['fromSchemaSha256'])
    else:
        checks.update(evidence_steps(repo, run_id, {
            'build': 'Compile in Docker',
            'schema-contract': 'Apply release SQL on an isolated database and capture the expected schema',
            'binary-version': 'Smoke test the binaries (in a clean Ubuntu 26.04 with only the runtime libraries)',
            'module-config-layout': 'Smoke test the final archive, configuration is read from the package layout'}))
    folder.joinpath('release-lock.json').write_bytes(lock_path.read_bytes())
    qualification = {'schema': 1, 'snapshot': lock['snapshot'], 'version': manifest['version'],
                     'archive': manifest['archive'], 'platforms': {platform: checks}}
    if binary_run:
        qualification['binaryProvenance'] = {'run': binary_run, 'core': os.environ['BINARY_CORE_SHA'],
                                             'changes': 'sql-only'}
    matrix = {'schema': 1, 'snapshot': lock['snapshot'], 'version': manifest['version'],
              'minManagerVersion': manifest['minManagerVersion'],
              'platforms': {platform: manifest['compatibility']}}
    for name, value in [('qualification.json', qualification), ('compatibility-matrix.json', matrix)]:
        folder.joinpath(name).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    manifest.setdefault('releaseMetadata', {}).update({name: digest(folder / name) for name in FILES})
    folder.joinpath('manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    validate(folder)


def validate(folder):
    manifest = read(folder / 'manifest.json')
    hashes = manifest.get('releaseMetadata', {})
    for name in FILES:
        if not folder.joinpath(name).is_file() or hashes.get(name) != digest(folder / name):
            raise RuntimeError('Missing or changed release metadata: ' + name)
    lock, report, matrix = [read(folder / name) for name in FILES]
    spec = importlib.util.spec_from_file_location('daily', Path(__file__).with_name('daily-release.py'))
    daily = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daily)
    if lock.get('schema') != 1 or lock.get('snapshot') != daily.snapshot(lock['components']):
        raise RuntimeError('Invalid source snapshot')
    for value in (report, matrix):
        if value.get('schema') != 1 or value.get('snapshot') != lock.get('snapshot') or value.get('version') != manifest['version']:
            raise RuntimeError('Release metadata belongs to another candidate')
    if report['archive'] != manifest['archive']:
        raise RuntimeError('Qualification belongs to different archive bytes')
    platform = manifest['compatibility']['platform']
    if matrix['platforms'].get(platform) != manifest['compatibility'] or matrix['minManagerVersion'] != manifest['minManagerVersion']:
        raise RuntimeError('Standalone compatibility differs from signed manifest')
    frozen_sources = lock.get('upgradeSources', [])
    if frozen_sources and manifest['compatibility'].get('sourceVersions') != [s['version'] for s in frozen_sources]:
        raise RuntimeError('Compatibility omits or changes a frozen upgrade source')
    if manifest['core']['commit'] != lock['components']['core']['sha'] or manifest['bots']['commit'] != lock['components']['bots']['sha']:
        raise RuntimeError('Release differs from source lock')
    for name in ('bots', 'scaling', 'squid', 'races'):
        if manifest['compatibility'].get('moduleCommits', {}).get(name) != lock['components'][name]['sha']:
            raise RuntimeError('Module differs from source lock: ' + name)
    if report.get('binaryProvenance'):
        if report['platforms'][platform].get('sql-only-binary-reuse', {}).get('result') != 'passed':
            raise RuntimeError('Reused binaries lack SQL-only verification')
    required = WINDOWS_GATES if platform == 'windows-x86_64' else LINUX_GATES
    if platform == 'windows-x86_64':
        sources = manifest['compatibility'].get('sourceVersions', [])
        required = required | {f'upgrade-stable-{i}' for i in range(1, len(sources))}
    for gate in required:
        check = report['platforms'].get(platform, {}).get(gate, {})
        if check.get('result') != 'passed' or not check.get('evidence', '').startswith('https://github.com/'):
            raise RuntimeError('Candidate qualification missing: ' + gate)
    if platform == 'windows-x86_64':
        for source in frozen_sources:
            gate = 'upgrade-' + source['role']
            check = report['platforms'][platform].get(gate, {})
            database = manifest['compatibility']['sourceDatabases'][source['version']]
            if (check.get('fromVersion') != source['version']
                    or check.get('fromManifestSha256') != source['manifestSha256']
                    or check.get('fromSchemaSha256') != database['schemaSha256']):
                raise RuntimeError('Upgrade evidence differs from frozen source: ' + gate)
    if platform == 'windows-x86_64':
        spec = importlib.util.spec_from_file_location('installer', Path(__file__).with_name('installer-package.py'))
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        installer.validate(folder)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', required=True, type=Path)
    parser.add_argument('--lock', type=Path)
    parser.add_argument('--platform', choices=('windows-x86_64', 'linux-x86_64'))
    parser.add_argument('--reports', type=Path, default=Path('_upgrade-reports'))
    parser.add_argument('--binary-run', default='')
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    if args.verify:
        validate(args.dir)
    else:
        collect(args.dir, args.lock, args.platform, args.reports, args.binary_run)
