param([string] $Ref = 'latest-release')
$ErrorActionPreference = 'Stop'
if ($Ref -eq 'latest-release') {
    $pages = gh api repos/Zyth45/mod-playerbots/tags --paginate --slurp | ConvertFrom-Json
    if ($LASTEXITCODE) { throw 'Cannot read SQUID release tags.' }
    $tags = @($pages | ForEach-Object { $_ } | Where-Object { $_.name -match '^v\d+\.\d+(?:\.\d+)?$' })
    $selected = $tags | Sort-Object { [version]($_.name.Substring(1)) } -Descending | Select-Object -First 1
    if (-not $selected) { throw 'No stable SQUID v* release tag was found.' }
    $tag = $selected.name
    $sha = $selected.commit.sha
} else {
    $encoded = [uri]::EscapeDataString($Ref)
    $commit = gh api "repos/Zyth45/mod-playerbots/commits/$encoded" | ConvertFrom-Json
    if ($LASTEXITCODE) { throw 'Cannot resolve the requested SQUID source.' }
    $sha = $commit.sha
    $tag = if ($Ref -match '^v\d+\.\d+(?:\.\d+)?$') { $Ref } else { '' }
}
if ($sha -notmatch '^[a-f0-9]{40}$') { throw 'Invalid resolved SQUID commit.' }
"squid_sha=$sha"
"squid_tag=$tag"
if ($env:GITHUB_OUTPUT) {
    "squid_sha=$sha", "squid_tag=$tag" | Out-File $env:GITHUB_OUTPUT -Append -Encoding utf8
}
