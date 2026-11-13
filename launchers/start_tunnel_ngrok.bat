@echo off
REM ===========================================================================
REM  OMBAR FL-AI Studio  -  ngrok tunnel launcher  (alternative to cloudflared)
REM  -----------------------------------------------------------------------
REM  Requires ngrok installed (https://ngrok.com) and authenticated with
REM  your auth token:  ngrok config add-authtoken YOUR_TOKEN
REM
REM  Exposes http://localhost:8080 as a public HTTPS URL.
REM ===========================================================================

setlocal
title OMBAR - ngrok Tunnel (port 8080)

where ngrok >nul 2>nul
if errorlevel 1 (
  echo   [tunnel] ngrok tidak ditemukan di PATH.
  echo   [tunnel] Install dari https://ngrok.com/download lalu jalankan:
  echo            ngrok config add-authtoken YOUR_AUTH_TOKEN
  echo   [tunnel] Lalu jalankan ulang script ini.
  echo.
  pause
  exit /b 1
)

echo ============================================================
echo   OMBAR FL-AI Studio - ngrok Tunnel
echo ============================================================
echo   Exposing http://localhost:8080 as public HTTPS URL.
echo   Copy the forwarding URL (https://xxxx.ngrok.io) into the
echo   dashboard's Backend URL field.
echo ============================================================
echo.

ngrok http 8080

echo.
echo === ngrok berhenti ===
pause
endlocal
