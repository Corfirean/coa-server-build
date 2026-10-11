import json
import subprocess


def api(path):
    return json.loads(subprocess.check_output(['gh', 'api', path], encoding='utf-8'))


def component_notes(current, previous, fetch=api):
    components = current['components']
    old = previous.get('components', {})
    legacy_core = previous.get('core', {}).get('commit')
    entries = []

    def add(key, title, body):
        entries.append({'id': 'components:' + key + ':' + components[key]['sha'],
                        'source': 'build', 'repo': components[key]['repository'],
                        'date': '', 'area': 'server', 'type': 'changed',
                        'audience': 'players', 'title': title, 'body': body})

    upstream = components.get('upstream')
    before = old.get('upstream', {}).get('sha') or old.get('core', {}).get('sha') or legacy_core
    if upstream and before and before != upstream['sha']:
        repo = components['core']['repository']
        comparison = fetch(f"repos/{repo}/compare/{before}...{upstream['sha']}")
        add('upstream', f"Integrated {comparison['ahead_by']} upstream commits",
            f"{before[:8]} → {upstream['sha'][:8]}. {comparison['html_url']}")
    elif upstream:
        add('upstream', 'Included upstream revision ' + upstream['sha'][:8],
            'Previous upstream baseline is unavailable.' if not before else 'No new upstream commits.')

    for key, label in (('squid', 'SQUID Playerbots'), ('races', 'Custom races'),
                       ('bots', 'CoA Companions'), ('scaling', 'Content Scaling')):
        item = components.get(key)
        if not item:
            continue
        prior = old.get(key, {})
        if not prior and previous.get(key, {}).get('commit'):
            prior = {'sha': previous[key]['commit']}
        version = item.get('ref', item['sha'][:8])
        if version in ('main', 'master', 'coa-bots'):
            version = item['sha'][:8]
        unchanged = prior.get('sha') == item['sha']
        title = f"{label}: {version}" + (' (unchanged)' if unchanged else '')
        if prior.get('sha') and not unchanged:
            title = f"{label}: {prior.get('ref', prior['sha'][:8])} → {version}"
        body = 'Pinned revision: ' + item['sha'][:8] + '.'
        if not prior:
            body += ' Previous version was not recorded; no version transition is assumed.'
        if key in ('squid', 'races'):
            repo = 'Zyth45/squidbots-dashboard' if key == 'squid' else item['repository']
            release = fetch(f"repos/{repo}/releases/tags/{item['ref']}")
            body += ' ' + release['html_url']
            notes = (release.get('body') or '').strip()
            if notes:
                body += (' Dashboard: ' if key == 'squid' else ' Release notes: ') + notes.split('\n\n')[0][:350]
        elif prior.get('sha') and not unchanged:
            body += f" https://github.com/{item['repository']}/compare/{prior['sha']}...{item['sha']}"
        add(key, title, body)
    return entries
