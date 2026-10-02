#!/usr/bin/env bash
# Linux counterpart of assemble-tree.ps1: lays out the files of a release the way they sit in a server folder.
# Only shipped files: no configs the server owner edits (those are merged by the Manager), no databases.
set -euo pipefail

usage() { echo "usage: $0 --binaries DIR --core DIR --bots DIR --out DIR [--manager DIR] [--core-sha SHA] [--bots-sha SHA]" >&2; exit 2; }
binaries= core= bots= out= manager= core_sha=unknown bots_sha=unknown
while [ $# -gt 0 ]; do
  case "$1" in
    --binaries) binaries=$2 ;; --core) core=$2 ;; --bots) bots=$2 ;; --out) out=$2 ;;
    --manager) manager=$2 ;; --core-sha) core_sha=$2 ;; --bots-sha) bots_sha=$2 ;;
    *) usage ;;
  esac
  shift 2 || usage
done
[ -n "$binaries" ] && [ -n "$core" ] && [ -n "$bots" ] && [ -n "$out" ] || usage

mkdir -p "$out/Core/configs/modules" "$out/Core/reference" "$out/Extras/CoABotTools" "$out/Licenses"

install -m 0755 "$binaries/worldserver" "$binaries/authserver" "$out/Core/"

cp "$core/src/server/apps/worldserver/worldserver.conf.dist" "$out/Core/configs/"
cp "$core/src/server/apps/authserver/authserver.conf.dist" "$out/Core/configs/"
for d in "$core"/modules/*/; do
  for f in "$d"conf/*.dist; do [ -e "$f" ] && cp "$f" "$out/Core/configs/modules/"; done
done
cp "$bots/module/conf/mod_coa_playerbots.conf.dist" "$out/Core/configs/modules/"
# The CoA compatibility settings live in the core, not in a module folder. They must be active: without CoA.Enable = 1
# the world server rejects the Ascension client's extension packets and drops the connection after login.
cp "$core/src/server/coa/conf/coa.conf.dist" "$out/Core/configs/modules/"
# Every module reads configs/modules/<name>.conf. Ship an active copy of each .dist (created only when missing on
# install/update, never overwritten) so a fresh server runs with the documented defaults instead of warnings.
for f in "$out"/Core/configs/modules/*.conf.dist; do cp "$f" "${f%.dist}"; done
cp -r "$bots"/dist/reference/. "$out/Core/reference/"
cp -r "$bots/addon/CoABotUI" "$out/Extras/CoABotUI"
# The offline bot factory: creates fully equipped bots straight in the database while the server is stopped.
cp "$bots/tools/offline_bot_factory.py" "$out/Extras/CoABotTools/"

# Licences and the pointer to the exact sources of what was compiled (AGPL/GPL source availability).
[ -n "$manager" ] && [ -f "$manager/LICENSE" ] && cp "$manager/LICENSE" "$out/Licenses/CoA-Server-Manager-AGPL-3.0.txt"
[ -f "$bots/LICENSE" ] && cp "$bots/LICENSE" "$out/Licenses/mod-coa-playerbots-AGPL-3.0.txt"
[ -f "$core/LICENSE" ] && cp "$core/LICENSE" "$out/Licenses/AzerothCore-fork-LICENSE.txt"
cat > "$out/Licenses/NOTICE.txt" <<NOTICE
CoA Server Manager - notice

Server binaries (Core/worldserver, Core/authserver) were built from:
  core  https://github.com/Corfirean/azerothcore-wotlk-coa   commit $core_sha
  bots  https://github.com/Corfirean/mod-coa-playerbots       commit $bots_sha
The core keeps its upstream licences (GPL-2.0-or-later for the MaNGOS-derived parts, AGPL-3.0 for AzerothCore-original
files); the bots module and CoA Server Manager are AGPL-3.0. The complete corresponding source is at the links above.

The game data in the Data folder (dbc, maps, vmaps, mmaps) comes from the discontinued Ascension "Conquest of Azeroth"
realm client and is not covered by any of the licences above.
NOTICE

echo "assembled: $(find "$out" -type f | wc -l) files"
