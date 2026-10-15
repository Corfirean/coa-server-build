import importlib.util
import json
import os
from pathlib import Path


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def freeze(path):
    refs = {name: os.environ[name.upper() + '_REF'] for name in ('core', 'bots', 'scaling', 'squid', 'manager')}
    daily = load('daily-release')
    if path.exists():
        lock = json.loads(path.read_text(encoding='utf-8-sig'))
        if lock.get('schema') != 1 or lock.get('snapshot') != daily.snapshot(lock['components']):
            raise RuntimeError('Shared source snapshot failed validation')
        for name, ref in refs.items():
            if ref != lock['components'][name]['sha']:
                raise RuntimeError('Inputs differ from shared snapshot: ' + name)
        if not lock.get('upgradeSources'):
            raise RuntimeError('Shared snapshot has no frozen upgrade sources')
    else:
        lock = daily.resolve(refs['core'], refs['manager'], refs['bots'], refs['scaling'], refs['squid'],
                             upstream_ref=os.environ.get('UPSTREAM_REF') or 'main')
        daily.check_integration(lock)
        lock['upgradeSources'] = load('upgrade-sources').resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(lock, indent=2) + '\n', encoding='utf-8')
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
        for name in refs:
            output.write(name + '=' + lock['components'][name]['sha'] + '\n')
        output.write('snapshot=' + lock['snapshot'] + '\n')


if __name__ == '__main__':
    freeze(Path('_release-lock/release-lock.json'))
