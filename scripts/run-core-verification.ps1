param(
    [string]$CoreRoot = '_core',
    [ValidateRange(1,64)][int]$Jobs = 4,
    [ValidatePattern('^[A-Za-z0-9_./-]+$')][string]$BaseRef = 'origin/coa-bots'
)
$ErrorActionPreference = 'Stop'
$core = (Resolve-Path -LiteralPath $CoreRoot).Path
$cache = Join-Path $core '.cache'
New-Item -ItemType Directory -Force -Path $cache | Out-Null
$token = [guid]::NewGuid().ToString('N')
$stdout = Join-Path $cache "verification-$token.out.log"
$stderr = Join-Path $cache "verification-$token.err.log"
$positions = @{}
function Write-ProgressFile([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return }
    $file = [System.IO.FileStream]::new($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
    try {
        $position = if ($positions.ContainsKey($Path)) { $positions[$Path] } else { 0L }
        if ($position -gt $file.Length) { $position = 0L }
        $null = $file.Seek($position, [System.IO.SeekOrigin]::Begin)
        $reader = [System.IO.StreamReader]::new($file, [System.Text.Encoding]::UTF8, $true, 4096, $true)
        try {
            $text = $reader.ReadToEnd()
            $positions[$Path] = $file.Position
            if ($text.Length) { Write-Host -NoNewline $text }
        } finally { $reader.Dispose() }
    } finally { $file.Dispose() }
}
function Write-VerificationProgress {
    Write-ProgressFile $stdout
    Write-ProgressFile $stderr
    $logs = Join-Path $core '.cache/verify-all'
    if (Test-Path -LiteralPath $logs) {
        Get-ChildItem -LiteralPath $logs -Recurse -File -Filter build.log |
            Where-Object { $_.LastWriteTime -ge $started } |
            ForEach-Object { Write-ProgressFile $_.FullName }
    }
}
$started = Get-Date
$python = (Get-Command python -ErrorAction Stop).Source
$process = Start-Process -FilePath $python -WorkingDirectory $core -WindowStyle Hidden -PassThru `
    -ArgumentList @('-B', 'tools/verify_all.py', '--stages', 'source,build,unit', '--base', $BaseRef, '--jobs', "$Jobs") `
    -RedirectStandardOutput $stdout -RedirectStandardError $stderr
try {
    do {
        Write-VerificationProgress
        if (-not $process.HasExited) { Start-Sleep -Seconds 10 }
        $process.Refresh()
    } while (-not $process.HasExited)
    $process.WaitForExit()
    Write-VerificationProgress
    exit $process.ExitCode
} finally {
    if (-not $process.HasExited) { & taskkill.exe /PID $process.Id /T /F | Out-Null }
}
