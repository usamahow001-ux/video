@echo off
title AI Shorts Generator - Live Online
echo ===================================================
echo   AI Shorts Generator - Running Live
echo ===================================================
echo.

cd /d "%~dp0"

echo [1/2] Checking local app server...
netstat -ano | findstr :8000 >nul
if %errorlevel% neq 0 (
    echo Starting background server...
    powershell -ExecutionPolicy Bypass -File .\start_bg.ps1
    timeout /t 3 >nul
) else (
    echo [OK] Server is already running on port 8000.
)

echo.
echo [2/2] Starting secure live internet tunnel...
echo (You can close your laptop lid - the site stays online!)
echo.

ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -R 80:127.0.0.1:8000 nokey@localhost.run
pause
