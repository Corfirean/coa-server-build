"""Match Ninja's include prefix to the installed MSVC language and output encoding."""
import argparse
import os
import re
import subprocess
import tempfile
from pathlib import Path


def detect(compiler):
    with tempfile.TemporaryDirectory(prefix='coa-msvc-deps-') as directory:
        root = Path(directory)
        (root / 'probe.h').write_text('')
        (root / 'probe.cpp').write_text('#include "probe.h"\nint probe() { return 0; }\n')
        options = {}
        if os.name == 'nt':
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = subprocess.SW_HIDE
            options = {'creationflags': subprocess.CREATE_NEW_CONSOLE, 'startupinfo': startup}
        result = subprocess.run([str(compiler), '/nologo', '/showIncludes', '/c', str(root / 'probe.cpp'),
                                 '/Fo' + str(root / 'probe.obj')], cwd=root, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, check=True, **options)
        prefixes = []
        for line in result.stdout.splitlines():
            path = re.search(rb'[A-Za-z]:[\\/]', line)
            if path and line.rstrip().endswith(b'probe.h'):
                prefixes.append(line[:path.start()])
        if len(prefixes) != 1 or not prefixes[0].strip():
            raise RuntimeError('MSVC did not expose an unambiguous header dependency prefix')
        return prefixes[0]


def configure(build, prefix):
    rules = build / 'CMakeFiles' / 'rules.ninja'
    original = rules.read_bytes()
    updated, count = re.subn(rb'(?m)^msvc_deps_prefix = [^\r\n]*',
                            lambda _: b'msvc_deps_prefix = ' + prefix, original)
    if not count:
        raise RuntimeError('The generated Ninja rules have no MSVC dependency prefix')
    if updated != original:
        rules.write_bytes(updated)
    print(f'Validated MSVC dependency prefix in {count} Ninja rule set(s).')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', required=True, type=Path)
    parser.add_argument('--compiler', default='cl.exe')
    args = parser.parse_args()
    configure(args.build, detect(args.compiler))
