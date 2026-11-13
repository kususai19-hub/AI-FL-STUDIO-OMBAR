@echo off
REM ===========================================================================
REM  OMBAR FL-AI Studio  -  FastAPI backend launcher  (port 8080)
REM  -----------------------------------------------------------------------
REM  Starts the uvicorn server in a NEW, PERSISTENT window using `cmd /k`
REM  so the window never auto-closes (you can always read tracebacks).
REM ===========================================================================

setlocal EnableDelayedExpansion

set "ROOT=%~dp0..\"
set "BACKEND=%ROOT%backend"

REM Detect Python command
set "PYCMD=python"
where python >nul 2>nul
if errorlevel 1 set "PYCMD=py"

REM Ensure dependencies are present (best-effort, non-fatal)
echo   [server] Ensuring dependencies...
%PYCMD% -m pip install -q -r "%BACKEND%\requirements.txt" 2>nul

echo   [server] Backend dir : %BACKEND%
echo   [server] Launching uvicorn on 0.0.0.0:8080 ...

REM `cmd /k` keeps the window open even if uvicorn crashes.
start "OMBAR - FastAPI Backend :8080" cmd /k ^
  "cd /d "%BACKEND%" & %PYCMD% server.py & echo. & echo === Backend exited === & echo The window stays open so you can read any errors above. & cmd /k"

endlocal
exit /b 0
