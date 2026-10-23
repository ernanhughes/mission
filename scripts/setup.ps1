#requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$SkipFrontendBuild
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host "Mission Control setup" -ForegroundColor Cyan
Write-Host "Repository: $repoRoot"

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    throw "Python 3.12+ is required and 'python' was not found on PATH."
}
$versionText = (& python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
$version = [version]$versionText
if ($version -lt [version]"3.12") {
    throw "Python 3.12+ is required. Found $versionText."
}

$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) {
    throw "Node.js 20+ is required for the frontend."
}
$nodeVersion = (& node --version).Trim()
Write-Host "Python $versionText; Node $nodeVersion"

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        Write-Host "Creating virtual environment with uv..."
        uv venv .venv --python 3.13
    } else {
        Write-Host "Creating virtual environment with venv..."
        python -m venv .venv
    }
}

Write-Host "Installing the backend (editable) and test dependencies..."
if (Get-Command uv -ErrorAction SilentlyContinue) {
    & uv pip install --python .venv\Scripts\python.exe -e ".[dev]"
} else {
    & .venv\Scripts\python.exe -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "Could not upgrade pip." }
    & .venv\Scripts\python.exe -m pip install -e ".[dev]"
}
if ($LASTEXITCODE -ne 0) {
    throw "Backend dependency installation failed."
}

Write-Host "Installing frontend dependencies..."
Push-Location frontend
try {
    npm install
    if ($LASTEXITCODE -ne 0) { throw "npm install failed." }
    if (-not $SkipFrontendBuild) {
        Write-Host "Building the frontend..."
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
    }
} finally {
    Pop-Location
}

New-Item -ItemType Directory -Force -Path "data", "data\logs" | Out-Null
Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Start Mission Control with:  .\scripts\start.ps1"
