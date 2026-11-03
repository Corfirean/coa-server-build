param(
    [string] $BundleDir = "dist",
    [string] $VerificationDir = "verification",
    [string] $ChannelMetadataDir = "updates",
    [string] $UpdaterPackage = "",
    [string] $TauriConfig = "C:/games/coa-server-manager-preview/src-tauri/tauri.conf.json",
    [string] $TrustedPubkey = "",
    [switch] $RequireSignature
)

$ErrorActionPreference = "Stop"
Write-Host "=== Pre-Publish Gate Verification (Cryptographic & Candidate Binding) ==="

# 1. Verify and Load Candidate Lock
$lockPath = Join-Path $BundleDir "candidate-lock.json"
if (-not (Test-Path $lockPath)) {
    throw "PRE-PUBLISH GATE FAILED: candidate-lock.json missing from bundle directory '$BundleDir'!"
}
$lock = Get-Content $lockPath -Raw | ConvertFrom-Json
Write-Host "  Candidate Version:   $($lock.version)"
Write-Host "  Core Revision:       $($lock.core.commit)"
Write-Host "  SDK ABI Fingerprint: $($lock.sdk.abi_fingerprint)"

# 2. Verify Qualification Verdict and Ensure Exact Candidate Binding (P0-4)
$verdictFile = Join-Path $VerificationDir "preview-qualification-verdict.json"
if (-not (Test-Path $verdictFile)) {
    throw "PRE-PUBLISH GATE FAILED: preview-qualification-verdict.json missing from '$VerificationDir'! Candidate qualification was not completed."
}
$verdict = Get-Content $verdictFile -Raw | ConvertFrom-Json
if ($verdict.status -ne "PASS" -or -not $verdict.qualified) {
    $f = if ($verdict.failed_checks) { $verdict.failed_checks -join ', ' } else { "Unknown" }
    throw "PRE-PUBLISH GATE FAILED: Candidate failed qualification checks! Status: $($verdict.status), Failed checks: $f"
}

# Immutable binding check: Verdict must match Candidate Lock
if ($verdict.candidate_version -ne $lock.version) {
    throw "PRE-PUBLISH GATE FAILED: Mixed candidate assets! Verdict version ($($verdict.candidate_version)) does not match candidate lock version ($($lock.version))."
}
if ($verdict.core_commit -ne $lock.core.commit) {
    throw "PRE-PUBLISH GATE FAILED: Mixed candidate assets! Verdict core commit ($($verdict.core_commit)) does not match candidate lock core commit ($($lock.core.commit))."
}
if ($verdict.builder_commit -ne $lock.builder.commit) {
    throw "PRE-PUBLISH GATE FAILED: Mixed candidate assets! Verdict builder commit ($($verdict.builder_commit)) does not match candidate lock builder commit ($($lock.builder.commit))."
}
if ($verdict.sdk_abi_fingerprint -ne $lock.sdk.abi_fingerprint) {
    throw "PRE-PUBLISH GATE FAILED: Mixed candidate assets! Verdict SDK ABI fingerprint ($($verdict.sdk_abi_fingerprint)) does not match candidate lock ($($lock.sdk.abi_fingerprint))."
}
Write-Host "  PASS: Candidate qualification verdict confirmed and bound to candidate lock ($($verdict.status))."

# 3. Verify Bundle Critical Assets & Physical Integrity
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

# Verify physical host hash and size against lock
$actualWsHash = (Get-FileHash (Join-Path $BundleDir "server/worldserver.exe") -Algorithm SHA256).Hash.ToLowerInvariant()
$actualWsSize = (Get-Item (Join-Path $BundleDir "server/worldserver.exe")).Length
if ($actualWsHash -ne $lock.core.sha256.ToLowerInvariant()) {
    throw "PRE-PUBLISH GATE FAILED: worldserver.exe SHA-256 ($actualWsHash) does not match candidate lock ($($lock.core.sha256))!"
}
if ($lock.core.size -and ([int64]$actualWsSize -ne [int64]$lock.core.size)) {
    throw "PRE-PUBLISH GATE FAILED: worldserver.exe size ($actualWsSize bytes) does not match candidate lock ($($lock.core.size) bytes)!"
}
Write-Host "  PASS: All critical bundle assets verified present, non-empty, and matching lock."

# 4. Verify Channel Metadata Manifests Binding (P0-4)
$compManifestFile = Join-Path $ChannelMetadataDir "csm-preview-components.json"
if (-not (Test-Path $compManifestFile)) {
    throw "PRE-PUBLISH GATE FAILED: Channel metadata csm-preview-components.json missing from '$ChannelMetadataDir'!"
}
$comp = Get-Content $compManifestFile -Raw | ConvertFrom-Json
if ($comp.version -ne $lock.version) {
    throw "PRE-PUBLISH GATE FAILED: Mixed candidate assets! Component manifest version ($($comp.version)) differs from lock ($($lock.version))."
}
if ($comp.core.commit -ne $lock.core.commit) {
    throw "PRE-PUBLISH GATE FAILED: Mixed candidate assets! Component manifest core commit ($($comp.core.commit)) differs from lock ($($lock.core.commit))."
}
if ($comp.core.sha256 -ne $lock.core.sha256) {
    throw "PRE-PUBLISH GATE FAILED: Mixed candidate assets! Component manifest core SHA-256 ($($comp.core.sha256)) differs from lock ($($lock.core.sha256))."
}
if ($comp.sdk.abi_fingerprint -ne $lock.sdk.abi_fingerprint) {
    throw "PRE-PUBLISH GATE FAILED: Mixed candidate assets! Component manifest SDK ABI ($($comp.sdk.abi_fingerprint)) differs from lock."
}
if (-not $comp.sdk.version -or $comp.sdk.version -ne $lock.sdk.version) {
    throw "PRE-PUBLISH GATE FAILED: Component manifest has invalid or mismatched sdk.version ('$($comp.sdk.version)')."
}
if ($comp.sdk.download_url -match "coa-plugin-sdk-v\.zip") {
    throw "PRE-PUBLISH GATE FAILED: Component manifest has unversioned sdk download_url."
}
Write-Host "  PASS: Contract 2 component manifest validated and bound to candidate lock."

# 5. Cryptographic Signature Verification of Contract 1 (P0-2)
$appManifestFile = Join-Path $ChannelMetadataDir "csm-preview-app-latest.json"
if (-not (Test-Path $appManifestFile)) {
    throw "PRE-PUBLISH GATE FAILED: App updater manifest csm-preview-app-latest.json missing from '$ChannelMetadataDir'!"
}
$appManifest = Get-Content $appManifestFile -Raw | ConvertFrom-Json
$winPlatform = $appManifest.platforms."windows-x86_64"
if (-not $winPlatform) {
    throw "PRE-PUBLISH GATE FAILED: App updater manifest missing windows-x86_64 platform configuration!"
}

$signature = $winPlatform.signature
if ([string]::IsNullOrWhiteSpace($signature)) {
    throw "PRE-PUBLISH GATE FAILED: updates/csm-preview-app-latest.json is unsigned! Production/preview publication strictly requires a valid cryptographic signature."
}

# Resolve Trusted Public Key
$pubkey = $TrustedPubkey
if (-not $pubkey -and $TauriConfig -and (Test-Path $TauriConfig)) {
    $tConfig = Get-Content $TauriConfig -Raw | ConvertFrom-Json
    $pubkey = $tConfig.plugins.updater.pubkey
}

if (-not $pubkey) {
    throw "PRE-PUBLISH GATE FAILED: Trusted updater public key could not be resolved from Tauri configuration or -TrustedPubkey."
}

# Resolve Target Package to Verify
$packageToVerify = $UpdaterPackage
if (-not $packageToVerify) {
    # Check if a package file exists in BundleDir/manager or next to manifest
    $candidates = @(
        (Join-Path $BundleDir "manager/csm-modules-preview_$($appManifest.version)_x64_en-US.msi.zip"),
        (Join-Path $BundleDir "manager/csm-modules-preview_$($appManifest.version)_x64_en-US.zip"),
        (Join-Path $BundleDir "manager/app.zip")
    )
    foreach ($cand in $candidates) {
        if (Test-Path $cand) {
            $packageToVerify = $cand
            break
        }
    }
}

if (-not $packageToVerify -or -not (Test-Path $packageToVerify)) {
    # If the installer binary package is not downloaded or provided, publication cannot be verified
    throw "PRE-PUBLISH GATE FAILED: Cannot cryptographically verify updater signature: candidate installer package missing! (Checked '$packageToVerify')"
}

# Run Real Cryptographic Verifier Script
Write-Host "  Running cryptographic Minisign/Ed25519 signature verification on '$packageToVerify'..."
$verifierScript = Join-Path $PSScriptRoot "verify-updater-signature.py"
$verifyOutput = python "$verifierScript" `
    --pubkey "$pubkey" `
    --package "$packageToVerify" `
    --signature "$signature" `
    --version "$($appManifest.version)" 2>&1

if ($LASTEXITCODE -ne 0) {
    throw "PRE-PUBLISH GATE FAILED: Cryptographic signature verification failed!`n$verifyOutput"
}

Write-Host "  PASS: Cryptographic Minisign signature verified successfully against trusted public key."
Write-Host "SUCCESS: Pre-publish qualification gate passed completely." -ForegroundColor Green
exit 0
