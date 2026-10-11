import json
import os
import re
import subprocess


def api(path):
    return json.loads(subprocess.check_output(['gh', 'api', path], encoding='utf-8'))


def validate_delta(comparison):
    files = comparison.get('files', [])
    if comparison.get('status') not in ('ahead', 'identical') or len(files) >= 300:
        raise RuntimeError('Source comparison is divergent or incomplete')
    for file in files:
        if not file['filename'].startswith('data/sql/updates/pending_db_') or not file['filename'].endswith('.sql'):
            raise RuntimeError('Reusing binaries requires exclusively incremental SQL changes')
        if file.get('previous_filename') and not file['previous_filename'].startswith('data/sql/updates/pending_db_'):
            raise RuntimeError('A non-SQL input was renamed')


def main():
    repo = os.environ['GITHUB_REPOSITORY']
    run = os.environ['RUN_ID']
    jobs = api(f'repos/{repo}/actions/runs/{run}/jobs?per_page=100')['jobs']
    for name in ('binaries / source', 'binaries / build'):
        if not any(j['name'] == name and j['conclusion'] == 'success' for j in jobs):
            raise RuntimeError('The selected run lacks successful source and binary verification')
    pins = {'core_sha': os.environ['NEW_CORE'], 'bots_sha': os.environ['BOTS'],
            'scaling_sha': os.environ['SCALING'],
            'squid_sha': api('repos/Zyth45/mod-playerbots/commits/' + os.environ['SQUID'])['sha']}
    for sha in [os.environ['OLD_CORE'], *pins.values()]:
        if not re.fullmatch('[0-9a-f]{40}', sha):
            raise RuntimeError('Exact source SHAs are required')
    log = subprocess.check_output(['gh', 'run', 'view', run, '--repo', repo, '--log'], encoding='utf-8')
    for label, sha in (('core commit:', os.environ['OLD_CORE']), ('bots commit:', pins['bots_sha']),
                       ('scaling commit:', pins['scaling_sha']), ('squid_sha=', pins['squid_sha'])):
        if not re.search(re.escape(label) + r'\s*' + sha + r'\b', log):
            raise RuntimeError('Verified run does not match the requested component pins: ' + label)
    validate_delta(api('repos/Corfirean/azerothcore-wotlk-coa/compare/' + os.environ['OLD_CORE'] + '...' + pins['core_sha']))
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
        for key, value in pins.items():
            output.write(key + '=' + value + '\n')


if __name__ == '__main__':
    main()
