import argparse
import base64
import hashlib
import json
import re
import subprocess
import urllib.request
from pathlib import Path

REPO = 'Corfirean/coa-server-build'
ROLES = ('base', 'stable-1', 'stable-2')


def validate_roles(sources):
    roles = [s['role'] for s in sources]
    if len(roles) < 2 or roles != ['base'] + [f'stable-{i}' for i in range(1, len(roles))]:
        raise RuntimeError('Invalid upgrade fixture roles')


def api(path):
    return json.loads(subprocess.check_output(['gh', 'api', path], text=True))


def fetch(url):
    if not url.startswith(f'https://github.com/{REPO}/releases/download/'):
        raise RuntimeError('Upgrade fixtures must come from the server release repository')
    with urllib.request.urlopen(url, timeout=120) as response:
        raw = response.read(64 * 1024 * 1024 + 1)
    if len(raw) > 64 * 1024 * 1024:
        raise RuntimeError('Upgrade manifest is too large')
    return raw


def source(release, role):
    assets = {asset['name']: asset for asset in release['assets']}
    result = {'role': role, 'tag': release['tag_name'], 'assets': {}}
    for name in ('manifest.json', 'manifest.json.sig'):
        url = assets[name]['browser_download_url']
        raw = fetch(url)
        result['assets'][name] = {'url': url, 'sha256': hashlib.sha256(raw).hexdigest()}
        if name == 'manifest.json':
            result['version'] = json.loads(raw)['version']
            result['manifestSha256'] = result['assets'][name]['sha256']
    return result


def channel(ref='channels'):
    result = subprocess.run(['gh', 'api', f'repos/{REPO}/contents/stable.json?ref={ref}'],
                            capture_output=True, text=True)
    if result.returncode:
        try:
            if json.loads(result.stdout).get('status') == '404':
                return None
        except (ValueError, AttributeError):
            pass
        raise RuntimeError('Cannot read signed stable history')
    envelope = json.loads(base64.b64decode(json.loads(result.stdout)['content']))
    pointer = json.loads(envelope['payload'])
    if not re.fullmatch(r'server-\d+\.\d+\.\d+', pointer['releaseTag']):
        raise RuntimeError('Invalid stable history tag')
    return envelope, pointer


def resolve():
    base = source(api(f'repos/{REPO}/releases/tags/base'), 'base')
    current = channel()
    stable_tag = current[1]['releaseTag'] if current else 'stable'
    stable = source(api(f'repos/{REPO}/releases/tags/{stable_tag}'), 'stable-1')
    if current:
        stable['channelPointer'] = current[0]
    # Preserve every published source, rather than forgetting it after two releases.
    # Legacy movable tags are frozen by manifest digest just like immutable tags.
    releases = []
    page = 1
    while True:
        batch = api(f'repos/{REPO}/releases?per_page=100&page={page}')
        releases.extend(r for r in batch if not r['draft'] and (
            re.fullmatch(r'server-\d+\.\d+\.\d+', r['tag_name']) or r['tag_name'] in ('stable', 'edge')))
        if len(batch) < 100:
            break
        page += 1
    known = {base['version']: base, stable['version']: stable}
    for release in releases:
        if release['tag_name'] == stable_tag:
            continue
        item = source(release, 'pending')
        if not re.fullmatch(r'\d+\.\d+\.\d+', item['version']):
            raise RuntimeError('Published source has an invalid version')
        old = known.get(item['version'])
        if old and old['manifestSha256'] != item['manifestSha256']:
            raise RuntimeError('Different signed packages share source version ' + item['version'])
        known.setdefault(item['version'], item)
    remaining = sorted((s for v, s in known.items() if v not in (base['version'], stable['version'])),
                       key=lambda s: tuple(map(int, s['version'].split('.'))), reverse=True)
    result = [base, stable] + remaining
    for index, item in enumerate(result[1:], 1):
        item['role'] = f'stable-{index}'
    return result


def download(lock, folder):
    sources = lock['upgradeSources']
    validate_roles(sources)
    for item in sources:
        package = folder / item['role']
        package.mkdir(parents=True, exist_ok=True)
        for name in ('manifest.json', 'manifest.json.sig'):
            asset = item['assets'][name]
            target = package / name
            if target.exists():
                if hashlib.sha256(target.read_bytes()).hexdigest() != asset['sha256']:
                    raise RuntimeError(f'Existing locked fixture changed: {item["role"]}/{name}')
                continue
            raw = fetch(asset['url'])
            if hashlib.sha256(raw).hexdigest() != asset['sha256']:
                raise RuntimeError(f'Locked upgrade fixture changed: {item["role"]}/{name}')
            target.write_bytes(raw)


def download_part(url, target, size, digest):
    if not url.startswith(f'https://github.com/{REPO}/releases/download/'):
        raise RuntimeError('Upgrade archive must come from the server release repository')
    if target.exists():
        actual = hashlib.sha256()
        with target.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                actual.update(block)
        if target.stat().st_size == size and actual.hexdigest() == digest:
            return
        raise RuntimeError(f'Existing upgrade archive failed verification: {target.name}')
    temporary = target.with_name(target.name + '.partial')
    created = False
    try:
        checksum = hashlib.sha256()
        count = 0
        with urllib.request.urlopen(url, timeout=120) as response, temporary.open('xb') as output:
            created = True
            while block := response.read(1024 * 1024):
                count += len(block)
                if count > size:
                    raise RuntimeError(f'Upgrade archive exceeds signed size: {target.name}')
                checksum.update(block)
                output.write(block)
        if count != size or checksum.hexdigest() != digest:
            raise RuntimeError(f'Upgrade archive failed verification: {target.name}')
        temporary.replace(target)
    finally:
        if created:
            temporary.unlink(missing_ok=True)


def download_packages(lock, folder, tool, role=None):
    download(lock, folder)
    if role is not None and role not in [s['role'] for s in lock['upgradeSources']]:
        raise RuntimeError('Unknown upgrade fixture role')
    for item in lock['upgradeSources']:
        if role is not None and item['role'] != role:
            continue
        package = folder / item['role']
        # Parse archive paths only after the Manager validates the manifest signature and structure.
        subprocess.run([str(tool), 'verify-manifest', '--dir', str(package)], check=True)
        manifest = json.loads((package / 'manifest.json').read_text(encoding='utf-8-sig'))
        if manifest['version'] != item['version']:
            raise RuntimeError('Locked upgrade version does not match its signed manifest')
        expected_kind = 'base' if item['role'] == 'base' else 'update'
        if manifest['kind'] != expected_kind or not manifest.get('archive', {}).get('parts'):
            raise RuntimeError('Upgrade fixture has the wrong package kind or no archives')
        parts = manifest['archive']['parts']
        names = set()
        for part in parts:
            name = part['name']
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', name) or name in names:
                raise RuntimeError('Invalid upgrade archive name')
            names.add(name)
            if not isinstance(part['size'], int) or part['size'] <= 0 or not re.fullmatch(r'[0-9a-f]{64}', part['sha256']):
                raise RuntimeError('Invalid signed upgrade archive size or hash')
        base_url = item['assets']['manifest.json']['url'].rsplit('/', 1)[0] + '/'
        for part in parts:
            download_part(base_url + part['name'], package / part['name'], part['size'], part['sha256'])
        subprocess.run([str(tool), 'verify-upgrade-fixture', '--dir', str(package)], check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--lock', type=Path, required=True)
    parser.add_argument('--download', type=Path)
    parser.add_argument('--packages', action='store_true')
    parser.add_argument('--tool', type=Path)
    parser.add_argument('--role', help='Download archives only for this frozen source; manifests remain complete')
    args = parser.parse_args()
    lock = json.loads(args.lock.read_text(encoding='utf-8-sig'))
    if args.download:
        if args.packages:
            if not args.tool:
                parser.error('--packages requires --tool')
            download_packages(lock, args.download, args.tool.resolve(), args.role)
        else:
            download(lock, args.download)
    else:
        if args.packages:
            parser.error('--packages requires --download')
        lock['upgradeSources'] = resolve()
        args.lock.write_text(json.dumps(lock, indent=2) + '\n', encoding='utf-8')
