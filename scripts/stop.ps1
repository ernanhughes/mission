#requires -Version 5.1
[CmdletBinding()]
param(
    [int]$Port = 8790
)

$ErrorActionPreference = "Stop"
$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1
if (-not $listener) {
    Write-Host "No Mission Control listener found on port $Port." -ForegroundColor Yellow
    exit 0
}
$pidValue = $listener.OwningProcess
$process = Get-CimInstance Win32_Process -Filter "ProcessId = $pidValue"
if (-not $process -or $process.CommandLine -notmatch "mission_control") {
    throw "Process $pidValue is listening on $Port but does not look like Mission Control. Refusing to stop it."
}
Write-Host "Stopping Mission Control backend (PID $pidValue)..."
Stop-Process -Id $pidValue
Write-Host "Backend stopped. Mission Control-managed applications are left running and can be reattached." -ForegroundColor Green
