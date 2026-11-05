import json
import os
import sys
from pathlib import Path


def summary(data):
    stats = data['stats']
    hits = sum(stats['cache_hits']['counts'].values())
    misses = sum(stats['cache_misses']['counts'].values())
    requests = stats['compile_requests']
    unsupported = stats['requests_not_cacheable']
    rate = 100 * hits / (hits + misses) if hits + misses else 0
    overall = 100 * hits / requests if requests else 0
    return (f'Compiler cache: {hits} hits, {misses} misses, {unsupported} non-cacheable calls.\n\n'
            f'Hit rate: {rate:.1f}% of cacheable calls; {overall:.1f}% of all calls.\n\n'
            f'Non-cacheable reasons: {json.dumps(stats.get("not_cached", {}), sort_keys=True)}\n')


if __name__ == '__main__':
    message = summary(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig')))
    print(message)
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as output:
        output.write(message)
