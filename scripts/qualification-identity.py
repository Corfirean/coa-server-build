"""Bind a successful upgrade report to the exact signed candidate tested by its job."""
import argparse
import hashlib
import json
from pathlib import Path


def bind(candidate, report_path, expected):
    actual = hashlib.sha256((candidate / 'manifest.json').read_bytes()).hexdigest()
    if not expected or actual != expected:
        raise RuntimeError('Candidate changed during upgrade qualification')
    report = json.loads(report_path.read_text(encoding='utf-8-sig'))
    manifest = json.loads((candidate / 'manifest.json').read_text(encoding='utf-8-sig'))
    if report.get('result') != 'passed' or report.get('toVersion') != manifest['version']:
        raise RuntimeError('Upgrade report did not qualify this candidate')
    report['candidateManifestSha256'] = actual
    report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--expected', required=True)
    args = parser.parse_args()
    bind(args.candidate, args.report, args.expected)
