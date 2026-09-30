param(
    [Parameter(Mandatory)] [string] $Binaries,
    [Parameter(Mandatory)] [string] $Core,
    [Parameter(Mandatory)] [string] $Bots,
    [Parameter(Mandatory)] [string] $Out
)
# Lays out the files of a release the way they sit in a server folder. Only shipped files: no configs the
# server owner edits (those are merged by the Manager), no databases.
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path "$Out/Core/configs/modules", "$Out/Core/reference", "$Out/Extras" | Out-Null

Copy-Item "$Binaries/worldserver.exe", "$Binaries/authserver.exe" "$Out/Core/" -Force
Get-ChildItem "$Binaries/*.dll" | Copy-Item -Destination "$Out/Core/" -Force

Copy-Item "$Core/src/server/apps/worldserver/worldserver.conf.dist" "$Out/Core/configs/" -Force
Copy-Item "$Core/src/server/apps/authserver/authserver.conf.dist" "$Out/Core/configs/" -Force
Get-ChildItem "$Core/modules" -Directory | ForEach-Object {
    Get-ChildItem "$($_.FullName)/conf/*.dist" -ErrorAction SilentlyContinue | Copy-Item -Destination "$Out/Core/configs/modules/" -Force
}
Copy-Item "$Bots/module/conf/mod_coa_playerbots.conf.dist" "$Out/Core/configs/modules/" -Force
Copy-Item "$Bots/dist/reference/*" "$Out/Core/reference/" -Recurse -Force
Copy-Item "$Bots/addon/CoABotUI" "$Out/Extras/CoABotUI" -Recurse -Force

"assembled:"
Get-ChildItem $Out -Recurse -File | Measure-Object | ForEach-Object { "$($_.Count) files" }
