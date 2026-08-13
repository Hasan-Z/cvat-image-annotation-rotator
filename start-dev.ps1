param(
    [string]$BackendPort = "8000",
    [string]$FrontendPort = "5173"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPath = Join-Path $repoRoot ".venv"
$venvActivate = Join-Path $venvPath "Scripts\Activate.ps1"
$backendBootstrapMarker = Join-Path $venvPath ".codex-backend-ready"
$frontendNodeModules = Join-Path $repoRoot "frontend\node_modules"

$backendScript = @"
Set-Location '$repoRoot'
if (-not (Test-Path '$venvActivate')) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        py -3.11 -m venv .venv
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        python -m venv .venv
    } else {
        throw 'Python is not installed or not on PATH.'
    }
}
. '$venvActivate'
if (-not (Test-Path '$backendBootstrapMarker')) {
    python -m pip install --upgrade pip
    python -m pip install -e .[dev]
    New-Item -ItemType File -Path '$backendBootstrapMarker' -Force | Out-Null
}
uvicorn backend.app.main:app --reload --port $BackendPort
"@

$frontendScript = @"
Set-Location '$repoRoot\frontend'
if (-not (Test-Path '$frontendNodeModules')) {
    npm install
}
npm run dev -- --port $FrontendPort
"@

Start-Process powershell.exe -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-Command", $backendScript
)

Start-Process powershell.exe -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-Command", $frontendScript
)

$backendReady = $false
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    try {
        Invoke-WebRequest -Uri "http://127.0.0.1:$BackendPort/health" -UseBasicParsing -TimeoutSec 2 | Out-Null
        $backendReady = $true
        break
    } catch {
        Start-Sleep -Seconds 1
    }
}

if (-not $backendReady) {
    Write-Warning "Backend did not become ready on http://127.0.0.1:$BackendPort/health"
    Write-Warning "Open the backend terminal window to see the startup error."
}

$chromeCandidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "$env:ProgramFiles(x86)\Google\Chrome\Application\chrome.exe",
    "chrome.exe"
)

foreach ($candidate in $chromeCandidates) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) {
        Start-Process $candidate -ArgumentList "http://localhost:$FrontendPort"
        exit 0
    }
    if (Test-Path $candidate) {
        Start-Process $candidate -ArgumentList "http://localhost:$FrontendPort"
        exit 0
    }
}

Start-Process "http://localhost:$FrontendPort"
