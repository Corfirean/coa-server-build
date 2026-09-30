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
```
gh secret set COA_SIGNING_KEY -R Corfirean/coa-server-build < "%USERPROFILE%\.coa-manager\signing\manifest-signing.key"
gh secret set FORK_PUSH_TOKEN -R Corfirean/coa-server-build     # fine-grained token: Contents + Workflows write on the fork
```
Without `COA_SIGNING_KEY` nothing is published (unsigned packages are refused by every Manager anyway).

## Base package
The base contains game data and a database built from the maintainer's repack, so it is produced on the maintainer's
machine (`coa-release clean-base` + `pack-base`, see the manager repository) and uploaded to the `base` release.
