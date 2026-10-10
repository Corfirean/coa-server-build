# coa-server-build

Build and release pipeline for **CoA Server Manager** packages.

| Release tag | What it holds | Who reads it |
|---|---|---|
| `base` | Base install package (server files, clean databases, game data) | "Install new server" |
| `edge` | Latest nightly cumulative update (prerelease) | anyone testing new builds |
| `stable` | The promoted update | every Manager, by default |
| `linux-unsigned` | Experimental Linux build, **not signed** | the repository owner, who signs it |

Each release carries `manifest.json`, `manifest.json.sig` (Ed25519, checked by the app against its built-in public key)
and the archive parts (`*.tar.zst.NNN`, below GitHub's 2 GiB asset limit).

## Workflows
* **build** - nightly + manual. Compiles [the fork](https://github.com/Corfirean/azerothcore-wotlk-coa) with
  [mod-coa-playerbots](https://github.com/Corfirean/mod-coa-playerbots) and unchanged
  [SQUID Playerbots](https://github.com/Zyth45/mod-playerbots/tree/coa) on Windows, builds a cumulative update against the
  `base` manifest, signs it, publishes it to `edge`. Versions are `0.YYMMDD.<run>`.
* **build-linux** - manual, **experimental**. Compiles the same fork, bots module, SQUID and Content Scaling on Linux inside
  Docker (`docker/Dockerfile.linux`, Ubuntu 26.04), lays the files out with `scripts/assemble-tree.sh`, applies the release
  SQL to the data directory of the signed `base` package in a MySQL container (the Manager's `coa-release`, same checks as
  the Windows job), adds the resulting databases as `Database/baseline` and publishes an
  **unsigned** package to `linux-unsigned`. The SQL is read from checkouts with Windows line endings
  (`scripts/crlf-checkout.sh`): the checksums recorded in the base are those of CRLF files. It has no access to the signing key and does not touch `edge`, `stable` or
  `base`. Signing and promoting it is a separate, manual step for the repository owner.
* **promote** - manual. Copies `edge` to `stable`.
* **sync-fork** - hourly. Mirrors upstream `main` into the fork and merges it into `coa-bots`; a conflict opens an issue.

The `squid_ref` build input defaults to `latest-release`, selecting the highest stable numeric `v*` tag.
Both jobs use its exact resolved commit; an explicit branch, tag or commit still overrides this.
`Extras/SquidPlayerbots/release.json` records the tag and commit for the Manager and diagnostics.
When the selected release supplies `conf/playerbots.conf.settings.json`, it is copied unchanged next to
`playerbots.conf.dist`. The Manager accepts its format-1 settings/groups, including types, bounds, descriptions,
`default` and the separate `default_if_missing`. Older releases without this file use the existing controls.
SQUID is disabled on fresh installs. Its SQL is skipped entirely while `AiPlayerbot.Enabled` is off.
This requires the matching core module-loader change before these launcher updates are released.
The launcher rejects configurations that enable both bot systems,
including starts from batch files. It provisions `acore_playerbots` using the existing repack credentials
and imports the module's shipped SQL before the first world start. Applied files are recorded in each
database's `coa_squid_migrations` table and never repeated; a changed applied migration stops startup.
On imported installations, the installer ledger `acore_playerbots.coa_bots_installed` is read for all target
databases, with Windows paths and MySQL batch escaping normalized. Existing `updates` entries also seed
the ledger after SHA-1 validation. Playerbots data without either upstream history or Manager history stops
before any SQL changes and requests history repair. The installer's `complete` marker alone is insufficient.
For each base SQL file in Playerbots, world and characters: adopt when all defined tables exist, execute
when none exist, and stop with a repair error when only some exist. Existing tables are never dropped
by base imports. New base files can therefore be applied without rebuilding old tables.
The upstream module source and SQL are copied unchanged. Only the packaged default master switch is disabled.

`scripts/manage.py` is the launcher from the published base package (SHA256
`780f8ed024f8e0e1fe322ac01fcf59a2e12685cde2cdd1dca24140796cd31a79`) with the SQUID integration hooks.
Run `python -B scripts/test_squid_playerbots.py` to check conflict detection and migration behavior.

## Secrets (set by the repository owner)
Run these in PowerShell on the machine where `gh` is logged in.

```powershell
# signing key: piped from the key file, never typed or printed
Get-Content "$env:USERPROFILE\.coa-manager\signing\manifest-signing.key" -Raw | gh secret set COA_SIGNING_KEY -R Corfirean/coa-server-build

# fork sync token: gh asks you to paste it
gh secret set FORK_PUSH_TOKEN -R Corfirean/coa-server-build
```
`FORK_PUSH_TOKEN` is a fine-grained personal access token (GitHub > Settings > Developer settings) with access to
**only** `Corfirean/azerothcore-wotlk-coa` and the permissions *Contents: read and write* and *Workflows: read and write*.
It is only needed by the hourly `sync-fork` workflow. Without `COA_SIGNING_KEY` nothing is published (unsigned packages
are refused by every Manager anyway).

## Changelog
The changelog of every CoA project lives here: [CHANGELOG.md](CHANGELOG.md). Each repository (server fork, bots, Content Scaling,
Manager, renderer) keeps one small `changelog.d/` file per change, written in the same format by people and AIs alike;
the **changelog-release** workflow collects them at release time and also produces the Discord text. Rules, format and
examples: [changelog/GUIDE.md](changelog/GUIDE.md).

## Base package
The base contains game data and a database built from the maintainer's repack, so it is produced on the maintainer's
machine (`coa-release clean-base` + `pack-base`, see the manager repository) and uploaded to the `base` release.

## Database acceptance

The package job downloads the signed `base`, verifies every archive entry and extracts only the database and launcher
files into a new `coa-schema-fixture-*` directory. It applies the same ordered core, bots and corrective SQL that will
ship in the update, checks critical character/Wildcard structures, and captures `Scripts/database-schema.json`.
The fixture uses temporary free ports and never starts a world server. A failed migration or schema check stops
packaging and publication. The release tools require the complete contract when packing/signing, and `verify`
checks the signature, every archived file and the contract before edge publication or stable promotion.

`database-repairs/{auth,characters,world}` holds narrowly scoped corrective migrations with new immutable IDs.
They are appended after the ordinary SQL and recorded as `manager_repair__<filename>`; old migration history is
never cleared or blindly replayed. The Wildcard repair creates missing tables without touching existing rows.
This restores missing structure, not any previously lost player data. Wrong existing column definitions remain
visible failures for a separate targeted correction.

These workflows require the release tooling from Manager PR #17. Merge that dependency before this pipeline change;
the manual `manager_ref` input permits testing its branch without changing the production default.

## License
The scripts and workflows in this repository are under the [GNU Affero General Public License v3.0](LICENSE).
The packages published from it contain a `Licenses` folder with the licences of everything shipped (the server fork,
the bots module, MySQL) and a `NOTICE.txt` naming the exact source commits. The game data in the base package is not
covered by this licence.
