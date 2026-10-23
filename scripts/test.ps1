#requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (-not $FrontendOnly) {
    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        throw "Python environment missing. Run .\scripts\setup.ps1 first."
    }
    Write-Host "Backend lint and tests" -ForegroundColor Cyan
    if (Test-Path ".venv\Scripts\ruff.exe") {
        & .venv\Scripts\ruff.exe check backend scripts
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    & .venv\Scripts\python.exe -m pytest -q
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if (-not $BackendOnly) {
    Write-Host "Frontend tests and build" -ForegroundColor Cyan
    Push-Location frontend
    try {
        npm test
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        npm run build
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    } finally {
        Pop-Location
    }
}

Write-Host "All requested checks passed." -ForegroundColor Green
