"""Only a verified stable pointer may suppress compilation of an unchanged snapshot."""
import argparse
import base64
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def previous_snapshot(manager):
    result = subprocess.run(['gh', 'api', 'repos/Corfirean/coa-server-build/contents/stable.json?ref=channels'],
                            capture_output=True, text=True)
    if result.returncode:
        try:
            missing = json.loads(result.stdout).get('status') == '404'
        except (ValueError, AttributeError):
            missing = False
        if missing:
            return ''  # Legacy bootstrap has no signed channel yet.
        raise RuntimeError('Could not read the stable pointer; refusing an unverified daily decision')
    envelope = base64.b64decode(json.loads(result.stdout)['content'])
    pointer = Path('previous-stable.json')
    pointer.write_bytes(envelope)
    subprocess.run(['cargo', 'build', '--release', '-p', 'coa-release'], cwd=manager, check=True)
    tool = Path(manager).resolve() / 'target/release/coa-release'
    if os.name == 'nt':
        tool = tool.with_suffix('.exe')
    verified = json.loads(subprocess.check_output(
        [str(tool), 'verify-channel', '--file', str(pointer.resolve()), '--channel', 'stable'], text=True))
    return verified['snapshot']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--lock', default='release-lock.json')
    parser.add_argument('--manager', required=True)
    args = parser.parse_args()
    lock = json.loads(Path(args.lock).read_text())
    previous = previous_snapshot(args.manager)
    with open(os.environ['GITHUB_OUTPUT'], 'a') as out:
        for name in ('core', 'bots', 'scaling', 'squid', 'manager'):
            out.write(name + '=' + lock['components'][name]['sha'] + '\n')
        out.write('snapshot=' + lock['snapshot'] + '\n')
        out.write('changed=' + str(previous != lock['snapshot']).lower() + '\n')
        out.write('version=0.' + datetime.now(timezone.utc).strftime('%y%m%d') + '.'
                  + str(100000 + int(os.environ['GITHUB_RUN_NUMBER'])) + '\n')


if __name__ == '__main__':
    main()
