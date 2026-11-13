@echo off
REM ===========================================================================
REM  OMBAR FL-AI Studio  -  MCP Daemon launcher  (TCP 127.0.0.1:9787)
REM  -----------------------------------------------------------------------
REM  Starts the FL Studio MCP server in a NEW, PERSISTENT window.
REM  The window uses `cmd /k` so it NEVER auto-closes, even on error.
REM
REM  This script auto-detects the flstudio-mcp entry point:
REM    1. Looks for an env var  FLSTUDIO_MCP_DIR
REM    2. Looks for a sibling folder ..\flstudio-mcp-main
REM    3. Lets you edit MCP_ENTRY below to point at the exact .py file.
REM ===========================================================================

setlocal EnableDelayedExpansion

set "ROOT=%~dp0..\"
set "MCP_DIR=%FLSTUDIO_MCP_DIR%"

REM If env not set, try the default sibling location
if not defined MCP_DIR (
  if exist "%ROOT%..\flstudio-mcp-main\flstudio-mcp-main" (
    set "MCP_DIR=%ROOT%..\flstudio-mcp-main\flstudio-mcp-main"
  ) else if exist "%ROOT%..\flstudio-mcp-main" (
    set "MCP_DIR=%ROOT%..\flstudio-mcp-main"
  ) else if exist "F:\BERTY\Projeck klaud FL\flstudio-mcp-main\flstudio-mcp-main" (
    set "MCP_DIR=F:\BERTY\Projeck klaud FL\flstudio-mcp-main\flstudio-mcp-main"
  )
)

REM Detect Python command
set "PYCMD=python"
where python >nul 2>nul
if errorlevel 1 (
  set "PYCMD=py"
)

echo   [mcp] MCP_DIR = %MCP_DIR%
echo   [mcp] Python  = %PYCMD%

REM Pick the entry point .py inside MCP_DIR
set "MCP_ENTRY="
if defined MCP_DIR (
  for %%F in (mcp_server.py server.py main.py run.py __main__.py) do (
    if exist "%MCP_DIR%\%%F" (
      if not defined MCP_ENTRY set "MCP_ENTRY=%MCP_DIR%\%%F"
    )
  )
)

if not defined MCP_ENTRY (
  echo.
  echo   [mcp] WARNING: flstudio-mcp entry point not found automatically.
  echo   [mcp] Set FLSTUDIO_MCP_DIR or edit this script's MCP_ENTRY path.
  echo   [mcp] Opening a window anyway so you can start it manually.
  start "OMBAR - MCP Daemon :9787" cmd /k ^
    "echo OMBAR FL-AI Studio - MCP Daemon & echo. & echo Edit launchers\start_mcp_daemon.bat & echo and set MCP_ENTRY to your flstudio-mcp script. & echo. & cd /d "%MCP_DIR%" & echo Ready. & cmd /k"
  exit /b 0
)

echo   [mcp] Entry point: %MCP_ENTRY%
echo   [mcp] Launching persistent window...

REM `cmd /k` keeps the window open no matter what happens.
start "OMBAR - MCP Daemon :9787" cmd /k ^
  "cd /d "%MCP_DIR%" & %PYCMD% "%MCP_ENTRY%" & echo. & echo === MCP daemon exited === & echo Press Ctrl+C or close this window to stop. & cmd /k"

endlocal
exit /b 0
