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
   migrations under the core repository's rules. Keep portable-character/session branches excluded unless the owner explicitly requests an experimental Portable Characters candidate. For that candidate, integrate both the Manager and core bridge, and pass `experimental_portable=true` to `build.yml`; its frozen lock records the experimental feature instead of listing those branches as excluded. Never imply stable promotion from this option.
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

When the owner requests compatibility with every previous version, run the full historical matrix against the
exact newly published candidate, not the current stable by default:

```powershell
gh workflow run direct-upgrade-tests.yml -R Corfirean/coa-server-build --ref <reviewed-pipeline-ref> `
  -f manager_ref=<candidate-locked-manager-sha> -f target_version=<candidate-version>
```

This does not promote stable or compile the server again. Preserve `direct-upgrade-lock.json` and require the final
`report` job to pass for every frozen source. Each source must have its own passing Manager transaction, database
schema/startup and preservation report; a manifest/hash audit alone is not update qualification. Report the actual
number and range of available signed Windows versions. Unknown imported installations, removed historical packages
and manually modified databases are not covered merely by a version label. Keep their limits explicit.

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

Creating a Manager release can also emit a tag-push event. The Manager release-intent guard must preserve an already published release, including its prerelease status and exact prepared assets. For a candidate, use `--prerelease --latest=false` and verify `/releases/latest` still names the prior stable Manager. If an old prepared source predates that guard, prevent its duplicate tag-triggered publishing job from overwriting the candidate; do not treat an automatic publishing run as authorization to replace prepared assets or mark the candidate stable.

After the owner explicitly approves the identified prepared candidate, dispatch `publish-prepared.yml` with its build
run ID. It verifies source-run identity, signed metadata, installer and package contents, then publishes the exact
immutable `server-<version>` candidate. It does not rebuild from moving refs or change `stable`.
The publication workflow must be present on the default branch before dispatching it:

```powershell
gh workflow run publish-prepared.yml -R Corfirean/coa-server-build -F candidate_run_id=<approved-build-run>
```

Stable promotion is the required final step of a normal owner release instruction, through `promote.yml`.
Do not ask for the same permission again or stop at the published candidate. Only an explicit candidate/prerelease
or prepare-only request stops short of stable. Obtain the current `channels` branch SHA and use
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

## Fast release checklist for the next agent

1. **Recover, do not restart.** Read this runbook and the previous handoff. Inspect the exact successful run and
   artifact expiry before scheduling any compilation. A current, verified prepared package is the release input;
   do not rebuild it just to publish it. Use `gh run view <run-id> -R Corfirean/coa-server-build --json
   status,conclusion,headSha,jobs` and inspect its actual qualification. If only a later publication failed, resume
   that stage. Never replace missing evidence with a successful-looking result.
2. **Check the local runner.** Use `gh api repos/Corfirean/coa-server-build/actions/runners` and confirm the
   `coa-persistent` Windows runner is online. On the owner's PC its existing installation is
   `C:/games/coa-build-runner`; inspect `.runner` to confirm the repository and check for an existing
   `Runner.Listener.exe` before starting it. Start an existing authorized runner hidden; never print `.credentials`
   or tokens, create a duplicate listener, change machine execution policy or run checks against production MySQL.
   On this PC production uses3307; disposable fixtures must use their own verified paths and free ports.
3. **Qualify changes locally.** Use only the applicable checks described above and retain logs against the frozen
   snapshot. Build/unit/startup/install/upgrade evidence is already produced by preparation; do not repeat the
   entire suite merely to move the channel. A relevant failure requires a fix and new candidate. Skipped local
   gameplay stays `not-run`; screenshots with mocked data do not establish compatibility or successful gameplay.
4. **Publish the compatible Manager if needed.** An already prepared Manager installer should be published from
   `prepared-manager-windows`, not rebuilt by dispatching `release.yml` again. Check `prepared-source.json` against
   the approved exact source/run/version, installer SHA-256 and `latest.json`; verify the updater signature with
   the matching released source's `src-tauri/tauri.conf.json` public key. Preserve the installer, `.sig`, `latest.json`
   and source metadata. Use the identified version/commit for the GitHub release, never a moving branch; do not
   overwrite an already published version with different bytes. Verify GitHub Latest and its `latest.json` before
   promoting a server that requires that Manager. The normal installer workflow remains for new preparation.
5. **Publish the server once.** Dispatch `publish-prepared.yml` with the approved build run ID and wait for success.
   If that exact immutable candidate already exists with matching signed assets, reuse it. Publication alone
   leaves a candidate; it does not make Manager users receive an update.
6. **Promote that exact server.** Read the current channels SHA immediately before dispatch; do not copy an old
   SHA from this document or the previous handoff. The real promotion command is:

   ```powershell
   $version = '<approved-numeric-version>'
   $previous = gh api repos/Corfirean/coa-server-build/git/ref/heads/channels --jq '.object.sha'
   gh workflow run promote.yml -R Corfirean/coa-server-build -f "version=$version" `
     -f "expected_channels_sha=$previous" -f runner=local -f check_only=false
   ```

   Record the returned run URL and wait for that specific run. Do not confuse a verification-only success with
   publication. `check_only=true` is for workflow changes or unresolved qualification concerns, not a mandatory
   extra pass before every unchanged release. A stale-parent failure means re-read the channel and inspect the
   competing change; never force the branch or replay an older promotion blindly.
7. **Confirm delivery, not just workflow success.** Inspect these independently:

   ```powershell
   gh api repos/Corfirean/coa-server-build/releases/latest --jq '{tag_name,prerelease,draft}'
   $channel = Invoke-RestMethod 'https://raw.githubusercontent.com/Corfirean/coa-server-build/channels/stable.json'
   $channel.payload | ConvertFrom-Json | Select-Object channel,version,releaseTag,snapshot
   ```

   GitHub Latest must be the exact intended server, `prerelease=false`, `draft=false`; the public signed pointer
   must name the same version/snapshot. GitHub's raw CDN can retain the prior pointer (`max-age=300`); distinguish
   that from a failed promotion and allow refresh. The GitHub contents API on `ref=channels` can confirm committed
   state while the CDN catches up. Check the actual Manager update path from a previous stable installation when
   applicable; do not tell players to reinstall just because the channel or CDN still points to an older build.
8. **Synchronize notes and hand off.** The component changelog workflows run after publication/promotion. Verify
   their success: each repository's `CHANGELOG.md` and GitHub release notes must match its reviewed
   `changelog/history.json`, containing only its own shipped changes. If needed dispatch `changelog-release.yml`
   (server) or `changelog.yml` (Manager). Do not revive the archived combined changelog generator or collect from
   moving source branches. See `changelog/GUIDE.md` for historical corrections and exact commands.
   Give the owner download/changelog/run links, actual qualification limits and whether
   the public pointer has refreshed. Player-facing release notes describe our authored changes; imported upstream
   or module changes must not be presented as our fixes. Prepare Discord text but send nothing without an explicit
   instruction to post it. Keep0.7.0 docs/screenshots awaiting review separate from a server release instruction.

Measured reference: the2026-10-19 persistent-PC verification-only run39268500611 took83 seconds with a warm cache.
That is not a cold-cache guarantee and does not include server compilation or local gameplay acceptance. Normal
promotion should reuse both tools and packages; only missing/changed verified assets need downloading.

## Persistent PC network preparation

On this PC the existing runner's `.env` also enables `ACTIONS_RUNNER_ACTION_ARCHIVE_CACHE=C:/games/coa-build-runner/action-archive-cache` and `DOTNET_SYSTEM_NET_DISABLEIPV6=1`. These are process settings, not Windows network policy changes. The official runner reads ZIP archives from `<cache>/<owner>_<repository>/<resolved-commit>.zip`; keep exact immutable commit archives and validate the ZIP before caching it. The 2026-10-21 preparation found repeated 100-second action downloads, while an isolated .NET download took 107.421 seconds normally and 1.380 seconds with IPv6 disabled. See Microsoft's [.NET IPv6 configuration](https://learn.microsoft.com/en-us/dotnet/framework/network-programming/internet-protocol-version-6) and the official [runner action manager](https://github.com/actions/runner/blob/main/src/Runner.Worker/ActionManager.cs).

Windows compilation fetches only the frozen core commit; the separate POSIX job retains full-history source verification. If network preparation needs a local Git object cache, prepare a valid detached checkout of that exact SHA while the runner is idle, before dispatching. An unborn repository is discarded by checkout and loses its cache. Never change an active checkout or use a different source revision to avoid a download. Do not restart a runner during compilation. Preserve the source lock, existing compiler outputs and actual attempt diagnostics when recovering a failed network preparation.

## Handoff between agents

Leave these facts in the current chat before stopping: pipeline branch/commit and PR; core integration branch/commit
and PR; frozen upstream/races/SQUID/companion/scaling/Manager SHAs; build run URL; artifact names and expiry; candidate
version and snapshot; verification report paths and passed/failed/unrun gates; incremental timing if actually measured;
remaining integration conflicts or prerequisites; and whether publication/promotion has been explicitly authorized.
Resume that candidate from its lock and artifacts. Do not silently advance versions or re-resolve source refs.

Store the handoff in a file as well as the chat, using this compact template:

```text
State: prepared | candidate-published | stable-promoted
Owner scope: prepare-only | candidate-only | normal release (publication + stable)
Server version / snapshot / signed manifest SHA256:
Frozen component SHAs / pipeline SHA / source PRs:
Preparation run / conclusion / artifacts / expiry / local evidence directory:
Windows build/startup/schema/fresh-install/upgrade evidence:
Applicable local acceptance: passed / failed / not-run, with logs and limitations:
Manager required version / released version / source SHA / prepared installer run+SHA256:
Publication run / immutable release URL:
Promotion run / channels commit / GitHub Latest status / public raw pointer status:
Runner status / cache location / measured scope and duration:
Remaining work / next exact command / publication or text approvals still needed:
```

For an explicitly requested upstream integration that imports module SQL outside pending migrations, pass
`allow_historical_sql=true` for the frozen candidate. Leave it false for ordinary changes. New CoA migrations
still belong in pending directories; authorize the core PR with the maintainer `sql-change-authorized` label.
