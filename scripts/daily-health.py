import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def api(path):
    return json.loads(subprocess.check_output(['gh', 'api', path], text=True))


def main():
    repo = os.environ['GITHUB_REPOSITORY']
    runs = api(f'repos/{repo}/actions/workflows/daily-status.yml/runs?per_page=100')['workflow_runs']
    successful = []
    for run in runs:
        if run['event'] != 'schedule':
            continue
        jobs = api(f'repos/{repo}/actions/runs/{run["id"]}/jobs?per_page=100')['jobs']
        for job in jobs:
            if job['name'] == 'resolve' and job['conclusion'] == 'success':
                steps = {step['name']: step['conclusion'] for step in job['steps']}
                if steps.get('Resolve and check daily snapshot') == 'success':
                    successful.append(datetime.fromisoformat(job['completed_at'].replace('Z', '+00:00')))
        if successful:
            break
    stale = not successful or (datetime.now(timezone.utc) - max(successful)).total_seconds() > 30 * 3600
    issues = api(f'repos/{repo}/issues?state=open&labels=daily-health&per_page=100')
    issue = next((item for item in issues if item['title'] == 'Daily reconciliation overdue' and 'pull_request' not in item), None)
    if stale:
        report = Path(os.environ.get('RUNNER_TEMP', '.')) / 'daily-health.md'
        last = max(successful).isoformat() if successful else 'No successful scheduled reconciliation found.'
        report.write_text(f'No successful scheduled source reconciliation within 30 hours.\n\nLast success: {last}\n\nPrevious stable remains available. Inspect https://github.com/{repo}/actions/workflows/daily-status.yml\n', encoding='utf-8')
        subprocess.run(['gh', 'label', 'create', 'daily-health', '--repo', repo, '--color', 'D93F0B', '--force'], check=True)
        command = ['gh', 'issue', 'edit', str(issue['number'])] if issue else ['gh', 'issue', 'create', '--title', 'Daily reconciliation overdue', '--label', 'daily-health']
        subprocess.run(command + ['--repo', repo, '--body-file', str(report)], check=True)
    elif issue:
        subprocess.run(['gh', 'issue', 'close', str(issue['number']), '--repo', repo], check=True)
    print('Daily reconciliation overdue' if stale else 'Daily reconciliation healthy')


if __name__ == '__main__':
    main()
