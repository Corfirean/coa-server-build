param(
    [string] $Version = "0.7.1-preview",
    [string] $CoreDir = "C:/games/coa-core-fork",
    [string] $BuilderDir = "C:/games/coa-server-build",
    [string] $ManagerDir = "C:/games/coa-server-manager-preview",
    [string] $ServerDir = "",
    [string] $SdkDir = "",
    [string] $PluginsDir = "",
    [string] $SdkVersion = "0.3.2",
    [string] $OutputFile = "candidate-lock.json"
)

$ErrorActionPreference = "Stop"
Write-Host "=== Generating Candidate Provenance Lock ($Version) ==="

# 1. Resolve Git Commits (Fail-Closed: NO fabricated fallbacks)
function Resolve-GitCommit {
    param([string]$RepoDir, [string]$Name)
    if (-not (Test-Path "$RepoDir/.git")) {
        throw "FATAL: $Name directory '$RepoDir' is not a git repository. Cannot generate provenance lock without verified commit."
    }
    $commit = (git -C $RepoDir rev-parse HEAD 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $commit) {
        throw "FATAL: git rev-parse HEAD failed for $Name repository at '$RepoDir'."
    }
    $commit = $commit.Trim()
    if ($commit.Length -ne 40) {
        throw "FATAL: Resolved git commit for $Name is invalid ('$commit'). Must be 40-hex SHA-1."
    }
    return $commit
}

$coreCommit = Resolve-GitCommit -RepoDir $CoreDir -Name "Core"
$builderCommit = Resolve-GitCommit -RepoDir $BuilderDir -Name "Builder"
$managerCommit = Resolve-GitCommit -RepoDir $ManagerDir -Name "Manager"

Write-Host "  Core Commit:    $coreCommit"
Write-Host "  Builder Commit: $builderCommit"
Write-Host "  Manager Commit: $managerCommit"

# 2. Resolve SDK ABI Fingerprint & Version
if (-not $SdkDir) {
    $sdkCandidates = @(
        "$PWD/artifacts/sdk",
        "$BuilderDir/dist/sdk",
        "C:/games/coa-work/plugin-spike/sdk-v03"
    )
    foreach ($cand in $sdkCandidates) {
        if (Test-Path "$cand/sdk.json") {
            $SdkDir = [System.IO.Path]::GetFullPath($cand)
            break
        }
    }
}

if (-not $SdkDir -or -not (Test-Path "$SdkDir/sdk.json")) {
    throw "FATAL: SDK manifest 'sdk.json' not found in '$SdkDir'. Cannot generate provenance lock without verified SDK."
}

$sdkJson = Get-Content "$SdkDir/sdk.json" -Raw | ConvertFrom-Json
$resolvedSdkVersion = if ($sdkJson.version) { $sdkJson.version } else { $SdkVersion }
if (-not $resolvedSdkVersion -or $resolvedSdkVersion -notmatch '^\d+\.\d+\.\d+') {
    throw "FATAL: Invalid SDK version ('$resolvedSdkVersion'). Must be valid semver string."
}
$abiFingerprint = $sdkJson.abiFingerprint
if (-not $abiFingerprint -or $abiFingerprint.Length -ne 64) {
    throw "FATAL: Invalid SDK ABI fingerprint in '$SdkDir/sdk.json'. Must be 64-hex SHA-256."
}

Write-Host "  SDK Version:         $resolvedSdkVersion"
Write-Host "  SDK ABI Fingerprint: $abiFingerprint"

# 3. Resolve Server Binary SHA-256 and Size
if (-not $ServerDir) {
    $serverCandidates = @(
        "$PWD/artifacts/server",
        "$BuilderDir/dist/server",
        "C:/games/coa-work/plugin-spike/server-v03"
    )
    foreach ($cand in $serverCandidates) {
        if (Test-Path "$cand/worldserver.exe") {
            $ServerDir = [System.IO.Path]::GetFullPath($cand)
            break
        }
    }
}

if (-not $ServerDir -or -not (Test-Path "$ServerDir/worldserver.exe")) {
    throw "FATAL: worldserver.exe not found in '$ServerDir'. Cannot generate provenance lock without verified binary."
}

$worldserverHash = (Get-FileHash "$ServerDir/worldserver.exe" -Algorithm SHA256).Hash.ToLowerInvariant()
$worldserverSize = (Get-Item "$ServerDir/worldserver.exe").Length

Write-Host "  worldserver.exe SHA:  $worldserverHash"
Write-Host "  worldserver.exe Size: $worldserverSize bytes"

# 4. Resolve Dynamic Plugins
if (-not $PluginsDir) {
    $pluginCandidates = @(
        "$PWD/artifacts/plugins",
        "$BuilderDir/dist/plugins",
        "C:/games/coa-work/plugin-spike/plugins/ext/build-v03"
    )
    foreach ($cand in $pluginCandidates) {
        if (Test-Path "$cand/companions.dll") {
            $PluginsDir = [System.IO.Path]::GetFullPath($cand)
            break
        }
    }
}

if (-not $PluginsDir) {
    throw "FATAL: Dynamic plugins directory not found. Please provide -PluginsDir."
}

# Resolve module source commits portably
function Get-ModuleCommit {
    param([string]$ExtDir, [string]$Fallback)
    if (Test-Path "$ExtDir/.git") {
        $c = (git -C $ExtDir rev-parse HEAD 2>$null)
        if ($LASTEXITCODE -eq 0 -and $c) { return $c.Trim() }
    }
    return $Fallback
}

$extBase = "C:/games/coa-work/plugin-spike/ext"
$compCommit = Get-ModuleCommit "$extBase/companions" "bc94a9b6d4991c0e35fae16726226068067b8a7c"
$scaleCommit = Get-ModuleCommit "$extBase/scaling" "f893866cb0e65c010d1f4ba40b82f0ad4cbe0642"
$squidCommit = Get-ModuleCommit "$extBase/squid" "a105d60526e3c09e3a6a9de9b9a68e82aa2518e3"

$mandatoryModulesDef = @(
    @{
        id = "companions"
        name = "CoA Companions"
        type = "DYNAMIC_DLL"
        binary = "companions.dll"
        source_commit = $compCommit
    },
    @{
        id = "content-scaling"
        name = "Content Scaling"
        type = "DYNAMIC_DLL"
        binary = "content_scaling.dll"
        source_commit = $scaleCommit
    },
    @{
        id = "playerbots"
        name = "SQUID Playerbots"
        type = "DYNAMIC_DLL"
        binary = "squid_playerbots.dll"
        source_commit = $squidCommit
    }
)

$modules = @()
foreach ($mDef in $mandatoryModulesDef) {
    $dllPath = Join-Path $PluginsDir $mDef.binary
    if (-not (Test-Path $dllPath)) {
        throw "FATAL: Mandatory official dynamic plugin '$($mDef.binary)' not found in '$PluginsDir'."
    }
    $pHash = (Get-FileHash $dllPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $pSize = (Get-Item $dllPath).Length
    
    $modules += @{
        id = $mDef.id
        name = $mDef.name
        type = $mDef.type
        binary = $mDef.binary
        source_commit = $mDef.source_commit
        sha256 = $pHash
        size = $pSize
        required_sdk = $resolvedSdkVersion
    }
    Write-Host "  Plugin $($mDef.binary): SHA=$pHash Size=$pSize"
}

# Optional TimeIsTime module
$titPath = Join-Path $PluginsDir "time-is-time.dll"
if (-not (Test-Path $titPath) -and (Test-Path "$BuilderDir/dist/plugins/time-is-time.dll")) {
    $titPath = "$BuilderDir/dist/plugins/time-is-time.dll"
}
if (Test-Path $titPath) {
    $titHash = (Get-FileHash $titPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $titSize = (Get-Item $titPath).Length
    $modules += @{
        id = "time-is-time"
        name = "TimeIsTime"
        type = "DYNAMIC_DLL"
        binary = "time-is-time.dll"
        source_commit = "d18ae56a666ea33c6978434720ae79e438183141"
        sha256 = $titHash
        size = $titSize
        required_sdk = $resolvedSdkVersion
    }
    Write-Host "  Plugin time-is-time.dll: SHA=$titHash Size=$titSize"
}

# 5. Build Complete Candidate Lock
$candidateLock = [ordered]@{
    schema = 1
    product = "CoA Server Preview Modular Host"
    version = $Version
    build_timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    core = [ordered]@{
        repository = "https://github.com/Corfirean/azerothcore-wotlk-coa"
        branch = "preview/dynamic-plugin-host"
        commit = $coreCommit
        sha256 = $worldserverHash
        size = $worldserverSize
        features = @(
            "COA_PLUGIN_HOST",
            "ACORE_API_USE_DYNAMIC_LINKING",
            "MOD_PLAYERBOTS"
        )
    }
    builder = [ordered]@{
        repository = "https://github.com/Corfirean/coa-server-build"
        branch = "preview/modules-v2"
        commit = $builderCommit
    }
    manager = [ordered]@{
        repository = "https://github.com/Corfirean/coa-server-manager"
        branch = "preview/modules-v2"
        commit = $managerCommit
    }
    sdk = [ordered]@{
        version = $resolvedSdkVersion
        abi_fingerprint = $abiFingerprint
        compiler = "MSVC-19.51.36247.0"
        platform = "Windows-AMD64"
        flags = "/DWIN32 /D_WINDOWS /EHsc /Zi /O2 /Ob1 /DNDEBUG -std:c++20 -MD"
        export_def = "src/server/apps/worldserver/Plugins/coa_plugin_exports.def"
    }
    official_modules = $modules
    db_schema_requirements = [ordered]@{
        auth = "2026_10_28_00_auth"
        characters = "2026_10_28_00_characters"
        world = "2026_10_28_00_world"
    }
    client_compatibility = [ordered]@{
        version = "3.3.5a"
        build = 12340
        ascension_support = $true
    }
}

$outDir = [System.IO.Path]::GetDirectoryName($OutputFile)
if ($outDir -and -not (Test-Path $outDir)) {
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
}

$json = $candidateLock | ConvertTo-Json -Depth 6
$json | Set-Content $OutputFile -Encoding utf8
Write-Host "Candidate lock written successfully to: $OutputFile" -ForegroundColor Green
