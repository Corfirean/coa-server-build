"""Reuse exact GitHub release assets on the persistent local runner."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


def matches(path, asset):
    if not path.is_file() or path.stat().st_size != asset['size']:
        return False
    digest = asset.get('digest') or ''
    # Without an API checksum, download again. Package verification afterwards
    # also checks signatures and the hashes recorded in the signed manifests.
    if not re.fullmatch(r'sha256:[a-f0-9]{64}', digest):
        return False
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest() == digest[7:]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--cache', required=True, type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9]+(?:\.[0-9]+)+', args.version):
        raise RuntimeError('An exact numeric server version is required')
    tag = 'server-' + args.version
    release = json.loads(subprocess.check_output(
        ['gh', 'api', f'repos/{args.repo}/releases/tags/{tag}'], text=True))
    if release['tag_name'] != tag or release['draft']:
        raise RuntimeError('Candidate must be an already published immutable release')
    folder = args.cache.resolve() / tag
    folder.mkdir(parents=True, exist_ok=True)
    for asset in release['assets']:
        name = asset['name']
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', name):
            raise RuntimeError('Unsafe release asset name')
        target = folder / name
        if matches(target, asset):
            print('Reusing verified asset:', name, flush=True)
            continue
        subprocess.run(['gh', 'release', 'download', tag, '--repo', args.repo,
                        '--pattern', name, '--dir', str(folder), '--clobber'], check=True)
        if target.stat().st_size != asset['size'] or (asset.get('digest') and not matches(target, asset)):
            raise RuntimeError('Downloaded asset differs from release: ' + name)
        print('Downloaded asset:', name, flush=True)
    print('Candidate cache:', folder, flush=True)


if __name__ == '__main__':
    main()
