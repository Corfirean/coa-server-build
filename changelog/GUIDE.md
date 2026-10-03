# CoA changelog guide

One changelog for everything the community runs: the server (`azerothcore-wotlk-coa`), the companion bots
(`mod-coa-playerbots`), Content Scaling (`mod-coa-content-scaling`), the Manager (`coa-server-manager`) and the renderer
(`modern-wow-renderer`). It is **written by whoever makes the change** (a person, Claude, Gemini, ChatGPT) in the same
format, and **assembled at release time** into `CHANGELOG.md`, a ready-to-post Discord text and `changelog.json`.

## How it works

1. You finish a change that a player or a server owner would notice.
2. In the **same repository and the same commit** you add one small file to `changelog.d/` (format below).
3. When a release goes out, someone runs the **changelog-release** workflow in `coa-server-build` (Actions tab, "Run
   workflow"), giving the release id and the versions that shipped. It reads the fragments of all five repositories,
   skips the ones already released, and commits `CHANGELOG.md`, `changelog/discord/<id>.txt` and
   `changelog/changelog.json`.
4. The Discord text is copied from `changelog/discord/<id>.txt` (it is already split into messages under 2000 characters).

Because each change is its own file, several AIs and people can write at the same time without conflicts, and nothing
has to be remembered at release time.

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

## Commands (optional, the script is plain Python 3, no packages)

```
python changelog.py new --area bots --type fixed --audience players --title "..." [--body "..."]
python changelog.py check --dir changelog.d          # in a repository: is my file valid?
python changelog.py status --remote                  # all repositories: what is waiting for the next release?
python changelog.py release --id 2026-10-03 --server 0.261002.13 --manager 0.4.0 --addon 2.1.1 --dry-run
```

Get the script: https://raw.githubusercontent.com/Corfirean/coa-server-build/main/changelog/changelog.py

Every repository also runs `check` in CI when `changelog.d/` changes, so a malformed file is reported on the commit.

## Release ids

Usually the date, `2026-10-03`. A second release on the same day is `2026-10-03-2`. Versions (all optional): `--server`,
`--manager`, `--addon`, `--renderer`.

## For a chat that cannot see the repository

Paste `changelog/prompt.md` into ChatGPT or Gemini, then describe what you changed; it answers with the file name and
the file content to save as `changelog.d/<name>`.

## Adding a repository

Add it to `changelog/sources.json` (name, repo, default branch), run
`python changelog.py sync-instructions PATH_TO_REPO` in it (creates `changelog.d/`, the AGENTS/CLAUDE/GEMINI instruction
files and the shared rules section) and add `.github/workflows/changelog.yml` (see any existing repository).
