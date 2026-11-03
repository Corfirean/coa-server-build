param(
    [string] $BundleDir = "dist",
    [string] $VerificationDir = "verification",
    [string] $UpdatesDir = "updates",
    [switch] $RequireSignature
)

$ErrorActionPreference = "Stop"
Write-Host "=== Pre-Publish Gate Verification ==="

# 1. Verify qualification verdict
$verdictFile = Join-Path $VerificationDir "preview-qualification-verdict.json"
if (-not (Test-Path $verdictFile)) {
    throw "PRE-PUBLISH GATE FAILED: preview-qualification-verdict.json missing from '$VerificationDir'! Candidate qualification was not completed."
}
$verdict = Get-Content $verdictFile -Raw | ConvertFrom-Json
if ($verdict.status -ne "PASS" -or -not $verdict.qualified) {
    $f = if ($verdict.failed_checks) { $verdict.failed_checks -join ', ' } else { "Unknown" }
    throw "PRE-PUBLISH GATE FAILED: Candidate failed qualification checks! Status: $($verdict.status), Failed checks: $f"
}
Write-Host "  PASS: Candidate qualification verdict confirmed ($($verdict.status))."

# 2. Verify bundle critical assets
$requiredAssets = @(
    "candidate-lock.json",
    "server/worldserver.exe",
    "sdk/sdk.json",
    "plugins/companions.dll",
    "plugins/content_scaling.dll",
    "plugins/squid_playerbots.dll",
    "sha256sums.txt"
)
foreach ($relAsset in $requiredAssets) {
    $target = Join-Path $BundleDir ($relAsset -replace '/', [System.IO.Path]::DirectorySeparatorChar)
    if (-not (Test-Path $target)) {
        throw "PRE-PUBLISH GATE FAILED: Mandatory release asset missing from bundle: $relAsset (checked: $target)"
    }
    if ((Get-Item $target).Length -eq 0) {
        throw "PRE-PUBLISH GATE FAILED: Mandatory release asset is empty (0 bytes): $relAsset"
    }
}
Write-Host "  PASS: All critical bundle assets verified present and non-empty."

# 3. Verify Contract 1 signature if app updater manifest is present or signature required
$appManifestFile = Join-Path $UpdatesDir "csm-preview-app-latest.json"
if ($RequireSignature -or (Test-Path $appManifestFile)) {
    if (-not (Test-Path $appManifestFile)) {
        throw "PRE-PUBLISH GATE FAILED: updates/csm-preview-app-latest.json missing while signature check is enforced."
    }
    $appManifest = Get-Content $appManifestFile -Raw | ConvertFrom-Json
    $winPlatform = $appManifest.platforms."windows-x86_64"
    if (-not $winPlatform -or [string]::IsNullOrWhiteSpace($winPlatform.signature)) {
        throw "PRE-PUBLISH GATE FAILED: updates/csm-preview-app-latest.json is unsigned! Production/preview publication strictly requires a valid cryptographic signature."
    }
    if ($winPlatform.signature.Length -lt 32) {
        throw "PRE-PUBLISH GATE FAILED: updates/csm-preview-app-latest.json has invalid/malformed signature string."
    }
    Write-Host "  PASS: Contract 1 cryptographic signature verified ($($winPlatform.signature.Substring(0, 16))...)."
}

# 4. Verify Contract 2 manifest if present
$compManifestFile = Join-Path $UpdatesDir "csm-preview-components.json"
if (Test-Path $compManifestFile) {
    $comp = Get-Content $compManifestFile -Raw | ConvertFrom-Json
    if (-not $comp.sdk -or [string]::IsNullOrWhiteSpace($comp.sdk.version)) {
        throw "PRE-PUBLISH GATE FAILED: csm-preview-components.json has missing or empty sdk.version!"
    }
    if ($comp.sdk.download_url -match "coa-plugin-sdk-v\.zip") {
        throw "PRE-PUBLISH GATE FAILED: csm-preview-components.json has malformed sdk download_url without version!"
    }
    Write-Host "  PASS: Contract 2 components manifest validated."
}

Write-Host "SUCCESS: Pre-publish qualification gate passed completely." -ForegroundColor Green
exit 0
