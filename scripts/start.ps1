#requires -Version 5.1
[CmdletBinding()]
param(
    [int]$Port = 8790,
    [switch]$Rebuild
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "Python environment missing. Run .\scripts\setup.ps1 first."
}
if (-not (Test-Path "frontend\node_modules")) {
    throw "Frontend dependencies missing. Run .\scripts\setup.ps1 first."
}
if ($Rebuild -or -not (Test-Path "frontend\dist\index.html")) {
    Write-Host "Building frontend..." -ForegroundColor Cyan
    Push-Location frontend
    try {
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
    } finally {
        Pop-Location
    }
}

New-Item -ItemType Directory -Force -Path "data", "data\logs" | Out-Null
$env:MISSION_CONTROL_HOST = "127.0.0.1"
$env:MISSION_CONTROL_PORT = "$Port"

$url = "http://127.0.0.1:$Port"
Write-Host ""
Write-Host "MISSION CONTROL" -ForegroundColor Yellow
Write-Host "Local URL: $url" -ForegroundColor Green
Write-Host "Data:      $repoRoot\data"
Write-Host "Stop:      Ctrl+C (managed application processes remain and reattach on restart)"
Write-Host ""

# Open the browser shortly after startup without blocking the server.
$browserJob = Start-Job -ScriptBlock {
    param($target)
    Start-Sleep -Seconds 2
    Start-Process $target
} -ArgumentList $url

try {
    & .venv\Scripts\python.exe -m mission_control --host 127.0.0.1 --port $Port
} finally {
    if ($browserJob) {
        Stop-Job $browserJob -ErrorAction SilentlyContinue
        Remove-Job $browserJob -Force -ErrorAction SilentlyContinue
    }
}
