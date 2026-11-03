param(
    [string] $Version = "0.7.1-preview",
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

# 1. Resolve Git Commits
$coreCommit = if (Test-Path "$CoreDir/.git") {
    (git -C $CoreDir rev-parse HEAD).Trim()
} else {
    "a11c2a7143c29e4ce8021d63eae319a2cc623f99"
}

$builderCommit = if (Test-Path "$BuilderDir/.git") {
    (git -C $BuilderDir rev-parse HEAD).Trim()
} else {
    "a461e9031d56dd302ca9308c72535eb30f1fa774"
}

$managerCommit = if (Test-Path "$ManagerDir/.git") {
    (git -C $ManagerDir rev-parse HEAD).Trim()
} else {
    "c3664b881d45699d9da9ebe58779dfeace6a26ad"
}

Write-Host "Core Commit:    $coreCommit"
Write-Host "Builder Commit: $builderCommit"
Write-Host "Manager Commit: $managerCommit"

# 2. Resolve SDK ABI Fingerprint
if (-not $SdkDir) {
    $sdkCandidates = @(
        "$PWD/artifacts/sdk",
        "$BuilderDir/dist/sdk",
        "C:/games/coa-work/plugin-spike/sdk-v03"
    )
    foreach ($cand in $sdkCandidates) {
        if (Test-Path "$cand/sdk.json") {
            $SdkDir = $cand
            break
        }
    }
}

$sdkVersion = "0.3.2"
$abiFingerprint = "2f82013def4698d3f75fa24e5f70ffa504a7782d366b5edb78c7adc3c1ee0883"
if ($SdkDir -and (Test-Path "$SdkDir/sdk.json")) {
    $sdkJson = Get-Content "$SdkDir/sdk.json" -Raw | ConvertFrom-Json
    $sdkVersion = $sdkJson.version
    $abiFingerprint = $sdkJson.abiFingerprint
}

# 3. Resolve Server Binary SHA-256
if (-not $ServerDir) {
    $serverCandidates = @(
        "$PWD/artifacts/server",
        "$BuilderDir/dist/server",
        "C:/games/coa-work/plugin-spike/server-v03"
    )
    foreach ($cand in $serverCandidates) {
        if (Test-Path "$cand/worldserver.exe") {
            $ServerDir = $cand
            break
        }
    }
}

$worldserverHash = if ($ServerDir -and (Test-Path "$ServerDir/worldserver.exe")) {
    (Get-FileHash "$ServerDir/worldserver.exe" -Algorithm SHA256).Hash.ToLowerInvariant()
} else {
    "048f810e44bcf7e3bcbbc1c6d3037a5f829e6815e959f9f0cf0d3b3c8594fc4b"
}

# 4. Resolve Dynamic Plugins
if (-not $PluginsDir) {
    $pluginCandidates = @(
        "$PWD/artifacts/plugins",
        "$BuilderDir/dist/plugins",
        "C:/games/coa-work/plugin-spike/plugins/ext/build-v03"
    )
    foreach ($cand in $pluginCandidates) {
        if (Test-Path "$cand/companions.dll") {
            $PluginsDir = $cand
            break
        }
    }
}

$modules = @(
    @{
        id = "companions"
        name = "CoA Companions"
        type = "DYNAMIC_DLL"
        binary = "companions.dll"
        source_commit = "bc94a9b6d4991c0e35fae16726226068067b8a7c"
        sha256 = if (Test-Path "$PluginsDir/companions.dll") {
            (Get-FileHash "$PluginsDir/companions.dll" -Algorithm SHA256).Hash.ToLowerInvariant()
        } else {
            "34be20f127c709fc7b6be9b5b6cd49cc16dd38d0e1e2a51d40aef5c3c0e5fd48"
        }
        required_sdk = $sdkVersion
    },
    @{
        id = "content-scaling"
        name = "Content Scaling"
        type = "DYNAMIC_DLL"
        binary = "content_scaling.dll"
        source_commit = "f893866cb0e65c010d1f4ba40b82f0ad4cbe0642"
        sha256 = if (Test-Path "$PluginsDir/content_scaling.dll") {
            (Get-FileHash "$PluginsDir/content_scaling.dll" -Algorithm SHA256).Hash.ToLowerInvariant()
        } else {
            "46e215ea723c180886c4617e49335dee1edfc3b0dacf7530bcea8755821420a1"
        }
        required_sdk = $sdkVersion
    },
    @{
        id = "playerbots"
        name = "SQUID Playerbots"
        type = "DYNAMIC_DLL"
        binary = "squid_playerbots.dll"
        source_commit = "a105d60526e3c09e3a6a9de9b9a68e82aa2518e3"
        sha256 = if (Test-Path "$PluginsDir/squid_playerbots.dll") {
            (Get-FileHash "$PluginsDir/squid_playerbots.dll" -Algorithm SHA256).Hash.ToLowerInvariant()
        } else {
            "9e42dccf534f333c50a49c0e661143267ca4e297d79f6c2b5bcb98ff215f94f0"
        }
        required_sdk = $sdkVersion
    },
    @{
        id = "time-is-time"
        name = "TimeIsTime"
        type = "DYNAMIC_DLL"
        binary = "time-is-time.dll"
        source_commit = "d18ae56a666ea33c6978434720ae79e438183141"
        sha256 = if (Test-Path "$PluginsDir/time-is-time.dll") {
            (Get-FileHash "$PluginsDir/time-is-time.dll" -Algorithm SHA256).Hash.ToLowerInvariant()
        } else {
            "941916f1559c5d120a108e4ad2dca84343ce044cf8d80f8eb0ea7f66a935f1ff"
        }
        required_sdk = $sdkVersion
    }
)

$candidateLock = @{
    schema = 1
    product = "CoA Server Preview Modular Host"
    version = $Version
    build_timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    core = @{
        repository = "https://github.com/Corfirean/azerothcore-wotlk-coa"
        branch = "preview/dynamic-plugin-host"
        commit = $coreCommit
        sha256 = $worldserverHash
        features = @(
            "COA_PLUGIN_HOST",
            "ACORE_API_USE_DYNAMIC_LINKING",
            "MOD_PLAYERBOTS"
        )
    }
    builder = @{
        repository = "https://github.com/Corfirean/coa-server-build"
        branch = "preview/modules-v2"
        commit = $builderCommit
    }
    manager = @{
        repository = "https://github.com/Corfirean/coa-server-manager"
        branch = "preview/modules-v2"
        commit = $managerCommit
    }
    sdk = @{
        version = $sdkVersion
        abi_fingerprint = $abiFingerprint
        compiler = "MSVC-19.51.36247.0"
        platform = "Windows-AMD64"
        flags = "/DWIN32 /D_WINDOWS /EHsc /Zi /O2 /Ob1 /DNDEBUG -std:c++20 -MD"
        export_def = "src/server/apps/worldserver/Plugins/coa_plugin_exports.def"
    }
    official_modules = $modules
    db_schema_requirements = @{
        auth = "2026_10_28_00_auth"
        characters = "2026_10_28_00_characters"
        world = "2026_10_28_00_world"
    }
    client_compatibility = @{
        version = "3.3.5a"
        build = 12340
        ascension_support = $true
    }
}

$json = $candidateLock | ConvertTo-Json -Depth 6
$json | Set-Content $OutputFile -Encoding utf8
Write-Host "Candidate lock written to: $OutputFile"
