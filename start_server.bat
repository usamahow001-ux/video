@echo off
title AI Shorts Generator - Server
echo ============================================
echo      AI Shorts Generator
echo ============================================
echo.

cd /d "%~dp0backend"

echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Force UTF-8 so emoji in hooks/story text don't crash the server (Windows cp1252 default)
set PYTHONIOENCODING=utf-8

echo.
echo Starting server...
echo Open http://localhost:8000 in your browser
echo Press Ctrl+C to stop the server
echo ============================================
echo.

python app.py

echo.
echo Server stopped.
pause
