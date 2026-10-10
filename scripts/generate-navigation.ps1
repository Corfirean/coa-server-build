param(
    [Parameter(Mandatory)] [string] $Client,
    [Parameter(Mandatory)] [string] $Tools,
    [Parameter(Mandatory)] [string] $Out,
    [Parameter(Mandatory)] [string] $CoreSha,
    [ValidateRange(1, 16)] [int] $Threads = 4
)
$ErrorActionPreference = 'Stop'
$Client = (Resolve-Path -LiteralPath $Client).Path
$Tools = (Resolve-Path -LiteralPath $Tools).Path
$Out = [IO.Path]::GetFullPath($Out)
if (Test-Path -LiteralPath $Out) { throw 'Generation requires a new output directory.' }
if ($CoreSha -notmatch '^[0-9a-f]{40}$') { throw 'An exact core SHA is required.' }
$names = 'map_extractor.exe', 'vmap4_extractor.exe', 'vmap4_assembler.exe', 'mmaps_generator.exe', 'mmaps-config.yaml'
foreach ($name in $names) {
    if (!(Test-Path -LiteralPath (Join-Path $Tools $name))) { throw "Missing tool: $name" }
}
$archives = @(Get-ChildItem -LiteralPath (Join-Path $Client 'Data') -Recurse -File -Filter '*.mpq')
if (!$archives.Count) { throw 'Client MPQ archives were not found.' }
$inputs = @{}
foreach ($file in $archives) { $inputs[$file.FullName] = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
New-Item -ItemType Directory -Path $Out | Out-Null
foreach ($name in $names) { Copy-Item -LiteralPath (Join-Path $Tools $name) -Destination $Out }
Get-ChildItem -LiteralPath $Tools -Filter '*.dll' | Copy-Item -Destination $Out
Push-Location $Out
try {
    & ./map_extractor.exe -i $Client -o $Out -e 1 2>&1 | Tee-Object -FilePath maps.log
    if ($LASTEXITCODE) { throw 'Map extraction failed.' }
    & ./vmap4_extractor.exe -d (Join-Path $Client 'Data') 2>&1 | Tee-Object -FilePath vmap-extraction.log
    if ($LASTEXITCODE) { throw 'VMap extraction failed.' }
    & ./vmap4_assembler.exe Buildings vmaps 2>&1 | Tee-Object -FilePath vmap-assembly.log
    if ($LASTEXITCODE) { throw 'VMap assembly failed.' }
    & ./mmaps_generator.exe --config mmaps-config.yaml --threads $Threads --silent 2>&1 | Tee-Object -FilePath mmaps.log
    if ($LASTEXITCODE) { throw 'MMap generation failed.' }
    $files = @{}
    foreach ($directory in 'maps', 'vmaps', 'mmaps') {
        $entries = @(Get-ChildItem -LiteralPath $directory -Recurse -File)
        if (!$entries.Count) { throw "Empty navigation output: $directory" }
        foreach ($file in $entries) {
            $relative = [IO.Path]::GetRelativePath($Out, $file.FullName).Replace('\', '/')
            $files[$relative] = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
    $current = @(Get-ChildItem -LiteralPath (Join-Path $Client 'Data') -Recurse -File -Filter '*.mpq')
    if ($current.Count -ne $inputs.Count) { throw 'Client archives changed during generation.' }
    foreach ($file in $current) {
        if ($inputs[$file.FullName] -ne (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()) { throw 'Client archives changed during generation.' }
    }
    $toolHashes = @{}
    foreach ($name in $names) { $toolHashes[$name] = (Get-FileHash -LiteralPath $name -Algorithm SHA256).Hash.ToLowerInvariant() }
    @{ schema = 1; core = $CoreSha; inputs = $inputs; tools = $toolHashes; files = $files; generatedUtc = [DateTime]::UtcNow.ToString('o'); status = 'generated-not-gameplay-qualified' } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath navigation-manifest.json -Encoding utf8
} finally { Pop-Location }
