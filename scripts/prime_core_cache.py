import json
import os
from pathlib import Path
import re
import subprocess


REPOSITORY = 'https://github.com/Corfirean/azerothcore-wotlk-coa'


def git(root, *args):
    result = subprocess.run(['git', '-C', str(root), '-c', 'core.commitGraph=false', *args],
                            capture_output=True, encoding='utf-8')
    if result.returncode:
        raise RuntimeError('Core cache validation failed: ' + result.stderr.strip())
    return result.stdout.strip()


def complete_history(root, sha):
    git(root, 'cat-file', '-e', sha + '^{commit}')
    if git(root, 'rev-parse', '--is-shallow-repository') != 'false':
        raise RuntimeError('Core cache history is shallow; SQL ordering requires complete history')
    objects = git(root, 'rev-list', '--objects', '--missing=print', sha)
    if any(line.startswith('?') for line in objects.splitlines()):
        raise RuntimeError('Core cache has missing reachable objects')


def exact_checkout(root, sha):
    if git(root, 'rev-parse', 'HEAD') != sha:
        raise RuntimeError('Core cache checkout differs from the frozen SHA')
    if git(root, 'remote', 'get-url', 'origin').rstrip('/').removesuffix('.git') != REPOSITORY:
        raise RuntimeError('Core cache checkout belongs to a different repository')
    if git(root, 'status', '--porcelain', '--untracked-files=all') or git(root, 'clean', '-n', '-d', '-x'):
        raise RuntimeError('Core cache checkout contains changed or untracked inputs')
    complete_history(root, sha)


def prime(cache, workspace, sha):
    if not re.fullmatch('[0-9a-f]{40}', sha):
        raise RuntimeError('An immutable core SHA is required')
    workspace = Path(workspace).resolve()
    target = (workspace / '_core').resolve()
    if target.parent != workspace:
        raise RuntimeError('Core cache target escaped the workspace')
    if not cache or not Path(cache).exists():
        return False
    if target.exists():
        exact_checkout(target, sha)
        return True
    complete_history(Path(cache), sha)
    result = subprocess.run(['git', 'clone', '--shared', '--no-checkout', str(cache), str(target)],
                            capture_output=True, encoding='utf-8')
    if result.returncode:
        raise RuntimeError('Local core cache preparation failed: ' + result.stderr.strip())
    git(target, 'remote', 'set-url', 'origin', REPOSITORY)
    git(target, 'config', 'core.commitGraph', 'false')
    git(target, 'checkout', '--detach', sha)
    exact_checkout(target, sha)
    return True


if __name__ == '__main__':
    ready = prime(os.environ.get('CORE_OBJECT_CACHE'), os.environ['GITHUB_WORKSPACE'], os.environ['CORE_SHA'])
    with Path(os.environ['GITHUB_OUTPUT']).open('a', encoding='utf-8') as output:
        output.write('ready=' + str(ready).lower() + '\n')
    print(json.dumps({'exactCompleteCoreCache': ready, 'sha': os.environ['CORE_SHA']}))
