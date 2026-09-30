param(
    [Parameter(Mandatory)] [string] $Binaries,
    [Parameter(Mandatory)] [string] $Core,
    [Parameter(Mandatory)] [string] $Bots,
    [Parameter(Mandatory)] [string] $Out,
    [string] $Manager = "",
    [string] $CoreSha = "unknown",
    [string] $BotsSha = "unknown"
)
# Lays out the files of a release the way they sit in a server folder. Only shipped files: no configs the
# server owner edits (those are merged by the Manager), no databases.
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path "$Out/Core/configs/modules", "$Out/Core/reference", "$Out/Extras", "$Out/Licenses" | Out-Null

Copy-Item "$Binaries/worldserver.exe", "$Binaries/authserver.exe" "$Out/Core/" -Force
Get-ChildItem "$Binaries/*.dll" | Copy-Item -Destination "$Out/Core/" -Force

Copy-Item "$Core/src/server/apps/worldserver/worldserver.conf.dist" "$Out/Core/configs/" -Force
Copy-Item "$Core/src/server/apps/authserver/authserver.conf.dist" "$Out/Core/configs/" -Force
Get-ChildItem "$Core/modules" -Directory | ForEach-Object {
    Get-ChildItem "$($_.FullName)/conf/*.dist" -ErrorAction SilentlyContinue | Copy-Item -Destination "$Out/Core/configs/modules/" -Force
}
Copy-Item "$Bots/module/conf/mod_coa_playerbots.conf.dist" "$Out/Core/configs/modules/" -Force
# The CoA compatibility settings live in the core, not in a module folder. They must be active: without CoA.Enable = 1
# the world server rejects the Ascension client's extension packets and drops the connection after login.
Copy-Item "$Core/src/server/coa/conf/coa.conf.dist" "$Out/Core/configs/modules/" -Force
# Every module reads configs/modules/<name>.conf. Ship an active copy of each .dist (created only when missing on
# install/update, never overwritten) so a fresh server runs with the documented defaults instead of warnings.
Get-ChildItem "$Out/Core/configs/modules/*.conf.dist" | ForEach-Object {
    Copy-Item $_.FullName ($_.FullName -replace '\.dist$', '') -Force
}
Copy-Item "$Bots/dist/reference/*" "$Out/Core/reference/" -Recurse -Force
Copy-Item "$Bots/addon/CoABotUI" "$Out/Extras/CoABotUI" -Recurse -Force

# Licences and the pointer to the exact sources of what was compiled (AGPL/GPL source availability).
if ($Manager -and (Test-Path "$Manager/LICENSE")) { Copy-Item "$Manager/LICENSE" "$Out/Licenses/CoA-Server-Manager-AGPL-3.0.txt" -Force }
if (Test-Path "$Bots/LICENSE") { Copy-Item "$Bots/LICENSE" "$Out/Licenses/mod-coa-playerbots-AGPL-3.0.txt" -Force }
if (Test-Path "$Core/LICENSE") { Copy-Item "$Core/LICENSE" "$Out/Licenses/AzerothCore-fork-LICENSE.txt" -Force }
@"
CoA Server Manager - notice

Server binaries (Core\worldserver.exe, Core\authserver.exe) were built from:
  core  https://github.com/Corfirean/azerothcore-wotlk-coa   commit $CoreSha
  bots  https://github.com/Corfirean/mod-coa-playerbots       commit $BotsSha
The core keeps its upstream licences (GPL-2.0-or-later for the MaNGOS-derived parts, AGPL-3.0 for AzerothCore-original
files); the bots module and CoA Server Manager are AGPL-3.0. The complete corresponding source is at the links above.

The bundled MySQL is GPL-2.0 (see MySQL-LICENSE.txt in this folder).

The game data in the Data folder (dbc, maps, vmaps, mmaps) comes from the discontinued Ascension "Conquest of Azeroth"
realm client and is not covered by any of the licences above.
"@ | Set-Content "$Out/Licenses/NOTICE.txt" -Encoding utf8

"assembled:"
Get-ChildItem $Out -Recurse -File | Measure-Object | ForEach-Object { "$($_.Count) files" }
