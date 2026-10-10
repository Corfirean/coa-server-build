#!/usr/bin/env bash
# Linux counterpart of assemble-tree.ps1: lays out the files of a release the way they sit in a server folder.
# Only shipped files: no configs the server owner edits (those are merged by the Manager), no databases.
set -euo pipefail

usage() { echo "usage: $0 --binaries DIR --core DIR --bots DIR --out DIR [--manager DIR] [--core-sha SHA] [--bots-sha SHA] [--scaling-sha SHA] [--squid-sha SHA] [--squid-tag TAG]" >&2; exit 2; }
binaries= core= bots= out= manager= core_sha=unknown bots_sha=unknown scaling_sha=unknown squid_sha=unknown squid_tag=
while [ $# -gt 0 ]; do
  case "$1" in
    --binaries) binaries=$2 ;; --core) core=$2 ;; --bots) bots=$2 ;; --out) out=$2 ;;
    --manager) manager=$2 ;; --core-sha) core_sha=$2 ;; --bots-sha) bots_sha=$2 ;; --scaling-sha) scaling_sha=$2 ;; --squid-sha) squid_sha=$2 ;; --squid-tag) squid_tag=$2 ;;
    *) usage ;;
  esac
  shift 2 || usage
done
[ -n "$binaries" ] && [ -n "$core" ] && [ -n "$bots" ] && [ -n "$out" ] || usage

mkdir -p "$out/Core/configs/modules" "$out/Core/reference" "$out/Extras/CoABotTools" "$out/Extras/SquidPlayerbots" "$out/Scripts" "$out/Data/dbc" "$out/Licenses"

install -m 0755 "$binaries/worldserver" "$binaries/authserver" "$out/Core/"

cp "$core/src/server/apps/worldserver/worldserver.conf.dist" "$out/Core/configs/"
cp "$core/src/server/apps/authserver/authserver.conf.dist" "$out/Core/configs/"
for d in "$core"/modules/*/; do
  for f in "$d"conf/*.dist; do [ -e "$f" ] && cp "$f" "$out/Core/configs/modules/"; done
done
cp "$bots/module/conf/mod_coa_playerbots.conf.dist" "$out/Core/configs/modules/"
# The CoA settings live in the core, not in a module folder (coa.conf.dist, wildcard.conf.dist, coa_bugreport.conf.dist).
# coa.conf must end up active (CoA.Enable = 1) or the world server rejects the Ascension client's extension packets and
# drops the connection after login. Only templates are shipped; the Manager creates the active files, and it leaves the
# bug-report one off until the owner configures it.
for f in "$core"/src/server/coa/conf/*.conf.dist; do cp "$f" "$out/Core/configs/modules/"; done
# Both bot modules compile together, but SQUID starts disabled on a new installation.
squid_conf="$out/Core/configs/modules/playerbots.conf.dist"
sed -i -E 's/^AiPlayerbot\.Enabled[[:space:]]*=[[:space:]]*1[[:space:]]*(\r?)$/AiPlayerbot.Enabled = 0\1/' "$squid_conf"
grep -qE '^AiPlayerbot\.Enabled = 0' "$squid_conf" || { echo "AiPlayerbot.Enabled could not be set to 0 in $squid_conf" >&2; exit 1; }
# SQUID's SQL, the launcher scripts and the record of the exact release, as on Windows.
cp -r "$core/modules/mod-playerbots/data/sql" "$out/Extras/SquidPlayerbots/sql"
cp "$(dirname "$0")/manage.py" "$(dirname "$0")/squid_playerbots.py" "$out/Scripts/"
printf '{\n  "schema": 1,\n  "tag": "%s",\n  "commit": "%s"\n}\n' "$squid_tag" "$squid_sha" > "$out/Extras/SquidPlayerbots/release.json"
settings_json="$core/modules/mod-playerbots/conf/playerbots.conf.settings.json"
[ -f "$settings_json" ] && cp "$settings_json" "$out/Core/configs/modules/playerbots.conf.settings.json"
cp "$core/modules/mod-playerbots/LICENSE" "$out/Licenses/mod-playerbots-LICENSE.txt"
# Only the .dist files are shipped: coa-release leaves active .conf files out of the package, and the Manager creates
# them from the .dist ones.
cp -r "$bots"/dist/reference/. "$out/Core/reference/"
cp "$bots/reference/coa_missing_equipment_displays.txt" "$out/Data/dbc/"
cp -r "$bots/addon/CoABotUI" "$out/Extras/CoABotUI"
# The offline bot factory: creates fully equipped bots straight in the database while the server is stopped.
cp "$bots/tools/offline_bot_factory.py" "$out/Extras/CoABotTools/"

# Licences and the pointer to the exact sources of what was compiled (AGPL/GPL source availability).
[ -n "$manager" ] && [ -f "$manager/LICENSE" ] && cp "$manager/LICENSE" "$out/Licenses/CoA-Server-Manager-AGPL-3.0.txt"
[ -f "$bots/LICENSE" ] && cp "$bots/LICENSE" "$out/Licenses/mod-coa-playerbots-AGPL-3.0.txt"
[ -f "$core/modules/mod-coa-content-scaling/LICENSE" ] && cp "$core/modules/mod-coa-content-scaling/LICENSE" "$out/Licenses/mod-coa-content-scaling-GPL-2.0.txt"
[ -f "$core/LICENSE" ] && cp "$core/LICENSE" "$out/Licenses/AzerothCore-fork-LICENSE.txt"
cat > "$out/Licenses/NOTICE.txt" <<NOTICE
CoA Server Manager - notice

Server binaries (Core/worldserver, Core/authserver) were built from:
  core  https://github.com/Corfirean/azerothcore-wotlk-coa   commit $core_sha
  bots  https://github.com/Corfirean/mod-coa-playerbots       commit $bots_sha
  squid https://github.com/Zyth45/mod-playerbots             commit $squid_sha (unchanged upstream source)
  scaling https://github.com/Corfirean/mod-coa-content-scaling commit $scaling_sha (with its TBC and WotLK content packs)
The core keeps its upstream licences (GPL-2.0-or-later for the MaNGOS-derived parts, AGPL-3.0 for AzerothCore-original
files); the bots module and CoA Server Manager are AGPL-3.0; the Content Scaling module is GPL-2.0. The complete corresponding source is at the links above.

The game data in the Data folder (dbc, maps, vmaps, mmaps) comes from the discontinued Ascension "Conquest of Azeroth"
realm client and is not covered by any of the licences above.
NOTICE

echo "assembled: $(find "$out" -type f | wc -l) files"
