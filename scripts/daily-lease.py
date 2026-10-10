"""Acquire one daily candidate with an atomic, non-forced Git ref update."""
import json
import os
import subprocess

REF = 'heads/automation/daily-lease'


class ApiError(RuntimeError):
    def __init__(self, status):
        self.status = status
        super().__init__(f'GitHub lease request failed ({status})')


def api(path, method='GET', body=None):
    command = ['gh', 'api', path, '--method', method]
    if body is not None:
        command += ['--input', '-']
    result = subprocess.run(command, input=json.dumps(body) if body is not None else None,
                            capture_output=True, text=True)
    if result.returncode:
        try:
            status = int(json.loads(result.stdout)['status'])
        except (ValueError, KeyError, TypeError):
            status = 0
        raise ApiError(status)
    return json.loads(result.stdout)


def acquire(repo, run_id, source_sha):
    prefix = f'repos/{repo}'
    try:
        previous = api(f'{prefix}/git/ref/{REF}')['object']['sha']
    except ApiError as error:
        if error.status != 404:
            raise
        previous = None
    if previous:
        holder = api(f'{prefix}/git/commits/{previous}')
        message = json.loads(holder['message'])
        if message.get('schema') != 1 or message.get('repository') != repo:
            raise RuntimeError('Unknown daily lease format')
        owner = int(message['runId'])
        if owner == int(run_id):
            return True
        status = api(f'{prefix}/actions/runs/{owner}')['status']
        if status != 'completed':
            return False
        parent = previous
        tree = holder['tree']['sha']
    else:
        parent = source_sha
        tree = api(f'{prefix}/git/commits/{source_sha}')['tree']['sha']
    commit = api(f'{prefix}/git/commits', 'POST', {
        'message': json.dumps({'schema': 1, 'repository': repo, 'runId': int(run_id)}),
        'tree': tree, 'parents': [parent]})['sha']
    try:
        if previous:
            api(f'{prefix}/git/refs/{REF}', 'PATCH', {'sha': commit, 'force': False})
        else:
            api(f'{prefix}/git/refs', 'POST', {'ref': 'refs/' + REF, 'sha': commit})
    except ApiError as error:
        if error.status not in (409, 422):
            raise
        # Only a confirmed competing ref update is a normal skip. Other failures block.
        winner = api(f'{prefix}/git/ref/{REF}')['object']['sha']
        if winner == commit:
            return True
        if winner != previous:
            return False
        raise
    return True


def main():
    if not acquire(os.environ['GITHUB_REPOSITORY'], os.environ['GITHUB_RUN_ID'], os.environ['GITHUB_SHA']):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
            output.write('skip=true\n')
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
            summary.write('Skipped: another run owns the daily candidate lease.\n')


if __name__ == '__main__':
    main()
