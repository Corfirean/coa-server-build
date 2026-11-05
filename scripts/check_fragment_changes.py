import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess


def changed_fragments(root, base, head):
    names = subprocess.check_output(['git', '-C', str(root), 'diff', '--name-only',
                                    '--diff-filter=ACMR', base, head, '--', 'changelog.d'], encoding='utf-8')
    return [name for name in names.splitlines() if name.endswith('.md')
            and Path(name).name.lower() != 'readme.md']


def check(root, base, head, parser, name):
    fragments = []
    for path in changed_fragments(root, base, head):
        text = subprocess.check_output(['git', '-C', str(root), 'show', head + ':' + path], encoding='utf-8')
        fragments.append(parser.parse_fragment(name, name, Path(path).name, text))
    return parser.report(fragments)


def main():
    args = argparse.ArgumentParser()
    args.add_argument('--root', type=Path, default=Path('.'))
    args.add_argument('--parser', type=Path, required=True)
    options = args.parse_args()
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text(encoding='utf-8'))
    base = event.get('pull_request', {}).get('base', {}).get('sha') or event.get('before', '')
    if not re.fullmatch('[0-9a-f]{40}', base) or base == '0' * 40:
        base = event['repository']['default_branch']
    subprocess.run(['git', '-C', str(options.root), 'fetch', '--no-tags', '--depth=1', 'origin', base], check=True)
    base = subprocess.check_output(['git', '-C', str(options.root), 'rev-parse', 'FETCH_HEAD'], encoding='utf-8').strip()
    spec = importlib.util.spec_from_file_location('fragment_parser', options.parser)
    parser = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = parser
    spec.loader.exec_module(parser)
    raise SystemExit(check(options.root, base, 'HEAD', parser, event['repository']['name']))


if __name__ == '__main__':
    main()
