@echo off
setlocal

:: Load tunnel.env if present
set "SCRIPT_DIR=%~dp0"
set "ENV_FILE=%SCRIPT_DIR%tunnel.env"
if not exist "%ENV_FILE%" set "ENV_FILE=%SCRIPT_DIR%tunnel.env.example"
if exist "%ENV_FILE%" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
        set "%%A=%%B"
    )
)

:: Allow command-line override: MODE=REVERSE ssh_tunnel.bat
if not "%MODE%"=="" set "MODE=%MODE%"

:: Defaults
if "%MODE%"=="" set "MODE=forward"
if "%TUNNEL_PORT%"=="" set "TUNNEL_PORT=22"
if "%LOCAL_PORT%"=="" set "LOCAL_PORT=18883"
if "%BROKER_HOST%"=="" set "BROKER_HOST=localhost"
if "%BROKER_PORT%"=="" set "BROKER_PORT=8883"
if "%REMOTE_BIND_ADDR%"=="" set "REMOTE_BIND_ADDR=127.0.0.1"
if "%REMOTE_PORT%"=="" set "REMOTE_PORT=18883"
if "%REVERSE_TARGET_HOST%"=="" set "REVERSE_TARGET_HOST=localhost"
if "%REVERSE_TARGET_PORT%"=="" set "REVERSE_TARGET_PORT=%LOCAL_PORT%"

if "%TUNNEL_USER%"=="" (
    echo Missing TUNNEL_USER. Update tunnel.env. 1>&2
    exit /b 1
)
if "%TUNNEL_HOST%"=="" (
    echo Missing TUNNEL_HOST. Update tunnel.env. 1>&2
    exit /b 1
)

set "SSH_BASE=ssh -N -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes -p %TUNNEL_PORT%"

if /i "%MODE%"=="forward" (
    echo Starting forward tunnel: localhost:%LOCAL_PORT% -^> %BROKER_HOST%:%BROKER_PORT% via %TUNNEL_HOST%
    %SSH_BASE% -L %LOCAL_PORT%:%BROKER_HOST%:%BROKER_PORT% %TUNNEL_USER%@%TUNNEL_HOST%
) else if /i "%MODE%"=="reverse" (
    echo Starting reverse tunnel: %TUNNEL_HOST%:%REMOTE_PORT% -^> %REVERSE_TARGET_HOST%:%REVERSE_TARGET_PORT%
    %SSH_BASE% -R %REMOTE_BIND_ADDR%:%REMOTE_PORT%:%REVERSE_TARGET_HOST%:%REVERSE_TARGET_PORT% %TUNNEL_USER%@%TUNNEL_HOST%
) else (
    echo Unknown MODE=%MODE%. Use 'forward' or 'reverse'. 1>&2
    exit /b 1
)

endlocal
