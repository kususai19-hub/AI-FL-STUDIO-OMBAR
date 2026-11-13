@echo off
REM ===========================================================================
REM  OMBAR FL-AI Studio  -  MASTER LAUNCHER
REM  -----------------------------------------------------------------------
REM  Starts BOTH the MCP daemon (TCP 9787) and the FastAPI backend (8080)
REM  in separate, PERSISTENT console windows that never auto-close.
REM
REM  Double-click this file to boot the whole stack.
REM  Each child window stays open even if a command fails, so you can read
REM  the traceback.
REM ===========================================================================

setlocal EnableDelayedExpansion
title OMBAR FL-AI Studio - Master Launcher

REM ---- Resolve project root (the folder that contains this .bat) ----------
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"

echo.
echo ============================================================
echo   OMBAR FL-AI Studio  -  Master Launcher
echo ============================================================
echo   Project root : %ROOT%
echo   Backend      : %ROOT%\backend\server.py   (port 8080)
echo   MCP daemon   : FL Studio MCP server        (port 9787)
echo ============================================================
echo.

REM ---- 1) Start the MCP daemon --------------------------------------------
REM  We look for the flstudio-mcp entry point in a few common locations.
call "%ROOT%\launchers\start_mcp_daemon.bat"

echo.
echo   [master] waiting 2 seconds before starting backend...
timeout /t 2 /nobreak >nul

REM ---- 2) Start the FastAPI backend ---------------------------------------
call "%ROOT%\launchers\start_server.bat"

echo.
echo ============================================================
echo   Both services launched in their own windows.
echo   - Keep this window open while you work.
echo   - Open the dashboard at:  http://localhost:8080
echo   - Or open frontend\index.html directly in a browser.
echo.
echo   [Vercel users] Frontend Anda di Vercel (HTTPS) tidak bisa
echo   langsung memanggil http://localhost:8080 (mixed content block).
echo   Jalankan juga:  launchers\start_tunnel.bat
echo   untuk dapat URL HTTPS publik, lalu paste ke kolom Backend URL
echo   di dashboard Vercel.
echo ============================================================
echo.
echo   Press any key to close THIS launcher window
echo   (the two service windows will keep running).
pause >nul
endlocal
exit /b 0
