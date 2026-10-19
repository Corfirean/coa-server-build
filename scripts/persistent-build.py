"""Preserve Ninja input timestamps only when source bytes are unchanged after checkout."""
import argparse
import hashlib
import json
import os
import time
from pathlib import Path

ROOTS = ('src', 'deps', 'modules', 'conf', 'cmake', 'tools')
EXCLUDED = {'.git', '.cache', '__pycache__', 'node_modules', 'build'}


def inputs(root):
    for name in ('CMakeLists.txt', 'PreLoad.cmake', 'acore.json'):
        path = root / name
        if path.is_file() and not path.is_symlink():
            yield path
    for name in ROOTS:
        for directory, folders, files in os.walk(root / name, followlinks=False):
            folders[:] = sorted(folder for folder in folders if folder not in EXCLUDED
                                and not Path(directory, folder).is_symlink())
            for filename in sorted(files):
                path = Path(directory, filename)
                if not path.is_symlink():
                    yield path


def prepare(root, state):
    root = root.resolve()
    previous = {}
    if state.exists():
        saved = json.loads(state.read_text(encoding='utf-8'))
        if saved.get('schema') != 1 or saved.get('root') != str(root):
            raise RuntimeError('Persistent inputs belong to a different source checkout')
        previous = saved['files']
    current = {}
    reused = changed = 0
    now = time.time_ns()
    for path in inputs(root):
        relative = path.relative_to(root).as_posix()
        with path.open('rb') as stream:
            checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
        old = previous.get(relative)
        if old and old['sha256'] == checksum:
            modified = old['mtime_ns']
            reused += 1
        else:
            modified = now
            changed += 1
        info = path.stat()
        os.utime(path, ns=(info.st_atime_ns, modified))
        current[relative] = {'sha256': checksum, 'mtime_ns': path.stat().st_mtime_ns}
    state.parent.mkdir(parents=True, exist_ok=True)
    temporary = state.with_suffix('.tmp')
    temporary.write_text(json.dumps({'schema': 1, 'root': str(root), 'files': current}), encoding='utf-8')
    temporary.replace(state)
    result = {'unchanged': reused, 'changed_or_new': changed, 'removed': len(previous.keys() - current.keys())}
    print('Persistent build inputs: ' + json.dumps(result, sort_keys=True))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--state', required=True, type=Path)
    args = parser.parse_args()
    prepare(args.root, args.state)
