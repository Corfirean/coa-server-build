param(
    [string] $ServerDir = "C:/games/coa-work/plugin-spike/server-v03",
    [string] $SdkDir = "C:/games/coa-work/plugin-spike/sdk-v03",
    [string] $PluginsDir = "C:/games/coa-work/plugin-spike/plugins/ext/build-v03",
    [string] $CandidateLock = "C:/games/coa-server-build/candidate-lock.json",
    [string] $OutputDir = "C:/games/coa-server-build/dist",
    [switch] $GenerateChannelIndex
)

$ErrorActionPreference = "Stop"
Write-Host "=== CoA Modules Preview: Assembly & Packaging ==="

New-Item -ItemType Directory -Force -Path $OutputDir, "$OutputDir/server", "$OutputDir/sdk", "$OutputDir/plugins" | Out-Null

# 1. Package Server Executables & Runtime
if (Test-Path "$ServerDir/worldserver.exe") {
    Copy-Item "$ServerDir/worldserver.exe" "$OutputDir/server/" -Force
}
if (Test-Path "$ServerDir/authserver.exe") {
    Copy-Item "$ServerDir/authserver.exe" "$OutputDir/server/" -Force
}

# 2. Package Plugin SDK
if (Test-Path "$SdkDir/sdk.json") {
    Copy-Item "$SdkDir/*" "$OutputDir/sdk/" -Recurse -Force
}

# 3. Package Official Dynamic Plugins
if (Test-Path "$PluginsDir") {
    Get-ChildItem -Path $PluginsDir -Filter "*.dll" | Copy-Item -Destination "$OutputDir/plugins/" -Force
}
# TimeIsTime
$timeDir = "C:/games/coa-work/plugin-spike/plugins/timeistime/build-v03"
if (Test-Path "$timeDir/time-is-time.dll") {
    Copy-Item "$timeDir/time-is-time.dll" "$OutputDir/plugins/" -Force
} elseif (Test-Path "C:/games/coa-work/plugin-spike/plugins/timeistime/build/time-is-time.dll") {
    Copy-Item "C:/games/coa-work/plugin-spike/plugins/timeistime/build/time-is-time.dll" "$OutputDir/plugins/" -Force
}

# 4. Copy Candidate Lock
Copy-Item $CandidateLock "$OutputDir/candidate-lock.json" -Force

# 5. Generate Checksums for key deployable artifacts
$checksums = @()
$targets = @(
    "$OutputDir/server/worldserver.exe",
    "$OutputDir/server/authserver.exe",
    "$OutputDir/candidate-lock.json"
) + (Get-ChildItem -Path "$OutputDir/plugins" -Filter "*.dll" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName }) +
    (Get-ChildItem -Path "$OutputDir/sdk" -Filter "*.json" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })

foreach ($f in $targets) {
    if (Test-Path $f) {
        $hash = (Get-FileHash -Path $f -Algorithm SHA256).Hash.ToLowerInvariant()
        $name = $f.Substring($OutputDir.Length).TrimStart('\', '/')
        $checksums += "$hash  $name"
    }
}
$checksums | Set-Content "$OutputDir/sha256sums.txt" -Encoding utf8

# 6. Generate Preview Channel Index
$updatesDir = "C:/games/coa-server-build/updates"
New-Item -ItemType Directory -Force -Path $updatesDir | Out-Null

$lock = Get-Content $CandidateLock -Raw | ConvertFrom-Json
$channelIndex = @{
    channel = "preview"
    version = $lock.version
    release_timestamp = $lock.build_timestamp
    min_manager_version = "0.7.1"
    core = @{
        commit = $lock.core.commit
        abi_fingerprint = $lock.sdk.abi_fingerprint
        download_url = "https://github.com/Corfirean/coa-server-build/releases/download/preview-v$($lock.version)/csm-server-preview-win64.zip"
        sha256 = (Get-FileHash -Path "$OutputDir/server/worldserver.exe" -Algorithm SHA256 -ErrorAction SilentlyContinue).Hash.ToLowerInvariant()
    }
    sdk = @{
        version = $lock.sdk.version
        abi_fingerprint = $lock.sdk.abi_fingerprint
        download_url = "https://github.com/Corfirean/coa-server-build/releases/download/preview-v$($lock.version)/coa-plugin-sdk-v$($lock.sdk.version).zip"
    }
    modules = $lock.official_modules
    compatibility = @{
        db_schema = $lock.db_schema_requirements
        client = $lock.client_compatibility
    }
}

$channelIndexJson = $channelIndex | ConvertTo-Json -Depth 6
$channelIndexJson | Set-Content "$updatesDir/csm-preview-channel.json" -Encoding utf8
$channelIndexJson | Set-Content "$updatesDir/csm-preview-latest.json" -Encoding utf8

Write-Host "Preview package assembled successfully in $OutputDir"
Write-Host "Channel index written to $updatesDir/csm-preview-channel.json"
