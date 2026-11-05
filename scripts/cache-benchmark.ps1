param([ValidateSet('cold', 'warm')][string] $Mode)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force benchmark | Out-Null
$source = @'
#include <algorithm>
#include <filesystem>
#include <map>
#include <regex>
#include <string>
#include <vector>
std::string calculate(std::vector<std::string> values) {
    std::sort(values.begin(), values.end());
    std::map<std::string, unsigned> counts;
    for (auto const& value : values) {
        auto path = std::filesystem::path(value).lexically_normal().string();
        counts[std::regex_replace(path, std::regex("[0-9]+"), "number")] += UNIT;
    }
    std::string result;
    for (auto const& item : counts) result += item.first + std::to_string(item.second);
    return result;
}
'@
[IO.File]::WriteAllText((Join-Path (Get-Location) 'benchmark/sample.cpp'), $source)
sccache --zero-stats
if ($LASTEXITCODE) { throw 'Cannot reset benchmark statistics.' }
$clock = [Diagnostics.Stopwatch]::StartNew()
foreach ($unit in 1..8) {
    sccache cl.exe /nologo /c /O2 /Z7 /EHsc /std:c++17 "/DUNIT=$unit" benchmark/sample.cpp "/Fobenchmark/unit-$unit.obj"
    if ($LASTEXITCODE) { throw "MSVC compilation failed: unit $unit" }
}
$clock.Stop()
$stats = sccache --show-stats --stats-format json | ConvertFrom-Json
if ($LASTEXITCODE) { throw 'Cannot read benchmark statistics.' }
$hits = ($stats.stats.cache_hits.counts.PSObject.Properties.Value | Measure-Object -Sum).Sum
$misses = ($stats.stats.cache_misses.counts.PSObject.Properties.Value | Measure-Object -Sum).Sum
$compiler = (Get-Item (Get-Command cl.exe).Source).VersionInfo.FileVersion
$result = @{ mode = $Mode; seconds = $clock.Elapsed.TotalSeconds; compiler = $compiler; hits = $hits; misses = $misses; statistics = $stats }
$result | ConvertTo-Json -Depth 30 | Set-Content "benchmark/$Mode.json" -Encoding utf8NoBOM
"$Mode MSVC benchmark: $($clock.Elapsed.TotalSeconds) seconds; hits=$hits, misses=$misses" | Out-File $env:GITHUB_STEP_SUMMARY -Append -Encoding utf8
if ($Mode -eq 'cold' -and ($misses -ne 8 -or $hits -ne 0)) { throw 'Cold measurement did not compile every object.' }
if ($Mode -eq 'warm') {
    $cold = Get-Content benchmark/cold.json -Raw | ConvertFrom-Json
    if ($cold.compiler -ne $compiler) { throw 'Runner compiler versions differ; measurements cannot be compared.' }
    if ($hits -ne 8 -or $misses -ne 0) { throw 'Persisted compiler cache was not fully reused.' }
    $speedup = $cold.seconds / $clock.Elapsed.TotalSeconds
    "Cross-runner cache speedup: $speedup x. This measures the MSVC fixture, not a complete server build." | Out-File $env:GITHUB_STEP_SUMMARY -Append -Encoding utf8
    if ($speedup -lt 2) { throw 'Repeated fixture compilation did not meet the 2x target.' }
}
