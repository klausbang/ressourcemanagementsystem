@echo off
setlocal EnableDelayedExpansion
rem tunnel.bat - manage the Cloudflare quick tunnel + local app for SimpleVisualPlanner.
rem Run "tunnel.bat help" for usage.

set "APP_DIR=%~dp0"
rem A quoted Windows argument ending in "...\" is misparsed (trailing backslash escapes
rem the closing quote) - keep a slash-free copy for anywhere APP_DIR is passed quoted
rem on its own, e.g. -WorkingDirectory "%APP_DIR_NOSLASH%".
set "APP_DIR_NOSLASH=%APP_DIR:~0,-1%"
set "SCRIPTS_DIR=%APP_DIR%scripts\"
set "RUN_DIR=%APP_DIR%.run"
set "APP_PID_FILE=%RUN_DIR%\app.pid"
set "TUNNEL_PID_FILE=%RUN_DIR%\cloudflared.pid"
set "APP_LOG=%RUN_DIR%\app.out.log"
set "APP_ERR_LOG=%RUN_DIR%\app.err.log"
set "TUNNEL_LOG=%RUN_DIR%\cloudflared.out.log"
set "TUNNEL_ERR_LOG=%RUN_DIR%\cloudflared.err.log"
set "APP_URL=http://127.0.0.1:5000"

if not exist "%RUN_DIR%" mkdir "%RUN_DIR%" >nul 2>&1

set "CMD=%~1"
if "%CMD%"=="" set "CMD=help"

if /i "%CMD%"=="help"    goto :help
if /i "%CMD%"=="/?"      goto :help
if /i "%CMD%"=="-h"      goto :help
if /i "%CMD%"=="--help"  goto :help
if /i "%CMD%"=="restart" goto :restart
if /i "%CMD%"=="start"   goto :restart
if /i "%CMD%"=="stop"    goto :stop
if /i "%CMD%"=="status"  goto :status

echo Unknown command: %CMD%
echo.
goto :help

:help
echo.
echo tunnel.bat - manage the SimpleVisualPlanner Cloudflare quick tunnel
echo.
echo Usage:
echo   tunnel.bat restart   Start the local app if it isn't running, then (re)start the
echo                        Cloudflare tunnel and print the new public address.
echo   tunnel.bat start     Same as restart - safe to run whether anything is up yet or not.
echo   tunnel.bat status    Show whether the app and the tunnel are running, and the
echo                        tunnel's current public address.
echo   tunnel.bat stop      Stop the Cloudflare tunnel only. The local app keeps running,
echo                        so restarting the tunnel afterward doesn't restart the app.
echo   tunnel.bat help      Show this help (also: /? -h --help, or no argument at all).
echo.
echo Notes:
echo   - Cloudflare issues a brand new random *.trycloudflare.com address every time the
echo     tunnel (re)starts - always re-read it with "status" or after "restart" rather
echo     than reusing an old one.
echo   - This app's login has no password - anyone with the printed address can sign in
echo     as any demo user. Only share the address with who you intend to review it with,
echo     and run "tunnel.bat stop" when you're done.
echo   - Logs live in: %RUN_DIR%
echo.
exit /b 0

rem ---------------------------------------------------------------------------
rem Sets IS_APP_RUNNING / IS_TUNNEL_RUNNING to 1 or 0 by checking the PID files
rem against the live process list, not just whether the file exists.
rem ---------------------------------------------------------------------------
:check_running
set "IS_APP_RUNNING=0"
set "IS_TUNNEL_RUNNING=0"
if exist "%APP_PID_FILE%" (
    set /p _APP_PID=<"%APP_PID_FILE%"
    tasklist /fi "PID eq !_APP_PID!" 2>nul | find "!_APP_PID!" >nul
    if not errorlevel 1 set "IS_APP_RUNNING=1"
)
if exist "%TUNNEL_PID_FILE%" (
    set /p _TUNNEL_PID=<"%TUNNEL_PID_FILE%"
    tasklist /fi "PID eq !_TUNNEL_PID!" 2>nul | find "!_TUNNEL_PID!" >nul
    if not errorlevel 1 set "IS_TUNNEL_RUNNING=1"
)
goto :eof

rem ---------------------------------------------------------------------------
:find_cloudflared
set "CLOUDFLARED_EXE="
where cloudflared.exe >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%I in ('where cloudflared.exe') do (
        if not defined CLOUDFLARED_EXE set "CLOUDFLARED_EXE=%%I"
    )
)
if not defined CLOUDFLARED_EXE if exist "C:\Program Files (x86)\cloudflared\cloudflared.exe" set "CLOUDFLARED_EXE=C:\Program Files (x86)\cloudflared\cloudflared.exe"
if not defined CLOUDFLARED_EXE if exist "C:\Program Files\cloudflared\cloudflared.exe" set "CLOUDFLARED_EXE=C:\Program Files\cloudflared\cloudflared.exe"
goto :eof

rem ---------------------------------------------------------------------------
rem Pulls the first https://...trycloudflare.com URL out of %TUNNEL_LOG%/%TUNNEL_ERR_LOG%
rem into TUNNEL_URL (empty if not found yet). Done via PowerShell's regex, which can
rem return just the matched substring - cloudflared's log line wraps the URL in a
rem decorative box-drawing "|  ...  |" banner, and a plain-batch approach that captures
rem the whole line and re-parses it hits that literal "|" as a pipe operator.
rem ---------------------------------------------------------------------------
:find_tunnel_url
set "TUNNEL_URL="
for /f "usebackq delims=" %%U in (`powershell -NoProfile -Command "$m = Select-String -Path '%TUNNEL_LOG%','%TUNNEL_ERR_LOG%' -Pattern 'https://[a-zA-Z0-9.-]*trycloudflare\.com' -ErrorAction SilentlyContinue | Select-Object -First 1; if ($m) { $m.Matches[0].Value }"`) do set "TUNNEL_URL=%%U"
goto :eof

rem ===========================================================================
:status
call :check_running
echo.
if "%IS_APP_RUNNING%"=="1" (
    echo App:    RUNNING  ^(PID !_APP_PID!, %APP_URL%^)
) else (
    echo App:    NOT RUNNING
)
if "%IS_TUNNEL_RUNNING%"=="1" (
    echo Tunnel: RUNNING  ^(PID !_TUNNEL_PID!^)
    call :find_tunnel_url
    if defined TUNNEL_URL (
        echo         !TUNNEL_URL!
    ) else (
        echo         ^(address not in the log yet - it may still be starting; try "status" again shortly^)
    )
) else (
    echo Tunnel: NOT RUNNING
)
echo.
exit /b 0

rem ===========================================================================
:stop
call :check_running
if "%IS_TUNNEL_RUNNING%"=="1" (
    echo Stopping tunnel ^(PID !_TUNNEL_PID!^)...
    taskkill /PID !_TUNNEL_PID! /T /F >nul 2>&1
    del "%TUNNEL_PID_FILE%" >nul 2>&1
    echo Tunnel stopped. The local app is still running - use "tunnel.bat status" to check.
) else (
    echo Tunnel is not running.
)
exit /b 0

rem ===========================================================================
:restart
call :check_running

if "%IS_APP_RUNNING%"=="1" (
    echo App is already running ^(PID !_APP_PID!^) - leaving it as-is.
) else (
    echo Starting local app...
    del "%APP_PID_FILE%" >nul 2>&1
    rem This app is about to be reachable from the whole internet via the tunnel, so
    rem force debug/reloader off regardless of HOST (see run.py's DEBUG override - a
    rem 127.0.0.1-bound instance being tunneled is exactly the case its own HOST-based
    rem default can't see coming), and use a fresh random session secret rather than
    rem the checked-in dev default - see README.md "Sharing this app during development".
    set "DEBUG=false"
    for /f "usebackq delims=" %%S in (`powershell -NoProfile -Command "[guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')"`) do set "SECRET_KEY=%%S"
    powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPTS_DIR%start-hidden.ps1" -FilePath "python" -ArgumentList "run.py" -WorkingDirectory "%APP_DIR_NOSLASH%" -StdOut "%APP_LOG%" -StdErr "%APP_ERR_LOG%" -PidFile "%APP_PID_FILE%"
    if not exist "%APP_PID_FILE%" (
        echo ERROR: could not start the app - see %APP_ERR_LOG%
        exit /b 1
    )
    set /p _APP_PID=<"%APP_PID_FILE%"
    ping -n 3 127.0.0.1 >nul
    echo App started ^(PID !_APP_PID!^).
)

if "%IS_TUNNEL_RUNNING%"=="1" (
    echo Stopping existing tunnel ^(PID !_TUNNEL_PID!^)...
    taskkill /PID !_TUNNEL_PID! /T /F >nul 2>&1
    del "%TUNNEL_PID_FILE%" >nul 2>&1
)

call :find_cloudflared
if not defined CLOUDFLARED_EXE (
    echo ERROR: cloudflared.exe not found on PATH or in the usual install locations.
    echo Install it first, e.g.: winget install --id Cloudflare.cloudflared -e
    exit /b 1
)

del "%TUNNEL_LOG%" >nul 2>&1
del "%TUNNEL_ERR_LOG%" >nul 2>&1
del "%TUNNEL_PID_FILE%" >nul 2>&1
echo Starting tunnel...
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPTS_DIR%start-hidden.ps1" -FilePath "%CLOUDFLARED_EXE%" -ArgumentList "tunnel --url %APP_URL%" -WorkingDirectory "%APP_DIR_NOSLASH%" -StdOut "%TUNNEL_LOG%" -StdErr "%TUNNEL_ERR_LOG%" -PidFile "%TUNNEL_PID_FILE%"
if not exist "%TUNNEL_PID_FILE%" (
    echo ERROR: could not start cloudflared - see %TUNNEL_ERR_LOG%
    exit /b 1
)
set /p _TUNNEL_PID=<"%TUNNEL_PID_FILE%"

echo Waiting for the tunnel address...
set /a _TRIES=0
:wait_loop
call :find_tunnel_url
if defined TUNNEL_URL goto :got_url
set /a _TRIES+=1
if !_TRIES! gtr 30 goto :timeout
ping -n 2 127.0.0.1 >nul
goto :wait_loop

:timeout
echo Tunnel process is running ^(PID !_TUNNEL_PID!^) but no address showed up after ~60s.
echo Check %TUNNEL_ERR_LOG% or run "tunnel.bat status" again shortly.
exit /b 1

:got_url
echo.
echo Tunnel ready:
echo   !TUNNEL_URL!
echo.
echo ^(No password on this app - only share this with who you intend to review with.
echo  Run "tunnel.bat stop" when you're done.^)
exit /b 0
