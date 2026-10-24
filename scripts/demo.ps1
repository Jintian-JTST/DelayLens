# One-command local demo: offline bus 29 snapshot API + Vite UI, browser opens itself.
# Run from anywhere:  .\scripts\demo.cmd        (add -Live to use backend\.env instead of the snapshot)
# Press Ctrl+C in this window to stop both servers. Windows PowerShell 5.1 or PowerShell 7.
param([switch]$Live)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
# Team demo snapshot: Saturday 17:00 -> 16:22 / 92%, 56 trips. Relative paths resolve from the repo root.
$snapshot = 'docs/evidence/bus29-db-final-20261024T202558Z'

function Find-FreePort([int]$start) {
    foreach ($port in $start..($start + 50)) {
        if (-not (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)) { return $port }
    }
    throw "No free port found from $start"
}

function Wait-Url([string]$url, [int]$seconds, $process) {
    foreach ($i in 1..$seconds) {
        if ($process.HasExited) { return $false }
        try { Invoke-WebRequest $url -UseBasicParsing -TimeoutSec 2 | Out-Null; return $true } catch { Start-Sleep 1 }
    }
    return $false
}

foreach ($tool in 'uv', 'node', 'npm') {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "$tool is not installed or not on PATH." }
}

# Ports: take the usual ones if free, otherwise the next free ones; nothing already running is killed.
$apiPort = Find-FreePort 8000
$webPort = Find-FreePort 5173

if (-not (Test-Path (Join-Path $frontend 'node_modules\.bin\vite.cmd'))) {
    Write-Host 'Installing frontend dependencies (first run only)...'
    $modules = Join-Path $frontend 'node_modules'
    if (Test-Path $modules) { Remove-Item -Recurse -Force $modules }
    Push-Location $frontend
    try { npm ci; if ($LASTEXITCODE) { throw 'npm ci failed' } } finally { Pop-Location }
}
Push-Location $backend
try { uv sync --locked; if ($LASTEXITCODE) { throw 'uv sync failed' } } finally { Pop-Location }

if ($Live) { Remove-Item Env:SNAPSHOT_DIR -ErrorAction SilentlyContinue } else { $env:SNAPSHOT_DIR = $snapshot }
$env:API_TARGET = "http://127.0.0.1:$apiPort"   # overrides frontend\.env.local, which may point at another port
$log = Join-Path $env:TEMP 'delaylens-backend.log'

$api = $null
$web = $null
try {
    Write-Host "Starting API on port $apiPort ($(if ($Live) { 'live: backend\.env' } else { 'offline snapshot' }))..."
    $api = Start-Process uv -WorkingDirectory $backend -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $log -RedirectStandardError "$log.err" `
        -ArgumentList 'run', '--locked', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', $apiPort
    if (-not (Wait-Url "http://127.0.0.1:$apiPort/api/health" 90 $api)) {
        Get-Content "$log.err" -Tail 20 -ErrorAction SilentlyContinue
        throw "API did not start. Log: $log.err"
    }

    Write-Host "Starting UI on port $webPort..."
    $web = Start-Process npm.cmd -WorkingDirectory $frontend -NoNewWindow -PassThru `
        -ArgumentList 'run', 'dev', '--', '--port', $webPort
    if (-not (Wait-Url "http://127.0.0.1:$webPort/" 60 $web)) { throw 'UI did not start.' }

    Write-Host "`nDelayLens is running:  http://127.0.0.1:$webPort   (API docs: http://127.0.0.1:$apiPort/docs)"
    Write-Host 'Press Ctrl+C here to stop everything.'
    Start-Process "http://127.0.0.1:$webPort"
    while (-not $web.HasExited) { Start-Sleep 1 }
} finally {
    foreach ($p in $web, $api) { if ($p -and -not $p.HasExited) { & taskkill /T /F /PID $p.Id *> $null } }
}
