param(
    [string] $ServerDir = "",
    [string] $SdkDir = "",
    [string] $PluginsDir = "",
    [string] $CandidateLock = "",
    [string] $OutputDir = "",
    [string] $ManagerPackageDir = "",
    [string] $TimeIsTimeDll = "",
    [string] $ChannelDir = "",
    [string] $ManagerVersion = "0.7.1",
    [string] $ManagerSignature = "",
    [switch] $GenerateChannelIndex,
    [switch] $RequireAllOfficialModules
)

$ErrorActionPreference = "Stop"
Write-Host "=== CoA Modules Preview: Assembly & Packaging ==="

# 0. Resolve default paths portably
if (-not $OutputDir) {
    $OutputDir = "$PSScriptRoot/../dist"
}
$OutputDir = [System.IO.Path]::GetFullPath($OutputDir)

if (-not $ChannelDir) {
    $ChannelDir = "$PSScriptRoot/../updates"
}
$ChannelDir = [System.IO.Path]::GetFullPath($ChannelDir)

if (-not $CandidateLock) {
    $candidateLockCandidates = @(
        "$PWD/candidate-lock.json",
        "$PSScriptRoot/../candidate-lock.json"
    )
    foreach ($cand in $candidateLockCandidates) {
        if (Test-Path $cand) {
            $CandidateLock = [System.IO.Path]::GetFullPath($cand)
            break
        }
    }
}
if (-not $CandidateLock -or -not (Test-Path $CandidateLock)) {
    throw "Candidate lock not found. Please provide -CandidateLock path."
}

if (-not $ServerDir) {
    $serverCandidates = @(
        "$PWD/artifacts/server",
        "$PSScriptRoot/../artifacts/server",
        "C:/games/coa-work/plugin-spike/server-v03"
    )
    foreach ($cand in $serverCandidates) {
        if (Test-Path "$cand/worldserver.exe") {
            $ServerDir = [System.IO.Path]::GetFullPath($cand)
            break
        }
    }
}

if (-not $SdkDir) {
    $sdkCandidates = @(
        "$PWD/artifacts/sdk",
        "$PSScriptRoot/../artifacts/sdk",
        "C:/games/coa-work/plugin-spike/sdk-v03"
    )
    foreach ($cand in $sdkCandidates) {
        if (Test-Path "$cand/sdk.json") {
            $SdkDir = [System.IO.Path]::GetFullPath($cand)
            break
        }
    }
}

if (-not $PluginsDir) {
    $pluginCandidates = @(
        "$PWD/artifacts/plugins",
        "$PSScriptRoot/../artifacts/plugins",
        "C:/games/coa-work/plugin-spike/plugins/ext/build-v03"
    )
    foreach ($cand in $pluginCandidates) {
        if (Test-Path "$cand/companions.dll") {
            $PluginsDir = [System.IO.Path]::GetFullPath($cand)
            break
        }
    }
}

Write-Host "Server Dir:     $ServerDir"
Write-Host "SDK Dir:        $SdkDir"
Write-Host "Plugins Dir:    $PluginsDir"
Write-Host "Candidate Lock: $CandidateLock"
Write-Host "Output Dir:     $OutputDir"
Write-Host "Channel Dir:    $ChannelDir"

# Validate mandatory inputs
if (-not $ServerDir -or -not (Test-Path "$ServerDir/worldserver.exe")) {
    throw "Mandatory binary missing: worldserver.exe not found in '$ServerDir'."
}
if (-not $SdkDir -or -not (Test-Path "$SdkDir/sdk.json")) {
    throw "Mandatory metadata missing: sdk.json not found in '$SdkDir'."
}

New-Item -ItemType Directory -Force -Path $OutputDir, "$OutputDir/server", "$OutputDir/sdk", "$OutputDir/plugins" | Out-Null

# 1. Package Server Executables & Runtime
Copy-Item "$ServerDir/worldserver.exe" "$OutputDir/server/" -Force
if (Test-Path "$ServerDir/authserver.exe") {
    Copy-Item "$ServerDir/authserver.exe" "$OutputDir/server/" -Force
}

# 2. Package Plugin SDK
Copy-Item "$SdkDir/*" "$OutputDir/sdk/" -Recurse -Force

# 3. Package Official Dynamic Plugins
$mandatoryPlugins = @("companions.dll", "content_scaling.dll", "squid_playerbots.dll")
if ($PluginsDir -and (Test-Path $PluginsDir)) {
    Get-ChildItem -Path $PluginsDir -Filter "*.dll" | Copy-Item -Destination "$OutputDir/plugins/" -Force
}

if ($RequireAllOfficialModules) {
    foreach ($p in $mandatoryPlugins) {
        if (-not (Test-Path "$OutputDir/plugins/$p")) {
            throw "Mandatory official module '$p' missing from '$OutputDir/plugins'."
        }
    }
}

# Optional TimeIsTime
if ($TimeIsTimeDll -and (Test-Path $TimeIsTimeDll)) {
    Copy-Item $TimeIsTimeDll "$OutputDir/plugins/" -Force
} elseif (Test-Path "$PluginsDir/time-is-time.dll") {
    Copy-Item "$PluginsDir/time-is-time.dll" "$OutputDir/plugins/" -Force
} elseif (Test-Path "C:/games/coa-work/plugin-spike/plugins/timeistime/build-v03/time-is-time.dll") {
    Copy-Item "C:/games/coa-work/plugin-spike/plugins/timeistime/build-v03/time-is-time.dll" "$OutputDir/plugins/" -Force
}

# Optional Manager Installer/App
if ($ManagerPackageDir -and (Test-Path $ManagerPackageDir)) {
    New-Item -ItemType Directory -Force -Path "$OutputDir/manager" | Out-Null
    Copy-Item "$ManagerPackageDir/*" "$OutputDir/manager/" -Recurse -Force
}

# 4. Copy Candidate Lock
Copy-Item $CandidateLock "$OutputDir/candidate-lock.json" -Force

# 5. Generate SHA-256 Checksums for all deployable binaries
$checksums = @()
$targets = @(
    "$OutputDir/server/worldserver.exe",
    "$OutputDir/candidate-lock.json"
)
if (Test-Path "$OutputDir/server/authserver.exe") {
    $targets += "$OutputDir/server/authserver.exe"
}
$targets += (Get-ChildItem -Path "$OutputDir/plugins" -Filter "*.dll" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
$targets += (Get-ChildItem -Path "$OutputDir/sdk" -Filter "*.json" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
if (Test-Path "$OutputDir/manager") {
    $targets += (Get-ChildItem -Path "$OutputDir/manager" -Filter "*.*" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
}

foreach ($f in $targets) {
    if (Test-Path $f) {
        $hash = (Get-FileHash -Path $f -Algorithm SHA256).Hash.ToLowerInvariant()
        $relName = $f.Substring($OutputDir.Length).TrimStart('\', '/')
        $checksums += "$hash  $relName"
    }
}
$checksums | Set-Content "$OutputDir/sha256sums.txt" -Encoding utf8

# 6. Generate Channel Indexes (Contracts 1 & 2)
New-Item -ItemType Directory -Force -Path $ChannelDir | Out-Null
$lock = Get-Content $CandidateLock -Raw | ConvertFrom-Json

# Contract 1: Preview Manager Updater Manifest (Tauri v2 format)
$tauriManifest = @{
    version = $ManagerVersion
    notes = "CSM Modules Preview $ManagerVersion"
    pub_date = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    platforms = @{
        "windows-x86_64" = @{
            signature = if ($ManagerSignature) { $ManagerSignature } else { "" }
            url = "https://github.com/Corfirean/coa-server-manager/releases/download/preview-v$ManagerVersion/csm-modules-preview_${ManagerVersion}_x64_en-US.msi.zip"
        }
    }
}
$tauriManifest | ConvertTo-Json -Depth 5 | Set-Content "$ChannelDir/csm-preview-app-latest.json" -Encoding utf8

# Contract 2: Modular Server & Plugin Component Channel Manifest
$componentManifest = @{
    channel = "preview"
    version = $lock.version
    release_timestamp = $lock.build_timestamp
    min_manager_version = "0.7.1"
    core = @{
        commit = $lock.core.commit
        abi_fingerprint = $lock.sdk.abi_fingerprint
        download_url = "https://github.com/Corfirean/coa-server-build/releases/download/preview-v$($lock.version)/csm-server-preview-win64.zip"
        sha256 = (Get-FileHash -Path "$OutputDir/server/worldserver.exe" -Algorithm SHA256).Hash.ToLowerInvariant()
        binaries = @{
            worldserver = "worldserver.exe"
            authserver = if (Test-Path "$OutputDir/server/authserver.exe") { "authserver.exe" } else { $null }
        }
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

$componentManifestJson = $componentManifest | ConvertTo-Json -Depth 6
$componentManifestJson | Set-Content "$ChannelDir/csm-preview-components.json" -Encoding utf8
$componentManifestJson | Set-Content "$ChannelDir/csm-preview-channel.json" -Encoding utf8
$componentManifestJson | Set-Content "$ChannelDir/csm-preview-latest.json" -Encoding utf8

Write-Host "Preview package assembled successfully in $OutputDir"
Write-Host "Contract 1 (App Updater) written to:     $ChannelDir/csm-preview-app-latest.json"
Write-Host "Contract 2 (Components) written to:      $ChannelDir/csm-preview-components.json"
