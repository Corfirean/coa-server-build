import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess

repo = os.environ['GITHUB_REPOSITORY']
version = '0.261011.800006'
spec = importlib.util.spec_from_file_location('channel', Path(__file__).with_name('promote-channel.py'))
channel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(channel)
run = channel.api(f'repos/{repo}/actions/runs/38160121004')
if run['conclusion'] != 'success':
    raise RuntimeError('Windows release qualification did not succeed')
manifest_bytes = Path('candidate/manifest.json').read_bytes()
manifest = json.loads(manifest_bytes)
if manifest['version'] != version:
    raise RuntimeError('Unexpected candidate version')
for role, expected in [('base', '0.2.0'), ('stable-1', '0.261010.32'), ('stable-2', '0.261006.1')]:
    reports = list(Path('qualification').rglob(role + '.json'))
    if len(reports) != 1:
        raise RuntimeError('Missing upgrade evidence: ' + role)
    report = json.loads(reports[0].read_text())
    if report['result'] != 'passed' or report['fromVersion'] != expected or report['toVersion'] != version:
        raise RuntimeError('Incorrect upgrade evidence: ' + role)
tool = '_manager/target/release/coa-release'
subprocess.run([tool, 'verify', '--dir', 'candidate'], check=True)
pointer = Path('stable-pointer.json').resolve()
subprocess.run([tool, 'sign-channel', '--channel', 'stable', '--version', version,
                '--snapshot', hashlib.sha256(manifest_bytes).hexdigest(), '--out', str(pointer)], check=True)
subprocess.run([tool, 'verify-channel', '--channel', 'stable', '--file', str(pointer)], check=True)
refs = channel.api(f'repos/{repo}/git/matching-refs/heads/channels')
if refs:
    if len(refs) != 1 or refs[0]['ref'] != 'refs/heads/channels':
        raise RuntimeError('Ambiguous channel branch')
    expected = refs[0]['object']['sha']
else:
    expected = channel.api(f'repos/{repo}/git/ref/heads/main')['object']['sha']
    channel.api(f'repos/{repo}/git/refs', 'POST', {'ref': 'refs/heads/channels', 'sha': expected})
channel.publish(repo, expected, pointer.read_bytes())
subprocess.run(['gh', 'release', 'edit', 'server-' + version, '--repo', repo, '--prerelease=false',
                '--title', 'CoA Server ' + version], check=True)
print('Windows stable published with user-authorized one-time exception; Linux and gameplay gates remain unqualified.')
