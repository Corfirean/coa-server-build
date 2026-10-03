# coa-server-build

Build and release pipeline for **CoA Server Manager** packages.

| Release tag | What it holds | Who reads it |
|---|---|---|
| `base` | Base install package (server files, clean databases, game data) | "Install new server" |
| `edge` | Latest nightly cumulative update (prerelease) | anyone testing new builds |
| `stable` | The promoted update | every Manager, by default |

Each release carries `manifest.json`, `manifest.json.sig` (Ed25519, checked by the app against its built-in public key)
and the archive parts (`*.tar.zst.NNN`, below GitHub's 2 GiB asset limit).

## Workflows
* **build** - nightly + manual. Compiles [the fork](https://github.com/Corfirean/azerothcore-wotlk-coa) with
  [mod-coa-playerbots](https://github.com/Corfirean/mod-coa-playerbots) on Windows, builds a cumulative update against the
  `base` manifest, signs it, publishes it to `edge`. Versions are `0.YYMMDD.<run>`.
* **promote** - manual. Copies `edge` to `stable`.
* **sync-fork** - hourly. Mirrors upstream `main` into the fork and merges it into `coa-bots`; a conflict opens an issue.

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

## License
The scripts and workflows in this repository are under the [GNU Affero General Public License v3.0](LICENSE).
The packages published from it contain a `Licenses` folder with the licences of everything shipped (the server fork,
the bots module, MySQL) and a `NOTICE.txt` naming the exact source commits. The game data in the base package is not
covered by this licence.
