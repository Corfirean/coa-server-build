"""Only a verified stable pointer may suppress compilation of an unchanged snapshot."""
import argparse
import base64
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def previous_channel(manager):
    result = subprocess.run(['gh', 'api', 'repos/Corfirean/coa-server-build/contents/stable.json?ref=channels'],
                            capture_output=True, text=True)
    if result.returncode:
        try:
            missing = json.loads(result.stdout).get('status') == '404'
        except (ValueError, AttributeError):
            missing = False
        if missing:
            return None  # Legacy bootstrap has no signed channel yet.
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
    return verified


def previous_snapshot(manager):
    channel = previous_channel(manager)
    return channel['snapshot'] if channel else ''


def next_version(date, run_number, previous, tags):
    prefix = (0, int(date))
    floor = 100000 + int(run_number)
    if previous:
        major, day, revision = map(int, previous['version'].split('.'))
        prefix = max(prefix, (major, day))
        if prefix == (major, day):
            floor = max(floor, revision + 1)
    for tag in tags:
        match = re.fullmatch(r'server-(\d+)\.(\d+)\.(\d+)', tag)
        if match:
            major, day, revision = map(int, match.groups())
            if (major, day) == prefix:
                floor = max(floor, revision + 1)
    return f'{prefix[0]}.{prefix[1]}.{floor}'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--lock', default='release-lock.json')
    parser.add_argument('--manager', required=True)
    args = parser.parse_args()
    lock = json.loads(Path(args.lock).read_text())
    channel = previous_channel(args.manager)
    previous = channel['snapshot'] if channel else ''
    tags = subprocess.check_output(['gh', 'api', 'repos/Corfirean/coa-server-build/releases',
                                    '--paginate', '--jq', '.[].tag_name'], text=True).splitlines()
    version = next_version(datetime.now(timezone.utc).strftime('%y%m%d'),
                           os.environ['GITHUB_RUN_NUMBER'], channel, tags)
    with open(os.environ['GITHUB_OUTPUT'], 'a') as out:
        for name in ('core', 'bots', 'scaling', 'squid', 'manager'):
            out.write(name + '=' + lock['components'][name]['sha'] + '\n')
        out.write('snapshot=' + lock['snapshot'] + '\n')
        out.write('changed=' + str(previous != lock['snapshot']).lower() + '\n')
        out.write('version=' + version + '\n')


if __name__ == '__main__':
    main()
