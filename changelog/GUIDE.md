# CoA changelog guide

Changes use one shared fragment format, but **release histories are separate**:

- [Server changelog](https://github.com/Corfirean/coa-server-build/blob/main/CHANGELOG.md): shipped server packages, companions and server modules.
- [Manager changelog](https://github.com/Corfirean/coa-server-manager/blob/master/CHANGELOG.md): published Manager versions, including client-patch installation changes delivered by that app.

Each repository's `changelog/history.json` is its reviewed history. `CHANGELOG.md` and GitHub release notes render from that same source, so the two public views agree. Original combined records are retained under `changelog/archive/` for provenance, not used as a public release history.

## How it works

1. Add a player-facing fragment in the same commit as the change, in the repository that ships it.
2. Prepare and test the frozen candidate. Fragments on an unreleased branch are not published notes.
3. After publication, the component's changelog workflow finds **actual published stable releases**. Manager reads fragments at each immutable release tag; server reads only its core/bot/scaling/build SHAs from that candidate's release lock. It never collects Manager changes into the server history or reads moving source branches.
4. The workflow appends only previously unreleased fragments, updates its own `CHANGELOG.md` and synchronizes GitHub release notes. It skips drafts, prereleases and missing historical tags. Existing reviewed history is preserved; repeated runs make no duplicate entries.
5. Manager's workflow runs after its installer release workflow or a published release. Server's runs after promotion, including publication by an Actions token that does not produce another release event. Both can also be dispatched manually.

Manual recovery commands (run from the matching repository):

```powershell
# Server
gh workflow run changelog-release.yml -R Corfirean/coa-server-build
# Manager
gh workflow run changelog.yml -R Corfirean/coa-server-manager
```

For a historical correction, edit the matching record in `changelog/history.json`, render locally with
`python changelog/sync_history.py --render-only` (server) or `python tools/sync_history.py --render-only` (Manager), then review and commit both files. The next synchronization updates the matching GitHub notes. Do not silently edit released fragments or claim imported upstream work as our own authored fixes.

The old combined `changelog.py release` command is disabled in the production build repository. Its parser/check/new/sync-instructions commands remain useful for authoring fragments. Do not use the archived combined JSON or Discord files as the current changelog.

## The file

Name: `YYYYMMDD-short-slug.md` with **today's date** and a lowercase slug (`20261003-invite-bot-by-role.md`).

```
---
area: bots
type: added
audience: players
title: Invite one bot by role
refs: 4390b11
---
Pick tank, healer or damage and a free bot of your faction joins your group. Optional: one paragraph, 300 characters at most.
```

| key | values |
|---|---|
| `area` | `server` (core, gameplay, database), `bots` (companion bots), `scaling` (Content Scaling and its packs), `modules` (other server modules: Enchanter, Auction House Bot...), `manager`, `addon` (the bot UI addon), `client` (the game client itself), `renderer` |
| `type` | `added`, `changed`, `fixed`, `removed`, `known-issue` |
| `audience` | `players` (what you see in the game) or `admins` (people who run a server or use the Manager) |
| `title` | required, English, at most 90 characters, starts with a capital letter, no full stop |
| `refs` | optional: commit SHAs or links, for the maintainers (not shown to players) |

The text after the second `---` is the optional **body**: a single paragraph, English, at most 300 characters.

## Writing it well

- Say what changed **for the reader**, in plain words. Players do not know our class names for internal systems, files or commits.
- One change per file. Two unrelated fixes are two files.
- `added`: something new they can use. `changed`: it works differently now. `fixed`: it was broken and is not. `removed`: gone.
  `known-issue`: a problem we know about and have not fixed yet (add the workaround in the body if there is one).
- Settings and commands may appear in the body, in backticks: `CoaBots.Economy.Enable = 1`.
- **Do not** add a file for refactors, tests, CI, formatting, documentation or anything nobody would notice. Not every commit is a changelog line.
- Never edit or delete a fragment after it has been released, and never write version numbers: the release step adds them.
- A fix to something that was **never released** (so nobody saw it broken) does not need its own line: edit or drop the fragment of the feature instead.

| Bad | Good |
|---|---|
| `Fix BotMgr::UpdateTrades null deref` | `Bots no longer crash the server when a trade is cancelled` |
| `Refactor config cache` | (no file) |
| `Улучшен интерфейс` | `The Browse tab lists every online bot` |
| `Added stuff to the Manager.` | `Delete an account from the Players page` |

## Fragment authoring commands

```powershell
python changelog/changelog.py check --dir changelog.d
python changelog/changelog.py new --area manager --type fixed --audience admins --title "Updates recover safely"
```

Player-facing notes should be short and understandable. Source hashes, internal paths and test output belong in evidence and release metadata, not public bullet points. A module update may name its new version, but must not relabel the upstream authors' features as our fixes.

The standalone synchronizer and its tests are vendored into Manager as `tools/sync_history.py` and `tools/test_sync_history.py`. Keep those copies identical when changing the shared generator; both projects test them independently.
