@echo off
setlocal EnableExtensions
rem ============================================================
rem  Mission Control launcher
rem  Run directly or from D:\tools\mc.bat (on PATH).
rem ============================================================

set "ROOT=%~dp0"
set "PORT=8790"
set "REBUILD="
set "NOBROWSER="
set "MODE=start"

:parse
if "%~1"=="" goto dispatch
if /i "%~1"=="-h" goto usage
if /i "%~1"=="--help" goto usage
if /i "%~1"=="/?" goto usage
if /i "%~1"=="-p" goto set_port
if /i "%~1"=="--port" goto set_port
if /i "%~1"=="-r" goto want_rebuild
if /i "%~1"=="--rebuild" goto want_rebuild
if /i "%~1"=="-n" goto want_nobrowser
if /i "%~1"=="--no-browser" goto want_nobrowser
if /i "%~1"=="-d" goto want_dev
if /i "%~1"=="--dev" goto want_dev
if /i "%~1"=="-s" goto want_stop
if /i "%~1"=="--stop" goto want_stop

echo [mission] Unknown option: %~1
echo.
goto usage_error

:set_port
if "%~2"=="" (
    echo [mission] --port requires a value.
    echo.
    goto usage_error
)
set "PORT=%~2"
shift
shift
goto parse

:want_rebuild
set "REBUILD=-Rebuild"
shift
goto parse

:want_nobrowser
set "NOBROWSER=-NoBrowser"
shift
goto parse

:want_dev
set "MODE=dev"
shift
goto parse

:want_stop
set "MODE=stop"
shift
goto parse

:dispatch
set "BADPORT="
for /f "delims=0123456789" %%A in ("%PORT%") do set "BADPORT=1"
if defined BADPORT (
    echo [mission] Invalid port: %PORT%
    exit /b 2
)

if not exist "%ROOT%scripts\start.ps1" (
    echo [mission] Cannot find scripts under "%ROOT%".
    exit /b 1
)

if /i "%MODE%"=="stop" goto run_stop
if /i "%MODE%"=="dev" goto run_dev
goto run_start

:run_stop
pushd "%ROOT%"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\stop.ps1" -Port %PORT%
set "RC=%ERRORLEVEL%"
popd
exit /b %RC%

:run_dev
call :require_venv
if errorlevel 1 exit /b 1
pushd "%ROOT%"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\dev.ps1" -Port %PORT%
set "RC=%ERRORLEVEL%"
popd
exit /b %RC%

:run_start
call :require_venv
if errorlevel 1 exit /b 1
pushd "%ROOT%"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\start.ps1" -Port %PORT% %REBUILD% %NOBROWSER%
set "RC=%ERRORLEVEL%"
popd
exit /b %RC%

:require_venv
if not exist "%ROOT%.venv\Scripts\python.exe" (
    echo [mission] Python environment missing.
    echo [mission] Run "%ROOT%scripts\setup.ps1" first.
    exit /b 1
)
exit /b 0

:usage
echo Usage: mission [options]
echo.
echo   Launch Mission Control at http://127.0.0.1:8790.
echo   The browser opens automatically unless --no-browser is given.
echo.
echo Options:
echo   -p, --port ^<port^>   Port to listen on (default: 8790)
echo   -r, --rebuild       Rebuild the frontend before starting
echo   -n, --no-browser    Do not open a browser window
echo   -d, --dev           Development mode: backend plus Vite on 5173
echo   -s, --stop          Stop the backend listening on the port
echo   -h, --help          Show this help
echo.
echo Examples:
echo   mc
echo   mc --port 8800
echo   mc --rebuild --no-browser
echo   mc --stop
exit /b 0

:usage_error
exit /b 2
