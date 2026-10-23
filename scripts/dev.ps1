#requires -Version 5.1
[CmdletBinding()]
param(
    [int]$Port = 8790
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

$env:MISSION_CONTROL_HOST = "127.0.0.1"
$env:MISSION_CONTROL_PORT = "$Port"

Write-Host "Starting backend on http://127.0.0.1:$Port and Vite on http://127.0.0.1:5173" -ForegroundColor Cyan
$backend = Start-Process -FilePath ".venv\Scripts\python.exe" `
    -ArgumentList @("-m", "mission_control", "--host", "127.0.0.1", "--port", "$Port", "--reload") `
    -PassThru -WindowStyle Hidden
$frontend = Start-Process -FilePath "npm.cmd" `
    -ArgumentList @("run", "dev") `
    -WorkingDirectory (Join-Path $repoRoot "frontend") `
    -PassThru -WindowStyle Hidden

Write-Host "Backend PID $($backend.Id); Vite PID $($frontend.Id)."
Write-Host "Open http://127.0.0.1:5173"
Write-Host "Stop with: Stop-Process -Id $($backend.Id),$($frontend.Id)"
