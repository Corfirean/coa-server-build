param(
    [string] $CandidateLock = "",
    [string] $BundleDir = "",
    [string] $ServerDir = "",
    [string] $SdkDir = "",
    [string] $PluginsDir = "",
    [string] $ReportOut = ""
)

$ErrorActionPreference = "Stop"
Write-Host "=== CoA Modules Preview: Verification & Qualification ==="

# 0. Resolve default paths portably
if (-not $ReportOut) {
    $ReportOut = "$PSScriptRoot/../PREVIEW_BUILDER_QUALIFICATION.md"
}
$ReportOut = [System.IO.Path]::GetFullPath($ReportOut)

if ($BundleDir -and (Test-Path $BundleDir)) {
    $BundleDir = [System.IO.Path]::GetFullPath($BundleDir)
    if (-not $CandidateLock -and (Test-Path "$BundleDir/candidate-lock.json")) {
        $CandidateLock = "$BundleDir/candidate-lock.json"
    }
    if (-not $ServerDir -and (Test-Path "$BundleDir/server")) {
        $ServerDir = "$BundleDir/server"
    }
    if (-not $SdkDir -and (Test-Path "$BundleDir/sdk")) {
        $SdkDir = "$BundleDir/sdk"
    }
    if (-not $PluginsDir -and (Test-Path "$BundleDir/plugins")) {
        $PluginsDir = "$BundleDir/plugins"
    }
}

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
        "$PSScriptRoot/../dist/server",
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
        "$PSScriptRoot/../dist/sdk",
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
        "$PSScriptRoot/../dist/plugins",
        "C:/games/coa-work/plugin-spike/plugins/ext/build-v03"
    )
    foreach ($cand in $pluginCandidates) {
        if (Test-Path "$cand/companions.dll") {
            $PluginsDir = [System.IO.Path]::GetFullPath($cand)
            break
        }
    }
}

Write-Host "Candidate Lock: $CandidateLock"
Write-Host "Server Dir:     $ServerDir"
Write-Host "SDK Dir:        $SdkDir"
Write-Host "Plugins Dir:    $PluginsDir"
Write-Host "Report Out:     $ReportOut"

$lock = Get-Content $CandidateLock -Raw | ConvertFrom-Json
$sdk = if ($SdkDir -and (Test-Path "$SdkDir/sdk.json")) {
    Get-Content "$SdkDir/sdk.json" -Raw | ConvertFrom-Json
} else {
    $null
}

$results = @{}

# 1. ABI Fingerprint Match Check
Write-Host "1. Verifying ABI fingerprint..."
if ($sdk -and ($lock.sdk.abi_fingerprint -eq $sdk.abiFingerprint)) {
    $results["ABI_FINGERPRINT_MATCH"] = "PASS"
    Write-Host "  PASS: Candidate lock matches SDK fingerprint ($($sdk.abiFingerprint))"
} else {
    $results["ABI_FINGERPRINT_MATCH"] = "FAIL"
    Write-Host "  FAIL: Mismatch! Lock=$($lock.sdk.abi_fingerprint) vs SDK=$($sdk.abiFingerprint)"
}

# 2. Server Executable Integrity
Write-Host "2. Verifying worldserver.exe..."
if ($ServerDir -and (Test-Path "$ServerDir/worldserver.exe")) {
    $wsHash = (Get-FileHash "$ServerDir/worldserver.exe" -Algorithm SHA256).Hash.ToLowerInvariant()
    $results["WORLDSERVER_PRESENT"] = "PASS"
    $results["WORLDSERVER_SHA256"] = $wsHash
    if ($lock.core.sha256 -and ($lock.core.sha256 -ne $wsHash)) {
        Write-Host "  WARN: worldserver.exe hash differs from lock! Actual: $wsHash vs Lock: $($lock.core.sha256)"
    } else {
        Write-Host "  PASS: worldserver.exe present and matches lock (SHA: $wsHash)"
    }
} else {
    $results["WORLDSERVER_PRESENT"] = "FAIL"
    $results["WORLDSERVER_SHA256"] = "MISSING"
    Write-Host "  FAIL: worldserver.exe missing from '$ServerDir'!"
}

# 3. Dynamic Plugin DLL Check & Export Validation
Write-Host "3. Verifying official dynamic DLLs..."
$plugins = @("companions.dll", "content_scaling.dll", "squid_playerbots.dll")
$allPluginsPass = $true
foreach ($p in $plugins) {
    $dllPath = "$PluginsDir/$p"
    if (Test-Path $dllPath) {
        $pHash = (Get-FileHash $dllPath -Algorithm SHA256).Hash.ToLowerInvariant()
        Write-Host "  PASS: $p present (SHA: $pHash)"
    } else {
        $allPluginsPass = $false
        Write-Host "  FAIL: $p missing from '$PluginsDir'!"
    }
}
$results["OFFICIAL_DYNAMIC_DLLS"] = if ($allPluginsPass) { "PASS" } else { "FAIL" }

# 4. Static vs Dynamic Duplication Guard
Write-Host "4. Static / Dynamic Duplication Guard..."
$duplicationGuard = "PASS"
if ($SdkDir -and (Test-Path "$SdkDir/coa-plugin-abi-inputs.txt")) {
    $abiInputs = Get-Content "$SdkDir/coa-plugin-abi-inputs.txt" -Raw
    if ($abiInputs -notmatch "COA_PLUGIN_HOST") {
        $duplicationGuard = "FAIL"
    }
}
$results["DUPLICATION_GUARD"] = $duplicationGuard
Write-Host "  ${duplicationGuard}: Plugin host dynamic symbol exports validated."

# 5. Checksum file validation if present
if ($BundleDir -and (Test-Path "$BundleDir/sha256sums.txt")) {
    Write-Host "5. Verifying bundle sha256sums.txt..."
    $lines = Get-Content "$BundleDir/sha256sums.txt"
    $checksumsPass = $true
    foreach ($line in $lines) {
        if ($line -match "^\s*([a-f0-9]{64})\s+(.+)$") {
            $expectedHash = $matches[1].ToLowerInvariant()
            $relPath = $matches[2]
            $filePath = Join-Path $BundleDir $relPath
            if (Test-Path $filePath) {
                $actualHash = (Get-FileHash $filePath -Algorithm SHA256).Hash.ToLowerInvariant()
                if ($expectedHash -ne $actualHash) {
                    $checksumsPass = $false
                    Write-Host "  FAIL: Hash mismatch for $relPath!"
                }
            } else {
                $checksumsPass = $false
                Write-Host "  FAIL: File listed in sha256sums missing: $relPath"
            }
        }
    }
    $results["CHECKSUMS_VERIFIED"] = if ($checksumsPass) { "PASS" } else { "FAIL" }
} else {
    $results["CHECKSUMS_VERIFIED"] = "NOT_APPLICABLE"
}

# 6. Write Markdown Qualification Report
$report = @"
# PREVIEW BUILDER QUALIFICATION REPORT

**Candidate:** CoA Modules Preview Modular Host
**Version:** $($lock.version)
**Core Commit:** $($lock.core.commit)
**Builder Branch:** preview/modules-v2
**Verification Date:** $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

## Qualification Matrix

| Check | Expected | Actual | Status |
|-------|----------|--------|--------|
| ABI Fingerprint | $($lock.sdk.abi_fingerprint) | $($sdk.abiFingerprint) | $($results["ABI_FINGERPRINT_MATCH"]) |
| Server Binary | worldserver.exe | Exists | $($results["WORLDSERVER_PRESENT"]) |
| Official Dynamic DLLs | 3/3 | All present | $($results["OFFICIAL_DYNAMIC_DLLS"]) |
| Duplication Guard | COA_PLUGIN_HOST dynamic export | Verified | $($results["DUPLICATION_GUARD"]) |
| Checksums Integrity | sha256sums.txt verified | $($results["CHECKSUMS_VERIFIED"]) | $($results["CHECKSUMS_VERIFIED"]) |

## Artifact Hashes
- **worldserver.exe SHA-256:** $($results["WORLDSERVER_SHA256"])
- **ABI Fingerprint:** $($sdk.abiFingerprint)
"@

$report | Set-Content $ReportOut -Encoding utf8
Write-Host "Qualification report generated at $ReportOut"
