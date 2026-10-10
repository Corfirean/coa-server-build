# Daily release rollout

The candidate pipeline runs at 01:30 UTC and has no upstream-event triggers.
It merges upstream and the latest race release into an integration branch,
resolves component SHAs and race asset digests, and builds Windows and Linux
from the same lock. A conflict blocks the candidate and preserves production.
New race SQL outside the core migration directories requires review.

Compiler caches are separated from PR caches. Windows uses pinned sccache and
embedded MSVC debug information and a compiler-version cache key; Linux persists
both BuildKit layers and ccache and uses a pinned Ubuntu image digest. Cargo
dependencies and release-tool output have separate trusted caches.
Published candidate assets are immutable. Uploads remain drafts until every
downloaded asset matches the locally verified package.

## Activation gates

These are draft implementation branches, not a production stable cutover.
Do not merge the pipeline changes until the following remaining stages are ready:

- Generate mandatory gameplay/update integration qualification reports from real
  test runs, using the exact signed upgrade fixtures in the lock.
- Run Manager recovery and login isolation against live disposable server fixtures.
- Connect independent Manager, Bots and Server changelog histories to successful
  publications, including external module release notes.
- Bootstrap the signed channels branch and wire daily automatic promotion after
  both platforms qualify.
- A released Manager supporting signed channel pointers.
- Cold/warm hosted-run measurements.

The replacement promote workflow never modifies legacy release assets. It requires
an immutable signed candidate, compatibility metadata and a qualification report.
Each mandatory gate on both platforms must report `passed` with a GitHub Actions
run link; missing and skipped gates block promotion. A signed stable pointer is
written in one Git commit based on the exact previous channels SHA. A concurrent
pointer change is rejected without forcing the ref. The channels branch must be
bootstrapped during rollout; promotion does not create it implicitly.

The hourly daily-health workflow only checks scheduled reconciliation status.
Missing or unsuccessful reconciliations for over 30 hours update one diagnostic
issue, which closes after a successful scheduled reconciliation. An active-build
skip is not counted as a successful source reconciliation. It launches no builds.

Daily packaging now binds compatibility metadata to the locked core, Companions,
Scaling, SQUID and races revisions and the race release version. Upgrade source
manifests and signatures are frozen before compilation. Packaging verifies their
exact hashes and embedded-key signatures before recording the base and two
stable source versions and database contract hashes. Signed channels history is
used after cutover; initial legacy history uses the latest earlier non-prerelease
immutable server release as the previous-version fixture. The legacy base has no
full schema contract and is identified by its signed manifest; its actual database
still requires integration qualification. Publishing requires upgrade evidence for
each declared version and signed manifest, not merely a green generic test run.
