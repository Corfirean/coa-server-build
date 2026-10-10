# Daily release rollout

The candidate pipeline runs at 01:30 UTC and has no upstream-event triggers.
It merges upstream and the latest race release into an integration branch,
resolves component SHAs and race asset digests, and builds Windows and Linux
from the same lock. A conflict blocks the candidate and preserves production.
New race SQL outside the core migration directories requires review.

Compiler caches are separated from PR caches. Windows uses pinned sccache and
embedded MSVC debug information; Linux persists both BuildKit layers and ccache.
Published candidate assets are immutable. Uploads remain drafts until every
downloaded asset matches the locally verified package.

## Activation gates

This is the first implementation stage, not a production stable cutover.
Do not merge the pipeline changes until the following remaining stages are ready:

- Compatibility matrix and mandatory gameplay/update integration fixtures.
- Manager automatic rollback with restored-server health checks and login isolation.
- Independent Manager, Bots and Server changelog release histories.
- Signed channel publication with compare-and-swap, both-platform success gate,
  and stale-run monitoring.
- A released Manager supporting signed channel pointers.
- Cold/warm hosted-run measurements and pinned Linux image digest.

The existing promote workflow still mutates legacy releases and must be replaced
before enabling automatic stable. These drafts intentionally do not switch stable.
