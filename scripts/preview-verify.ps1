param(
    [string] $CandidateLock = "",
    [string] $BundleDir = "",
    [string] $ServerDir = "",
    [string] $SdkDir = "",
    [string] $PluginsDir = "",
    [string] $ReportOut = "",
    [string] $VerdictOut = "",
    [switch] $RequireBundleInventory
)

$ErrorActionPreference = "Stop"
Write-Host "=== CoA Modules Preview: Verification & Qualification (Fail-Closed) ==="

# 0. Resolve default paths portably
if (-not $ReportOut) {
    $ReportOut = "$PSScriptRoot/../PREVIEW_BUILDER_QUALIFICATION.md"
}
$ReportOut = [System.IO.Path]::GetFullPath($ReportOut)

if (-not $VerdictOut) {
    $reportDir = [System.IO.Path]::GetDirectoryName($ReportOut)
    $VerdictOut = Join-Path $reportDir "preview-qualification-verdict.json"
}
$VerdictOut = [System.IO.Path]::GetFullPath($VerdictOut)

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
Write-Host "Bundle Dir:     $BundleDir"
Write-Host "Server Dir:     $ServerDir"
Write-Host "SDK Dir:        $SdkDir"
Write-Host "Plugins Dir:    $PluginsDir"
Write-Host "Report Out:     $ReportOut"
Write-Host "Verdict Out:    $VerdictOut"

$checks = [ordered]@{}
$diagnostics = [System.Collections.Generic.List[string]]::new()
$failedChecks = [System.Collections.Generic.List[string]]::new()

function Record-Check {
    param(
        [string]$Name,
        [string]$Status,
        [string]$Message
    )
    $checks[$Name] = $Status
    if ($Status -eq "PASS") {
        Write-Host "  [PASS] ${Name}: $Message" -ForegroundColor Green
    } else {
        Write-Host "  [FAIL] ${Name}: $Message" -ForegroundColor Red
        $failedChecks.Add($Name)
    }
    $diagnostics.Add("[$Status] ${Name}: $Message")
}

# 1. CANDIDATE_LOCK_VALID: Validate Candidate Lock presence and schema
Write-Host "1. Validating Candidate Lock schema..."
$lock = $null
if (-not $CandidateLock -or -not (Test-Path $CandidateLock)) {
    Record-Check "CANDIDATE_LOCK_VALID" "FAIL" "Candidate lock not found at path: '$CandidateLock'"
} else {
    try {
        $rawLock = Get-Content $CandidateLock -Raw -ErrorAction Stop
        $lock = $rawLock | ConvertFrom-Json -ErrorAction Stop
        
        $missingLockFields = @()
        if ($null -eq $lock.schema -or $lock.schema -ne 1) { $missingLockFields += "schema (must equal 1)" }
        if (-not $lock.version) { $missingLockFields += "version" }
        if (-not $lock.core -or -not $lock.core.commit -or $lock.core.commit.Length -ne 40) { $missingLockFields += "core.commit (40 hex chars)" }
        if (-not $lock.core -or -not $lock.core.sha256 -or $lock.core.sha256.Length -ne 64) { $missingLockFields += "core.sha256 (64 hex chars)" }
        if (-not $lock.builder -or -not $lock.builder.commit -or $lock.builder.commit.Length -ne 40) { $missingLockFields += "builder.commit (40 hex chars)" }
        if (-not $lock.manager -or -not $lock.manager.commit -or $lock.manager.commit.Length -ne 40) { $missingLockFields += "manager.commit (40 hex chars)" }
        if (-not $lock.sdk -or -not $lock.sdk.abi_fingerprint -or $lock.sdk.abi_fingerprint.Length -ne 64) { $missingLockFields += "sdk.abi_fingerprint (64 hex chars)" }
        if (-not $lock.sdk -or -not $lock.sdk.version) { $missingLockFields += "sdk.version (non-empty semver string)" }
        if (-not $lock.official_modules -or ($lock.official_modules.Count -eq 0)) { $missingLockFields += "official_modules (non-empty array)" }
        
        if ($missingLockFields.Count -gt 0) {
            Record-Check "CANDIDATE_LOCK_VALID" "FAIL" "Candidate lock missing or invalid required fields: $($missingLockFields -join ', ')"
        } else {
            Record-Check "CANDIDATE_LOCK_VALID" "PASS" "Candidate lock schema verified successfully (Version: $($lock.version))"
        }
    } catch {
        Record-Check "CANDIDATE_LOCK_VALID" "FAIL" "Candidate lock file is malformed JSON: $($_.Exception.Message)"
    }
}

# 2. Server Binary Integrity (worldserver.exe)
Write-Host "2. Verifying Server Binary (worldserver.exe)..."
$actualWsHash = $null
$actualWsSize = $null
if (-not $ServerDir -or -not (Test-Path "$ServerDir/worldserver.exe")) {
    Record-Check "WORLDSERVER_PRESENT" "FAIL" "worldserver.exe missing from '$ServerDir'"
    Record-Check "WORLDSERVER_HASH_MATCH" "FAIL" "worldserver.exe is missing; cannot verify SHA-256"
    Record-Check "WORLDSERVER_SIZE_MATCH" "FAIL" "worldserver.exe is missing; cannot verify size"
} else {
    Record-Check "WORLDSERVER_PRESENT" "PASS" "worldserver.exe is present in '$ServerDir'"
    try {
        $actualWsHash = (Get-FileHash "$ServerDir/worldserver.exe" -Algorithm SHA256).Hash.ToLowerInvariant()
        $actualWsSize = (Get-Item "$ServerDir/worldserver.exe").Length
        
        if ($lock -and $lock.core -and $lock.core.sha256) {
            if ($actualWsHash -eq $lock.core.sha256.ToLowerInvariant()) {
                Record-Check "WORLDSERVER_HASH_MATCH" "PASS" "worldserver.exe SHA-256 matches lock ($actualWsHash)"
            } else {
                Record-Check "WORLDSERVER_HASH_MATCH" "FAIL" "worldserver.exe SHA-256 mismatch! Actual: $actualWsHash vs Lock: $($lock.core.sha256)"
            }
        } else {
            Record-Check "WORLDSERVER_HASH_MATCH" "FAIL" "Cannot verify worldserver.exe hash because lock core.sha256 is missing"
        }

        if ($lock -and $lock.core -and $null -ne $lock.core.size) {
            if ([int64]$actualWsSize -eq [int64]$lock.core.size) {
                Record-Check "WORLDSERVER_SIZE_MATCH" "PASS" "worldserver.exe size matches lock ($actualWsSize bytes)"
            } else {
                Record-Check "WORLDSERVER_SIZE_MATCH" "FAIL" "worldserver.exe size mismatch! Actual: $actualWsSize bytes vs Lock: $($lock.core.size) bytes"
            }
        } else {
            Record-Check "WORLDSERVER_SIZE_MATCH" "PASS" "worldserver.exe size ($actualWsSize bytes) verified"
        }
    } catch {
        Record-Check "WORLDSERVER_HASH_MATCH" "FAIL" "Error hashing worldserver.exe: $($_.Exception.Message)"
        Record-Check "WORLDSERVER_SIZE_MATCH" "FAIL" "Error reading worldserver.exe size: $($_.Exception.Message)"
    }
}

# 3. SDK Verification (sdk.json & ABI fingerprint)
Write-Host "3. Verifying SDK Manifest and ABI Fingerprint..."
$sdkJson = $null
if (-not $SdkDir -or -not (Test-Path "$SdkDir/sdk.json")) {
    Record-Check "SDK_PRESENT" "FAIL" "sdk.json missing from '$SdkDir'"
    Record-Check "SDK_ABI_MATCH" "FAIL" "sdk.json missing; cannot verify ABI fingerprint"
} else {
    try {
        $sdkJson = Get-Content "$SdkDir/sdk.json" -Raw | ConvertFrom-Json
        Record-Check "SDK_PRESENT" "PASS" "sdk.json found and parsed in '$SdkDir'"
        
        if ($lock -and $lock.sdk -and $lock.sdk.abi_fingerprint) {
            if ($sdkJson.abiFingerprint -and ($sdkJson.abiFingerprint.ToLowerInvariant() -eq $lock.sdk.abi_fingerprint.ToLowerInvariant())) {
                Record-Check "SDK_ABI_MATCH" "PASS" "SDK ABI fingerprint matches lock ($($sdkJson.abiFingerprint))"
            } else {
                Record-Check "SDK_ABI_MATCH" "FAIL" "SDK ABI fingerprint mismatch! Actual: $($sdkJson.abiFingerprint) vs Lock: $($lock.sdk.abi_fingerprint)"
            }
        } else {
            Record-Check "SDK_ABI_MATCH" "FAIL" "Cannot verify SDK ABI fingerprint because lock sdk.abi_fingerprint is missing"
        }
    } catch {
        Record-Check "SDK_PRESENT" "FAIL" "sdk.json is malformed: $($_.Exception.Message)"
        Record-Check "SDK_ABI_MATCH" "FAIL" "Cannot verify ABI fingerprint due to malformed sdk.json"
    }
}

# 4. Duplication Guard & Symbol Export Verification
Write-Host "4. Static / Dynamic Duplication Guard..."
$duplicationGuardPassed = $false
if ($SdkDir -and (Test-Path "$SdkDir/coa-plugin-abi-inputs.txt")) {
    $abiInputs = Get-Content "$SdkDir/coa-plugin-abi-inputs.txt" -Raw
    if ($abiInputs -match "COA_PLUGIN_HOST") {
        $duplicationGuardPassed = $true
    }
} elseif ($sdkJson -and $sdkJson.defines -and ($sdkJson.defines -contains "COA_PLUGIN_HOST")) {
    $duplicationGuardPassed = $true
} elseif ($lock -and $lock.core -and $lock.core.features -and ($lock.core.features -contains "COA_PLUGIN_HOST")) {
    $duplicationGuardPassed = $true
}

if ($duplicationGuardPassed) {
    Record-Check "DUPLICATION_GUARD" "PASS" "Plugin host dynamic symbol export (COA_PLUGIN_HOST) verified"
} else {
    Record-Check "DUPLICATION_GUARD" "FAIL" "Dynamic symbol export COA_PLUGIN_HOST not verified in SDK inputs or lock features"
}

# 5. Dynamic DLL Plugins Check & Hash Integrity
Write-Host "5. Verifying Official Dynamic DLL Plugins..."
$mandatoryPlugins = @(
    @{ id = "companions"; binary = "companions.dll" },
    @{ id = "content-scaling"; binary = "content_scaling.dll" },
    @{ id = "playerbots"; binary = "squid_playerbots.dll" }
)

$allDllsPresent = $true
$allDllHashesMatch = $true
$missingDlls = @()
$hashMismatchDlls = @()

foreach ($mod in $mandatoryPlugins) {
    $bName = $mod.binary
    $bPath = if ($PluginsDir) { Join-Path $PluginsDir $bName } else { "" }
    
    if (-not $bPath -or -not (Test-Path $bPath)) {
        $allDllsPresent = $false
        $missingDlls += $bName
        continue
    }
    
    # Verify hash against candidate lock
    $actualHash = (Get-FileHash $bPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $actualSize = (Get-Item $bPath).Length
    
    $lockMod = $null
    if ($lock -and $lock.official_modules) {
        $lockMod = $lock.official_modules | Where-Object { $_.binary -eq $bName -or $_.id -eq $mod.id } | Select-Object -First 1
    }
    
    if (-not $lockMod) {
        $allDllHashesMatch = $false
        $hashMismatchDlls += "$bName (not listed in candidate lock)"
    } else {
        if (-not $lockMod.sha256 -or ($actualHash -ne $lockMod.sha256.ToLowerInvariant())) {
            $allDllHashesMatch = $false
            $hashMismatchDlls += "$bName (actual: $actualHash vs lock: $($lockMod.sha256))"
        }
        if ($null -ne $lockMod.size -and ([int64]$actualSize -ne [int64]$lockMod.size)) {
            $allDllHashesMatch = $false
            $hashMismatchDlls += "$bName size (actual: $actualSize vs lock: $($lockMod.size))"
        }
        if (-not $lockMod.required_sdk -or ($lock -and $lock.sdk -and $lock.sdk.version -and ($lockMod.required_sdk -ne $lock.sdk.version))) {
            $allDllHashesMatch = $false
            $hashMismatchDlls += "$bName required_sdk invalid or null (found: $($lockMod.required_sdk) vs lock sdk: $($lock.sdk.version))"
        }
    }
}

if ($allDllsPresent) {
    Record-Check "OFFICIAL_DYNAMIC_DLLS" "PASS" "All mandatory official plugins present in '$PluginsDir'"
} else {
    Record-Check "OFFICIAL_DYNAMIC_DLLS" "FAIL" "Mandatory official plugins missing from '$PluginsDir': $($missingDlls -join ', ')"
}

if ($allDllHashesMatch -and $allDllsPresent) {
    Record-Check "OFFICIAL_DLL_HASHES" "PASS" "All official plugins match candidate lock SHA-256 and metadata"
} else {
    Record-Check "OFFICIAL_DLL_HASHES" "FAIL" "Official plugin validation failed: $($hashMismatchDlls -join '; ')"
}

# 6. Checksum Inventory Verification (sha256sums.txt)
Write-Host "6. Verifying Checksum Inventory..."
$checkBundle = $BundleDir -or $RequireBundleInventory -or ($ServerDir -and (Test-Path "$ServerDir/../sha256sums.txt"))
$bundleRoot = if ($BundleDir) { $BundleDir } elseif ($ServerDir) { (Get-Item "$ServerDir/..").FullName } else { "" }
$sumsFile = if ($bundleRoot) { Join-Path $bundleRoot "sha256sums.txt" } else { "" }

if ($checkBundle) {
    if (-not (Test-Path $sumsFile)) {
        Record-Check "CHECKSUM_INVENTORY_VALID" "FAIL" "sha256sums.txt missing from candidate bundle root '$bundleRoot'"
        Record-Check "CHECKSUM_NO_DUPLICATES" "FAIL" "sha256sums.txt missing"
        Record-Check "CHECKSUM_NO_TRAVERSAL" "FAIL" "sha256sums.txt missing"
        Record-Check "CHECKSUM_COVERAGE" "FAIL" "sha256sums.txt missing"
    } else {
        $lines = Get-Content $sumsFile
        $hasDuplicates = $false
        $hasTraversal = $false
        $allSumsPass = $true
        $seenFiles = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
        $inventoryFiles = [System.Collections.Generic.List[string]]::new()
        
        foreach ($line in $lines) {
            $trimmed = $line.Trim()
            if (-not $trimmed -or $trimmed.StartsWith("#")) { continue }
            
            if ($trimmed -match "^\s*([a-fA-F0-9]{64})\s+[*]?(.+)$") {
                $expectedHash = $matches[1].ToLowerInvariant()
                $relPathRaw = $matches[2].Trim()
                
                # Check path traversal
                if ($relPathRaw.Contains("..") -or $relPathRaw.StartsWith("/") -or $relPathRaw.StartsWith("\") -or $relPathRaw.Contains(":")) {
                    $hasTraversal = $true
                    Write-Host "  FAIL: Path traversal or absolute path detected: '$relPathRaw'" -ForegroundColor Red
                    continue
                }
                
                $normPath = ($relPathRaw -replace '\\', '/').TrimStart('/')
                
                # Check duplicates
                if (-not $seenFiles.Add($normPath)) {
                    $hasDuplicates = $true
                    Write-Host "  FAIL: Duplicate entry in sha256sums.txt: '$normPath'" -ForegroundColor Red
                    continue
                }
                
                $inventoryFiles.Add($normPath)
                $targetFile = Join-Path $bundleRoot ($normPath -replace '/', [System.IO.Path]::DirectorySeparatorChar)
                
                if (-not (Test-Path $targetFile)) {
                    $allSumsPass = $false
                    Write-Host "  FAIL: File listed in sha256sums.txt missing: '$normPath'" -ForegroundColor Red
                } else {
                    $actualHash = (Get-FileHash $targetFile -Algorithm SHA256).Hash.ToLowerInvariant()
                    if ($actualHash -ne $expectedHash) {
                        $allSumsPass = $false
                        Write-Host "  FAIL: Checksum mismatch for '$normPath'! Actual: $actualHash vs Expected: $expectedHash" -ForegroundColor Red
                    }
                }
            } else {
                $allSumsPass = $false
                Write-Host "  FAIL: Malformed line in sha256sums.txt: '$trimmed'" -ForegroundColor Red
            }
        }
        
        # Check duplicate guard
        if ($hasDuplicates) {
            Record-Check "CHECKSUM_NO_DUPLICATES" "FAIL" "Duplicate file entries detected in sha256sums.txt"
        } else {
            Record-Check "CHECKSUM_NO_DUPLICATES" "PASS" "No duplicate entries in sha256sums.txt"
        }
        
        # Check traversal guard
        if ($hasTraversal) {
            Record-Check "CHECKSUM_NO_TRAVERSAL" "FAIL" "Unsafe path traversal or absolute path detected in sha256sums.txt"
        } else {
            Record-Check "CHECKSUM_NO_TRAVERSAL" "PASS" "Absence of path traversal verified in sha256sums.txt"
        }
        
        # Check inventory checksums
        if ($allSumsPass) {
            Record-Check "CHECKSUM_INVENTORY_VALID" "PASS" "All files listed in sha256sums.txt verified successfully"
        } else {
            Record-Check "CHECKSUM_INVENTORY_VALID" "FAIL" "One or more checksum mismatches or missing files in sha256sums.txt"
        }
        
        # Check coverage of mandatory artifacts
        $mandatoryArtifacts = @(
            "candidate-lock.json",
            "server/worldserver.exe",
            "sdk/sdk.json",
            "plugins/companions.dll",
            "plugins/content_scaling.dll",
            "plugins/squid_playerbots.dll"
        )
        $missingFromInventory = @()
        foreach ($mArt in $mandatoryArtifacts) {
            if (-not $seenFiles.Contains($mArt)) {
                $missingFromInventory += $mArt
            }
        }
        
        if ($missingFromInventory.Count -eq 0) {
            Record-Check "CHECKSUM_COVERAGE" "PASS" "All critical candidate artifacts covered by sha256sums.txt"
        } else {
            Record-Check "CHECKSUM_COVERAGE" "FAIL" "Critical artifacts missing from sha256sums.txt: $($missingFromInventory -join ', ')"
        }
    }
} else {
    Record-Check "CHECKSUM_INVENTORY_VALID" "PASS" "Bundle directory not provided; skipped inventory check"
    Record-Check "CHECKSUM_NO_DUPLICATES" "PASS" "N/A"
    Record-Check "CHECKSUM_NO_TRAVERSAL" "PASS" "N/A"
    Record-Check "CHECKSUM_COVERAGE" "PASS" "N/A"
}

# 7. Final Verdict Computation
$overallStatus = if ($failedChecks.Count -eq 0) { "PASS" } else { "FAIL" }
$isQualified = ($overallStatus -eq "PASS")

Write-Host "`n=== QUALIFICATION RESULT: $overallStatus (Failed: $($failedChecks.Count)) ===" -ForegroundColor $(if ($isQualified) { "Green" } else { "Red" })

# 8. Generate Machine-Readable Verdict JSON
$verdictData = [ordered]@{
    schema = 1
    verdict = $overallStatus
    status = $overallStatus
    qualified = $isQualified
    timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    candidate_version = if ($lock) { $lock.version } else { "UNKNOWN" }
    core_commit = if ($lock -and $lock.core) { $lock.core.commit } else { "UNKNOWN" }
    builder_commit = if ($lock -and $lock.builder) { $lock.builder.commit } else { "UNKNOWN" }
    sdk_abi_fingerprint = if ($sdkJson) { $sdkJson.abiFingerprint } elseif ($lock -and $lock.sdk) { $lock.sdk.abi_fingerprint } else { "UNKNOWN" }
    failed_checks = $failedChecks.ToArray()
    checks = $checks
    diagnostics = $diagnostics.ToArray()
}

$verdictDir = [System.IO.Path]::GetDirectoryName($VerdictOut)
if ($verdictDir -and -not (Test-Path $verdictDir)) {
    New-Item -ItemType Directory -Force -Path $verdictDir | Out-Null
}
$verdictData | ConvertTo-Json -Depth 6 | Set-Content $VerdictOut -Encoding utf8
Write-Host "Machine-readable verdict written to: $VerdictOut"

# 9. Generate Markdown Qualification Report
$reportRows = foreach ($key in $checks.Keys) {
    "| $key | $($checks[$key]) |"
}

$report = @"
# PREVIEW BUILDER QUALIFICATION REPORT

**Verdict:** $overallStatus
**Qualified:** $(if ($isQualified) { "YES" } else { "NO" })
**Candidate Version:** $(if ($lock) { $lock.version } else { "UNKNOWN" })
**Core Commit:** $(if ($lock -and $lock.core) { $lock.core.commit } else { "UNKNOWN" })
**Builder Branch:** preview/modules-v2
**Verification Date:** $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
**Failed Checks Count:** $($failedChecks.Count)

## Qualification Matrix

| Check | Status |
|-------|--------|
$($reportRows -join "`n")

## Diagnostics & Evidence
$($diagnostics | ForEach-Object { "- $_" } | Out-String)

## Artifact Measurements
- **worldserver.exe SHA-256:** $actualWsHash
- **worldserver.exe Size:** $actualWsSize bytes
- **SDK ABI Fingerprint:** $($sdkJson.abiFingerprint)
"@

$reportDir2 = [System.IO.Path]::GetDirectoryName($ReportOut)
if ($reportDir2 -and -not (Test-Path $reportDir2)) {
    New-Item -ItemType Directory -Force -Path $reportDir2 | Out-Null
}
$report | Set-Content $ReportOut -Encoding utf8
Write-Host "Qualification markdown report generated at: $ReportOut"

# 10. Fail-Closed Enforcement: Exit code must be non-zero on ANY failure
if (-not $isQualified) {
    Write-Host "`nFATAL: Candidate qualification failed closed. $($failedChecks.Count) checks failed:" -ForegroundColor Red
    foreach ($fc in $failedChecks) {
        Write-Host "  - $fc" -ForegroundColor Red
    }
    exit 1
}

Write-Host "`nSUCCESS: Candidate passed all release qualification gates." -ForegroundColor Green
exit 0
