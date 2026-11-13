@echo off
REM ===========================================================================
REM  OMBAR FL-AI Studio  -  Cloudflare Tunnel launcher  (FREE, no signup)
REM  -----------------------------------------------------------------------
REM  Exposes the local FastAPI backend (port 8080) as a PUBLIC HTTPS URL so
REM  a Vercel-hosted frontend can call it WITHOUT mixed-content blocks.
REM
REM  After starting, copy the URL that looks like:
REM     https://random-words-1234.trycloudflare.com
REM  and paste it into the dashboard's "Backend URL" field.
REM ===========================================================================

setlocal EnableDelayedExpansion
title OMBAR - Cloudflare Tunnel (port 8080)

set "TUNNEL_PORT=8080"
set "CF_DIR=%USERPROFILE%\ombar-tools"
set "CF_EXE=%CF_DIR%\cloudflared.exe"

echo ============================================================
echo   OMBAR FL-AI Studio - Cloudflare Tunnel
echo ============================================================
echo   Exposing  http://localhost:%TUNNEL_PORT%  as a public HTTPS URL
echo   so the Vercel dashboard can reach your local backend.
echo ============================================================
echo.

REM ---- 1) Locate or download cloudflared ---------------------------------
where cloudflared >nul 2>nul
if not errorlevel 1 (
  set "CF_CMD=cloudflared"
  echo   [tunnel] Found cloudflared in PATH.
  goto :run
)

if exist "%CF_EXE%" (
  set "CF_CMD=%CF_EXE%"
  echo   [tunnel] Found cloudflared at %CF_EXE%.
  goto :run
)

echo   [tunnel] cloudflared not found - downloading...
if not exist "%CF_DIR%" mkdir "%CF_DIR%"

REM Download the official Cloudflare tunnel binary (Windows 64-bit)
set "CF_URL=https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
echo   [tunnel] URL: %CF_URL%
powershell -NoProfile -Command ^
  "try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; ^
   Invoke-WebRequest -Uri '%CF_URL%' -OutFile '%CF_EXE%' -UseBasicParsing; ^
   Write-Host '   [tunnel] Download complete.' } ^
   catch { Write-Host '   [tunnel] Download FAILED: ' $_.Exception.Message; exit 1 }"

if not exist "%CF_EXE%" (
  echo.
  echo   [tunnel] ERROR: Download gagal.
  echo   [tunnel] Download manual dari: https://github.com/cloudflare/cloudflared/releases/latest
  echo   [tunnel] Letakkan cloudflared.exe di %CF_DIR% lalu jalankan ulang.
  echo.
  pause
  exit /b 1
)
set "CF_CMD=%CF_EXE%"

:run
echo.
echo   [tunnel] Starting tunnel... tunggu URL HTTPS muncul di bawah:
echo   [tunnel] (copy URL tsb ke kolom Backend URL di dashboard Vercel)
echo.

REM `cmd /k` keeps the window open so the URL stays visible.
"%CF_CMD%" tunnel --url http://localhost:%TUNNEL_PORT%

REM If cloudflared exits, keep the window open so errors are readable
echo.
echo === Tunnel berhenti ===
echo   URL yang sudah dipakai di dashboard kini tidak valid.
echo   Jalankan ulang script ini untuk dapat URL baru.
pause
endlocal
