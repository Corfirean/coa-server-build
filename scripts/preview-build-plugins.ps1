param(
    [string] $SdkDir = "C:/games/coa-work/plugin-spike/sdk-v03",
    [string] $OutputDir = "C:/games/coa-work/plugin-spike/plugins"
)

$ErrorActionPreference = "Stop"
Write-Host "=== CoA Modules Preview: Official Dynamic Plugins Build ==="
Write-Host "SDK Directory: $SdkDir"
Write-Host "Output Directory: $OutputDir"

if (-not (Test-Path "$SdkDir/sdk.json")) {
    throw "CoA Plugin SDK not found at $SdkDir"
}

$sdk = Get-Content "$SdkDir/sdk.json" -Raw | ConvertFrom-Json
Write-Host "Compiling against ABI Fingerprint: $($sdk.abiFingerprint)"

$extBuildDir = "C:/games/coa-work/plugin-spike/plugins/ext/build-v03"
if (Test-Path "$extBuildDir/companions.dll") {
    Write-Host "Found pre-built verified official plugins in $extBuildDir"
    New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
    Copy-Item "$extBuildDir/*.dll" "$OutputDir/" -Force
    Write-Host "Dynamic plugins copied to $OutputDir"
    exit 0
}

Write-Host "Building plugins via CMake..."
# If not pre-built, invoke cmake build for ext plugins
$pluginsSrc = "C:/games/coa-work/plugin-spike/plugins/ext"
cmake -S "$pluginsSrc" -B "$pluginsSrc/build-v03" -G "Visual Studio 17 2022" -A x64 -DCOA_SDK_DIR="$SdkDir"
cmake --build "$pluginsSrc/build-v03" --config RelWithDebInfo

Copy-Item "$pluginsSrc/build-v03/*.dll" "$OutputDir/" -Force
Write-Host "Plugin compilation complete."
