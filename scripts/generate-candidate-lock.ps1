param(
    [string] $Version = "0.7.1-preview",
    [string] $SourceLock = "",
    [string] $CoreDir = "C:/games/coa-core-fork",
    [string] $BuilderDir = "C:/games/coa-server-build",
    [string] $ManagerDir = "C:/games/coa-server-manager-preview",
    [string] $ServerDir = "",
    [string] $SdkDir = "",
    [string] $PluginsDir = "",
    [string] $OutputFile = "candidate-lock.json"
)

$ErrorActionPreference = "Stop"
Write-Host "=== Generating Candidate Provenance Lock ($Version) ==="

# 1. Resolve and Validate Immutable Source Lock (P0-1: NO fabricated fallbacks)
if (-not $SourceLock) {
    $sourceLockCandidates = @(
        "$PWD/source-lock.json",
        "$PSScriptRoot/../source-lock.json"
    )
    foreach ($cand in $sourceLockCandidates) {
        if (Test-Path $cand) {
            $SourceLock = [System.IO.Path]::GetFullPath($cand)
            break
        }
    }
}

if (-not $SourceLock -or -not (Test-Path $SourceLock)) {
    throw "FATAL: Immutable Source Lock not found. Candidate generation strictly requires a verified source-lock.json file. (Checked: '$SourceLock')"
}

Write-Host "  Using Source Lock: $SourceLock"
try {
    $srcLock = Get-Content $SourceLock -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
} catch {
    throw "FATAL: Source lock file is malformed JSON: $($_.Exception.Message)"
}

# Validate Source Lock Schema and Required Commits
if (-not $srcLock.core -or -not $srcLock.core.commit -or $srcLock.core.commit.Length -ne 40) {
    throw "FATAL: Source lock has missing or invalid core.commit (must be 40-hex Git SHA)."
}
if (-not $srcLock.builder -or -not $srcLock.builder.commit -or $srcLock.builder.commit.Length -ne 40) {
    throw "FATAL: Source lock has missing or invalid builder.commit (must be 40-hex Git SHA)."
}
if (-not $srcLock.manager -or -not $srcLock.manager.commit -or $srcLock.manager.commit.Length -ne 40) {
    throw "FATAL: Source lock has missing or invalid manager.commit (must be 40-hex Git SHA)."
}
if (-not $srcLock.modules -or ($srcLock.modules.Count -eq 0)) {
    throw "FATAL: Source lock has missing or empty modules list."
}

# Validate that EVERY module has an immutable 40-character commit
foreach ($m in $srcLock.modules) {
    if (-not $m.commit -or $m.commit.Length -ne 40 -or $m.commit -notmatch '^[0-9a-fA-F]{40}$') {
        throw "FATAL: Module '$($m.id)' ($($m.binary)) has missing or invalid source commit in source lock: '$($m.commit)'. Historical fallback is strictly prohibited."
    }
    if (-not $m.repository) {
        throw "FATAL: Module '$($m.id)' has missing repository in source lock."
    }
}

# 2. Verify Live Build Repositories against Source Lock (when repositories are present)
function Verify-RepoRevision {
    param([string]$RepoDir, [string]$ExpectedCommit, [string]$Name)
    if (Test-Path "$RepoDir/.git") {
        $actual = (git -C $RepoDir rev-parse HEAD 2>$null)
        if ($LASTEXITCODE -eq 0 -and $actual) {
            $actual = $actual.Trim()
            if ($actual -ne $ExpectedCommit) {
                # Allow Builder repo to advance linearly from locked baseline
                if ($Name -eq "Builder") {
                    git -C $RepoDir merge-base --is-ancestor $ExpectedCommit HEAD 2>$null
                    if ($LASTEXITCODE -eq 0) {
                        Write-Host "  $Name Commit:    $actual (verified descendant of locked baseline $ExpectedCommit)"
                        return $actual
                    }
                }
                throw "FATAL: Build provenance mismatch for $Name repository at '$RepoDir'! Actual checkout: $actual vs Source Lock: $ExpectedCommit"
            }
            Write-Host "  $Name Commit:    $actual (verified matching source lock)"
            return $actual
        }
    }
    Write-Host "  $Name Commit:    $ExpectedCommit (from source lock)"
    return $ExpectedCommit
}

$coreCommit = Verify-RepoRevision -RepoDir $CoreDir -ExpectedCommit $srcLock.core.commit -Name "Core"
$builderCommit = Verify-RepoRevision -RepoDir $BuilderDir -ExpectedCommit $srcLock.builder.commit -Name "Builder"
$managerCommit = Verify-RepoRevision -RepoDir $ManagerDir -ExpectedCommit $srcLock.manager.commit -Name "Manager"

# 3. Resolve SDK ABI Fingerprint & Version
if (-not $SdkDir) {
    $sdkCandidates = @(
        "$PWD/artifacts/sdk",
        "$BuilderDir/dist/sdk"
    )
    foreach ($cand in $sdkCandidates) {
        if (Test-Path "$cand/sdk.json") {
            $SdkDir = [System.IO.Path]::GetFullPath($cand)
            break
        }
    }
}

if (-not $SdkDir -or -not (Test-Path "$SdkDir/sdk.json")) {
    throw "FATAL: SDK manifest 'sdk.json' not found in '$SdkDir'. Cannot generate candidate lock without verified SDK."
}

$sdkJson = Get-Content "$SdkDir/sdk.json" -Raw | ConvertFrom-Json
$abiFingerprint = $sdkJson.abiFingerprint
if (-not $abiFingerprint -or $abiFingerprint.Length -ne 64) {
    throw "FATAL: Invalid SDK ABI fingerprint in '$SdkDir/sdk.json'. Must be 64-hex SHA-256."
}

# Determine SDK Version: Must come from sdk.json or verified source-lock. NO synthetic fallbacks!
$resolvedSdkVersion = $null
if ($sdkJson.version) {
    $resolvedSdkVersion = $sdkJson.version
} elseif ($srcLock.sdk_version) {
    $resolvedSdkVersion = $srcLock.sdk_version
} else {
    throw "FATAL: SDK version cannot be determined. Neither sdk.json nor source-lock.json provided a verified sdk_version."
}

if ($resolvedSdkVersion -notmatch '^\d+\.\d+\.\d+') {
    throw "FATAL: Invalid SDK version ('$resolvedSdkVersion'). Must be valid semver string."
}

Write-Host "  SDK Version:         $resolvedSdkVersion"
Write-Host "  SDK ABI Fingerprint: $abiFingerprint"

# 4. Resolve Server Binary SHA-256 and Size
if (-not $ServerDir) {
    $serverCandidates = @(
        "$PWD/artifacts/server",
        "$BuilderDir/dist/server"
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

# 5. Resolve Compiled Dynamic Plugins (NO developer-specific paths, NO historical fallbacks)
if (-not $PluginsDir) {
    $pluginCandidates = @(
        "$PWD/artifacts/plugins",
        "$BuilderDir/dist/plugins"
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

$modules = @()
foreach ($mDef in $srcLock.modules) {
    $dllPath = Join-Path $PluginsDir $mDef.binary
    if (-not (Test-Path $dllPath)) {
        throw "FATAL: Compiled dynamic plugin DLL '$($mDef.binary)' not found in '$PluginsDir'. Module provenance cannot be established without compiled artifact."
    }
    
    $pHash = (Get-FileHash $dllPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $pSize = (Get-Item $dllPath).Length
    
    $modules += @{
        id = $mDef.id
        name = $mDef.name
        type = "DYNAMIC_DLL"
        binary = $mDef.binary
        repository = $mDef.repository
        source_commit = $mDef.commit
        sha256 = $pHash
        size = $pSize
        required_sdk = $resolvedSdkVersion
    }
    Write-Host "  Plugin $($mDef.binary): SHA=$pHash Size=$pSize Source=$($mDef.commit)"
}

# 6. Build Complete Candidate Lock
$candidateLock = [ordered]@{
    schema = 1
    product = "CoA Server Preview Modular Host"
    version = $Version
    build_timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    core = [ordered]@{
        repository = $srcLock.core.repository
        branch = $srcLock.core.branch
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
        repository = $srcLock.builder.repository
        branch = $srcLock.builder.branch
        commit = $builderCommit
    }
    manager = [ordered]@{
        repository = $srcLock.manager.repository
        branch = $srcLock.manager.branch
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
    static_modules = $srcLock.static_modules
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
