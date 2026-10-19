import argparse
import json
import os
import subprocess
from pathlib import Path


def validate(run, repo, lock):
    if (run.get('repository', {}).get('full_name') != repo
            or run.get('head_repository', {}).get('full_name') != repo
            or run.get('path') != '.github/workflows/build.yml'
            or run.get('event') != 'workflow_dispatch'
            or run.get('status') != 'completed' or run.get('conclusion') != 'success'):
        raise RuntimeError('Publication requires a successful manual build in this repository')
    if lock['components']['build']['sha'] != run['head_sha']:
        raise RuntimeError('Prepared candidate belongs to another workflow revision')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True, type=int)
    parser.add_argument('--lock', required=True, type=Path)
    args = parser.parse_args()
    repo = os.environ['GITHUB_REPOSITORY']
    run = json.loads(subprocess.check_output(['gh', 'api', f'repos/{repo}/actions/runs/{args.run}'], text=True))
    validate(run, repo, json.loads(args.lock.read_text(encoding='utf-8-sig')))
