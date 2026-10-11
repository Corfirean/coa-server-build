"""Restore a frozen, hash-verified navigation set into the release tree."""
import argparse
import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path, PurePosixPath


def restore(component, tree, downloads):
    spec = importlib.util.spec_from_file_location('sources', Path(__file__).with_name('upgrade-sources.py'))
    sources = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sources)
    downloads.mkdir(parents=True, exist_ok=True)
    for part in component['assets']:
        sources.download_part(part['url'], downloads / part['name'], part['size'], part['sha256'])
    archive = downloads / 'navigation.zip'
    checksum = hashlib.sha256()
    with archive.open('xb') as output:
        for part in component['assets']:
            with (downloads / part['name']).open('rb') as source:
                while block := source.read(1024 * 1024):
                    output.write(block)
                    checksum.update(block)
    if checksum.hexdigest() != component['archiveSha256']:
        raise RuntimeError('Navigation archive identity differs from the lock')
    with zipfile.ZipFile(archive) as z:
        raw = z.read('navigation-manifest.json')
        if hashlib.sha256(raw).hexdigest() != component['manifestSha256']:
            raise RuntimeError('Navigation manifest differs from the lock')
        manifest = json.loads(raw.decode('utf-8-sig'))
        if manifest['core'] != component['sha']:
            raise RuntimeError('Navigation generator revision differs from the lock')
        expected = {'Data/' + name for name in manifest['files']}
        actual = [i.filename for i in z.infolist() if i.filename.startswith('Data/')]
        if set(actual) != expected or len(actual) != len(expected):
            raise RuntimeError('Navigation archive inventory differs from its manifest')
        for name, digest in manifest['files'].items():
            relative = PurePosixPath(name)
            if relative.is_absolute() or '..' in relative.parts or '\\' in name or ':' in name or relative.parts[0] not in ('maps', 'vmaps', 'mmaps'):
                raise RuntimeError('Unsafe navigation path')
            target = tree / 'Data' / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            h = hashlib.sha256()
            with z.open('Data/' + name) as source, target.open('wb') as output:
                while block := source.read(1024 * 1024):
                    h.update(block)
                    output.write(block)
            if h.hexdigest() != digest:
                raise RuntimeError('Navigation payload checksum mismatch: ' + name)
        (tree / 'Scripts').mkdir(parents=True, exist_ok=True)
        (tree / 'Scripts/navigation-manifest.json').write_bytes(raw)
    # Large intermediate downloads are not needed after all payload hashes pass.
    for path in [archive, *(downloads / p['name'] for p in component['assets'])]:
        path.unlink()
    print(f'Restored {len(manifest["files"])} verified navigation files')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--lock', required=True, type=Path)
    parser.add_argument('--tree', required=True, type=Path)
    parser.add_argument('--download', required=True, type=Path)
    args = parser.parse_args()
    lock = json.loads(args.lock.read_text(encoding='utf-8-sig'))
    restore(lock['components']['navigation'], args.tree, args.download)
