"""Point the Modules Preview channel at a published preview release.

Writes preview.json (a pointer signed with the preview key by `coa-release sign-channel`) to the
preview-channels branch, creating that branch as an orphan when it does not exist. It never touches the
channels branch that holds the stable and edge pointers.

usage: python -I publish-preview-pointer.py --repo OWNER/NAME --pointer preview.json
"""
import argparse
import base64
import json
import subprocess

BRANCH = 'preview-channels'


def api(path, method='GET', body=None, ok_missing=False):
    args = ['gh', 'api', path, '--method', method]
    if body is not None:
        args.extend(['--input', '-'])
    result = subprocess.run(args, input=json.dumps(body) if body is not None else None,
                            text=True, capture_output=True)
    if result.returncode != 0:
        if ok_missing and ('404' in result.stderr or 'Not Found' in result.stdout):
            return None
        raise RuntimeError(f'gh api {method} {path} failed: {result.stderr.strip() or result.stdout.strip()}')
    return json.loads(result.stdout) if result.stdout.strip() else {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True)
    parser.add_argument('--pointer', required=True)
    args = parser.parse_args()
    content = open(args.pointer, 'rb').read()
    envelope = json.loads(content)
    payload = json.loads(envelope['payload'])
    if payload.get('channel') != 'preview' or not payload.get('releaseTag', '').startswith('preview-server-'):
        raise SystemExit('refusing to publish: not a preview pointer')

    blob = api(f'repos/{args.repo}/git/blobs', 'POST',
               {'encoding': 'base64', 'content': base64.b64encode(content).decode()})
    ref = api(f'repos/{args.repo}/git/ref/heads/{BRANCH}', ok_missing=True)
    parents, base_tree = [], None
    if ref:
        head = ref['object']['sha']
        parents = [head]
        base_tree = api(f'repos/{args.repo}/git/commits/{head}')['tree']['sha']
    tree_body = {'tree': [{'path': 'preview.json', 'mode': '100644', 'type': 'blob', 'sha': blob['sha']}]}
    if base_tree:
        tree_body['base_tree'] = base_tree
    tree = api(f'repos/{args.repo}/git/trees', 'POST', tree_body)
    commit = api(f'repos/{args.repo}/git/commits', 'POST', {
        'message': f"Point the Modules Preview channel at {payload['releaseTag']}",
        'tree': tree['sha'], 'parents': parents})
    if ref:
        # Fast-forward only: a concurrent publication makes this fail instead of being overwritten.
        api(f'repos/{args.repo}/git/refs/heads/{BRANCH}', 'PATCH', {'sha': commit['sha'], 'force': False})
    else:
        api(f'repos/{args.repo}/git/refs', 'POST', {'ref': f'refs/heads/{BRANCH}', 'sha': commit['sha']})
    print(f"{BRANCH}: preview.json -> {payload['releaseTag']} ({commit['sha']})")


if __name__ == '__main__':
    main()
