@echo off
REM ===========================================================================
REM  OMBAR FL-AI Studio  -  STOP everything
REM  -----------------------------------------------------------------------
REM  Kills any python process holding ports 8080 (FastAPI) and 9787 (MCP).
REM  Safe to run any time.
REM ===========================================================================
title OMBAR FL-AI Studio - Stop

echo   [stop] Killing listeners on 8080 and 9787 ...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8080" ^| findstr "LISTENING"') do (
  taskkill /F /PID %%a 2>nul
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":9787" ^| findstr "LISTENING"') do (
  taskkill /F /PID %%a 2>nul
)
echo   [stop] Done.
timeout /t 2 /nobreak >nul
exit /b 0
