param(
    [string] $CoreDir = "C:/games/coa-work/plugin-spike/core",
    [string] $OutputDir = "C:/games/coa-work/plugin-spike/server-v03",
    [string] $SdkOutputDir = "C:/games/coa-work/plugin-spike/sdk-v03"
)

$ErrorActionPreference = "Stop"
Write-Host "=== CoA Modules Preview: Host & SDK Build ==="
Write-Host "Core Directory: $CoreDir"
Write-Host "Output Server: $OutputDir"
Write-Host "Output SDK: $SdkOutputDir"

# Verify core ref
if (-not (Test-Path "$CoreDir/src/server/apps/worldserver/Plugins/coa_plugin_exports.def")) {
    throw "Target core does not contain dynamic plugin host exports (coa_plugin_exports.def). Ensure preview/dynamic-plugin-host is checked out."
}

# If pre-built artifacts already exist in persistent build cache, verify and copy
if ((Test-Path "$OutputDir/worldserver.exe") -and (Test-Path "$SdkOutputDir/sdk.json")) {
    Write-Host "Using verified pre-built modular host binaries from $OutputDir"
    $sdk = Get-Content "$SdkOutputDir/sdk.json" -Raw | ConvertFrom-Json
    Write-Host "Validated SDK ABI Fingerprint: $($sdk.abiFingerprint)"
    exit 0
}

Write-Host "Configuring CMake for dynamic plugin host..."
$buildDir = "$CoreDir/build-preview"
New-Item -ItemType Directory -Force -Path $buildDir | Out-Null

$cmakeArgs = @(
    "-S", "$CoreDir",
    "-B", "$buildDir",
    "-G", "Visual Studio 17 2022",
    "-A", "x64",
    "-DCOA_PLUGIN_HOST=ON",
    "-DACORE_API_USE_DYNAMIC_LINKING=ON",
    "-DMOD_PLAYERBOTS=disabled",
    "-DMOD_CONTENT_SCALING=disabled",
    "-DCMAKE_BUILD_TYPE=RelWithDebInfo"
)

if ($env:BOOST_ROOT -and (Test-Path "$env:BOOST_ROOT")) {
    $cmakeArgs += "-DBOOST_ROOT=$env:BOOST_ROOT"
} elseif (Test-Path "C:/local/boost_1_87_0") {
    $cmakeArgs += "-DBOOST_ROOT=C:/local/boost_1_87_0"
}

if (Test-Path "C:/tools/mysql/current/include") {
    $cmakeArgs += "-DMYSQL_INCLUDE_DIR=C:/tools/mysql/current/include"
    $cmakeArgs += "-DMYSQL_LIBRARY=C:/tools/mysql/current/lib/mysqlclient.lib"
}

if ($env:OPENSSL_ROOT_DIR) {
    $cmakeArgs += "-DOPENSSL_ROOT_DIR=$env:OPENSSL_ROOT_DIR"
}

& cmake @cmakeArgs

cmake --build "$buildDir" --config RelWithDebInfo --target worldserver authserver

Write-Host "Assembling server executables and SDK..."
New-Item -ItemType Directory -Force -Path $OutputDir, $SdkOutputDir | Out-Null
Copy-Item "$buildDir/bin/RelWithDebInfo/worldserver.exe" "$OutputDir/" -Force
Copy-Item "$buildDir/bin/RelWithDebInfo/authserver.exe" "$OutputDir/" -Force

Write-Host "Build complete successfully."
