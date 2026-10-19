# Server integration, build and release

## Sources and frozen candidate

The build repository is `Corfirean/coa-server-build`; the maintained server is
`Corfirean/azerothcore-wotlk-coa`, production branch `coa-bots`. Upstream is
`jealous-sound/azerothcore-wotlk-coa:main`. Custom races come from the latest published
`ilusixn/azerothcore-wotlk-coa` release tag, including its SHA-256-verified client assets.
Companion bots are `Corfirean/mod-coa-playerbots:master`; Content Scaling is
`Corfirean/mod-coa-content-scaling:main`, including its TBC and WotLK content packs.
SQUID is `Zyth45/mod-playerbots`, highest stable numeric `v*` tag. Manager tooling is
`Corfirean/coa-server-manager:master`, pinned to a commit by the candidate lock.

1. Fetch the relevant repositories. Record exact upstream, race tag/commit, SQUID tag/commit and companion/scaling SHAs.
2. On an isolated core branch based on `origin/coa-bots`, merge the fetched upstream and race release. Resolve conflicts
   by examining both changes and their callers. Review new race SQL and convert required changes to immutable pending
   migrations under the core repository's rules. Do not merge the excluded portable-character/session branches.
   Inspect mandatory SQL shipped under module `base/` and nested `updates/` directories as well: the release
   collector does not automatically apply either location to an existing installation. Port required, reviewed
   schema/data changes into pending migrations. Keep authored snapshot ordering, ownership guards and player data;
   never replay raw character exports or replace entire tables to satisfy startup checks.
3. Verify the resulting core using its AGENTS.md and `tools/verify_all.py`. Include the updated external modules in the
   build. Publish the source branch/PR so GitHub Actions can fetch its exact commit. Source integration is not a release.
4. Run `build.yml` from the reviewed build workflow revision, supplying exact `core_ref`, `upstream_ref`, `bots_ref`,
   `scaling_ref`, `squid_ref`, `races_ref` (the reviewed release tag), `manager_ref` and `publish_candidate=false`. The source lock freezes race assets, navigation,
   representative upgrade fixtures and historical sources. Fix a failed source/integration gate; never bypass it.

Example (replace every placeholder with the recorded exact value):

```powershell
gh workflow run build.yml -R Corfirean/coa-server-build --ref <pipeline-ref> `
  -f core_ref=<core-sha> -f upstream_ref=<upstream-sha> -f bots_ref=<bots-sha> `
  -f scaling_ref=<scaling-sha> -f squid_ref=<squid-sha> -f races_ref=<race-tag> -f manager_ref=<manager-sha> `
  -F publish_candidate=false
gh run view <run-id> -R Corfirean/coa-server-build --json status,conclusion,jobs
```

## Compilation and qualification

`server-binaries.yml` runs POSIX source checks and Windows build/unit verification. `verify-server.yml` compiles the
same frozen components without packaging. A repository variable `COA_WINDOWS_RUNNER` can select a registered dedicated
runner with a JSON label array such as `["self-hosted","Windows","X64","coa-persistent"]`; the default is hosted Windows.
The dedicated runner needs PowerShell 7 on PATH, in `C:/Program Files/PowerShell/7` or `C:/tools/PowerShell/7`,
along with Visual Studio C++ tools, Boost and MySQL development files. The workflow locates PowerShell before
using its shell. Its bootstrap uses a process-scoped execution policy; the machine policy stays unchanged. On the dedicated runner Ninja outputs live outside the cleaned checkout in `RUNNER_WORKSPACE/_coa-build-state`.
Unchanged source bytes recover their previous timestamps, changed bytes invalidate outputs, and CMake refreshes the
source graph. Keep the existing optimization/debug settings and all unit tests. Do not mix static OpenSSL with the
static MySQL client that imports the same OpenSSL symbols; use compatible dynamic OpenSSL development libraries.
The compiler-prefix probe verifies localized MSVC header dependency parsing before any incremental result is trusted.

Measured on the dedicated Ryzen 7700X / 32 GB runner with 16 workers, RelWithDebInfo, `/O2`, `/Z7`,
static modules and PCH disabled (2026-10-18): the GitHub incremental build and unit step took 170.7 seconds.
A controlled change to `ScriptedCreature.h` (588 dependent objects) plus 32 C++ files across CoA, game,
scripts and SQUID produced 657 Ninja operations and passed build/unit verification in 865.0 seconds.
These measurements cover compilation and unit verification, not downloading packages or installation qualification.
Incremental build/unit verification has a 3600-second budget; a timeout fails the job and preserves diagnostics,
without skipping tests or publishing a partial result. Cold builds retain their separate budget.
A widely included header or toolchain change can still approach a full rebuild; never promise a fixed duration
for every change or skip required checks to meet a timing target.

Packaging verifies signatures and frozen fixtures, applies SQL in an isolated database, checks startup, prepares and
qualifies a clean installer, and tests representative direct Manager upgrades. The full historical upgrade matrix is
separate (`direct-upgrade-tests.yml`). Report the actual tested scope; an unrun gate is never a pass.

For an upstream integration, preflight SQL locally on a disposable copy of the exact signed base with the pinned
Manager's `extract-schema-base`, `schema-contract` and `qualify-startup` commands before the final GitHub build.
Keep a pristine fixture for retries after a failed migration; do not repair its ledger manually. Assign free ports
in the fixture's `Settings/repack.json` before startup if another local server is running. An enabled Manastorm must
log successful backend initialization as well as worldserver readiness.

When `publish_candidate=false`, the successful run stores `windows-qualified-candidate` and `windows-candidate-tool`
for 14 days. Preserve the run ID, exact lock/snapshot and qualification results in the handoff. An artifact expiring or
a failed run requires fresh preparation; do not publish an unqualified partial package.

## Publication only on owner command

If the candidate raises `minManagerVersion`, prepare the matching Manager installer as well. On the owner's release
command, publish that compatible Manager before making the server available to users. A server requiring an
unpublished Manager is not ready for stable promotion.

The Manager release workflow also supports preparation without publication:

```powershell
gh workflow run release.yml -R Corfirean/coa-server-manager --ref <manager-ref> -F publish_release=false
```

Preserve `prepared-manager-windows` (installer, updater signature, `latest.json`, source/hash metadata). On the owner's
publication command, verify those hashes/signatures and publish the exact prepared assets under `v<manager-version>`
if a compatible Manager is not already available. Never run a publishing workflow just to test installer compilation.

After the owner explicitly approves the identified prepared candidate, dispatch `publish-prepared.yml` with its build
run ID. It verifies source-run identity, signed metadata, installer and package contents, then publishes the exact
immutable `server-<version>` candidate. It does not rebuild from moving refs or change `stable`.
The publication workflow must be present on the default branch before dispatching it:

```powershell
gh workflow run publish-prepared.yml -R Corfirean/coa-server-build -F candidate_run_id=<approved-build-run>
```

Stable promotion is a separate owner command through `promote.yml`: obtain the current `channels` branch SHA and use
the exact candidate version and compare-and-swap SHA. It runs on the owner's persistent Windows PC by default
(`COA_WINDOWS_RUNNER`). Keep its runner online; `runner=hosted` explicitly selects hosted Windows when necessary.
Tools are built from the exact released Manager commit, with persistent Cargo outputs outside the cleaned checkout.
Candidate assets are reused only when their size and GitHub SHA-256 match; signatures and signed package hashes are
still verified on every promotion. The workflow does not recompile the server or repeat its successful build tests.

The package distributed by this workflow is Windows-only. Required recorded checks are source, build, unit,
auth/world startup, schema contract, fresh install, Manager update and every upgrade source declared in its signed
compatibility matrix. Linux qualification is not a prerequisite for shipping this Windows package. Interactive
gameplay and fault-injection checks are performed locally during preparation, according to the changed features;
keep their real results in qualification rather than calling unrun checks successful. Any recorded failed check
still blocks promotion. An owner exception cannot bypass the automated Windows requirements.

Before publishing, agents should run applicable local checks in disposable fixtures: login/relog after changes to
authentication or characters; companions/SQUID after bot changes; races/hidearmor/client assets after patch changes;
rollback, locked DLL, disk-full, corrupt download and SQL/startup failure after updater/recovery changes; headless
console and Manager server/bot pages after UI or startup changes. Preserve the fixture, logs and frozen snapshot in
the handoff. Never use the owner's production database or claim that screenshot mocks qualify live gameplay.

Use `check_only=true` to exercise tool/package/qualification verification locally without signing or publishing.
For example (replace version and SHA):

```powershell
gh workflow run promote.yml -R Corfirean/coa-server-build -f version=<version> `
  -f expected_channels_sha=<channels-sha> -f check_only=true
```

On a real promotion the signed pointer is switched atomically first; the same immutable GitHub release then becomes
Latest and loses its Pre-release flag. Check both and fetch the public raw pointer, allowing for GitHub CDN caching.
If the final GitHub release edit fails, the pointer may already have changed: reconcile the release metadata before
retrying with a newly fetched channels SHA. Legacy explicit snapshot approvals remain auditable, but are no longer
required merely because optional local acceptance or Linux checks were not run.

## Handoff between agents

Leave these facts in the current chat before stopping: pipeline branch/commit and PR; core integration branch/commit
and PR; frozen upstream/races/SQUID/companion/scaling/Manager SHAs; build run URL; artifact names and expiry; candidate
version and snapshot; verification report paths and passed/failed/unrun gates; incremental timing if actually measured;
remaining integration conflicts or prerequisites; and whether publication/promotion has been explicitly authorized.
Resume that candidate from its lock and artifacts. Do not silently advance versions or re-resolve source refs.

For an explicitly requested upstream integration that imports module SQL outside pending migrations, pass
`allow_historical_sql=true` for the frozen candidate. Leave it false for ordinary changes. New CoA migrations
still belong in pending directories; authorize the core PR with the maintainer `sql-change-authorized` label.
