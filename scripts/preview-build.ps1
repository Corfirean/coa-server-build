# Builds the CoA plugin host (worldserver.exe + authserver.exe) and exports the CoA Plugin SDK from the
# same build tree. The two form a pair with one ABI fingerprint: plugins built against this SDK load only
# into this worldserver.exe. Runs in an MSVC developer environment (msvc-dev-cmd in CI, vcvars locally).
#
# Nothing is reused from earlier builds or from other machines: every run configures and compiles from the
# given core checkout.
param(
    [Parameter(Mandatory = $true)] [string] $CoreDir,
    [Parameter(Mandatory = $true)] [string] $BuildDir,
    [Parameter(Mandatory = $true)] [string] $OutDir,
    [string] $BoostRoot = $env:BOOST_ROOT,
    [string] $MysqlRoot = 'C:/tools/mysql/current',
    [string] $OpensslRoot = $env:OPENSSL_ROOT_DIR,
    [int] $Jobs = 4,
    [string] $ExpectCl = ''
)

$ErrorActionPreference = 'Stop'
function Invoke-Checked([string] $what, [scriptblock] $cmd) {
    & $cmd
    if ($LASTEXITCODE -ne 0) { throw "$what failed with exit code $LASTEXITCODE" }
}

$CoreDir = (Resolve-Path $CoreDir).Path
if (-not (Test-Path "$CoreDir/src/server/apps/worldserver/Plugins/coa_plugin_exports.def")) {
    throw "$CoreDir is not a plugin-host core (no coa_plugin_exports.def)."
}
foreach ($tool in 'cl', 'cmake', 'ninja', 'python') {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "$tool is not on PATH (run inside an MSVC developer environment)." }
}

$cmakeArgs = @(
    '-S', $CoreDir, '-B', $BuildDir, '-G', 'Ninja',
    '-DCMAKE_BUILD_TYPE=RelWithDebInfo',
    '-DCOA_PLUGIN_HOST=ON',
    '-DAPPS_BUILD=all', '-DTOOLS_BUILD=none', '-DBUILD_TESTING=OFF',
    '-DSCRIPTS=static', '-DMODULES=static',
    # PCH only speeds the build up; export_sdk.py strips its flags from the SDK.
    '-DUSE_COREPCH=1', '-DUSE_SCRIPTPCH=1',
    '-DWITH_WARNINGS=OFF',
    '-DCMAKE_EXE_LINKER_FLAGS=/FORCE:MULTIPLE',
    "-DBOOST_ROOT=$BoostRoot",
    "-DMYSQL_INCLUDE_DIR=$MysqlRoot/include",
    "-DMYSQL_LIBRARY=$MysqlRoot/lib/mysqlclient.lib"
)
if ($OpensslRoot) { $cmakeArgs += "-DOPENSSL_ROOT_DIR=$OpensslRoot" }

Write-Host '=== configure ==='
Invoke-Checked 'CMake configure' { cmake @cmakeArgs }
Write-Host '=== build worldserver + authserver ==='
Invoke-Checked 'build' { cmake --build $BuildDir --target worldserver authserver -j $Jobs }

$bin = (Get-ChildItem $BuildDir -Recurse -Filter worldserver.exe | Select-Object -First 1).DirectoryName
if (-not $bin) { throw 'worldserver.exe was not produced.' }
Invoke-Checked 'worldserver --version' { & "$bin/worldserver.exe" --version }

$coreOut = Join-Path $OutDir 'core'
$sdkOut = Join-Path $OutDir 'sdk'
New-Item -ItemType Directory -Force -Path $coreOut | Out-Null
Copy-Item "$bin/worldserver.exe", "$bin/authserver.exe" $coreOut
Get-ChildItem $bin -Filter *.dll | Copy-Item -Destination $coreOut
Get-ChildItem $bin -Filter *.pdb | Where-Object { $_.BaseName -in 'worldserver', 'authserver' } | Copy-Item -Destination $coreOut

Write-Host '=== export SDK ==='
Invoke-Checked 'export_sdk.py' { python -I "$CoreDir/tools/plugin-sdk/export_sdk.py" $CoreDir $BuildDir $sdkOut }

Write-Host '=== verify host/SDK pair ==='
$coreSha = (git -C $CoreDir rev-parse HEAD).Trim()
$verify = @("$CoreDir/tools/plugin-sdk/verify_pair.py", "$coreOut/worldserver.exe", $sdkOut, (Join-Path $OutDir 'pair.json'), '--core-sha', $coreSha)
if ($ExpectCl) { $verify += @('--expect-cl', $ExpectCl) }
Invoke-Checked 'verify_pair.py' { python -I @verify }
