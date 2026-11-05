"""Write Core/plugins/recommended.json for a Modules Preview release.

The preview core loads Content Scaling, Companions and SQUID's Playerbots (with Dungeon Clear) as plugins
instead of having them built in. The Manager builds them on the server's PC before the first start; this
file names the exact commits the stable release it is made from was built and qualified with.

usage: python -I preview-recommended.py <stable release-lock.json> <out recommended.json>
"""
import json
import re
import sys

SHA = re.compile(r'^[0-9a-f]{40}$')


def pin(components, name):
    c = components[name]
    sha = c.get('sha', '')
    if not SHA.match(sha):
        raise SystemExit(f'{name}: no exact commit in the release lock')
    return c['repository'], sha


def main():
    lock = json.load(open(sys.argv[1], encoding='utf-8'))
    c = lock['components']
    scaling_repo, scaling = pin(c, 'scaling')
    squid_repo, squid = pin(c, 'squid')
    dc_repo, dc = pin(c, 'dungeon-clear')
    bots_repo, bots = pin(c, 'bots')
    recommended = {
        'schema': 1,
        'modules': [
            {'id': 'content-scaling', 'repo': scaling_repo, 'commit': scaling,
             'bundled': [{'path': 'content-packs/mod-coa-tbc-content'},
                         {'path': 'content-packs/mod-coa-wotlk-content'}]},
            # SQUID only where the owner had it switched on; the stable release's validation patches only
            # affect CI startup checks (CoA.ValidationMode) and are not part of the player build.
            {'id': 'playerbots', 'repo': squid_repo, 'commit': squid,
             'bundled': [{'repo': dc_repo, 'commit': dc}],
             'when': 'config:playerbots.conf:AiPlayerbot.Enabled=1'},
            {'id': 'companions', 'repo': bots_repo, 'commit': bots, 'when': 'unless:playerbots'},
        ],
    }
    with open(sys.argv[2], 'w', encoding='utf-8', newline='\n') as f:
        json.dump(recommended, f, indent=1)
        f.write('\n')
    print(json.dumps(recommended, indent=1))


if __name__ == '__main__':
    main()
