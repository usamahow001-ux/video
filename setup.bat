@echo off
title AI Shorts Generator - Setup
echo ============================================
echo    🎬 AI Shorts Generator - Setup
echo ============================================
echo.

REM Check Python
echo [1/6] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python not found! Please install Python 3.10+ from https://www.python.org/downloads/
    echo    Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)
echo ✅ Python found

REM Check FFmpeg
echo [2/6] Checking FFmpeg...
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠️ FFmpeg not found!
    echo.
    echo    Download FFmpeg from: https://ffmpeg.org/download.html
    echo    Or install via winget: winget install ffmpeg
    echo.
    echo    For manual install:
    echo    1. Download from https://www.gyan.dev/ffmpeg/builds/ (Windows builds)
    echo    2. Extract to C:\ffmpeg
    echo    3. Add C:\ffmpeg\bin to your PATH
    echo.
    echo Continuing anyway... Install FFmpeg before running the generator.
) else (
    echo ✅ FFmpeg found
)

REM Create virtual environment
echo [3/6] Creating virtual environment...
cd backend
if not exist venv (
    python -m venv venv
    if %errorlevel% neq 0 (
        echo ❌ Failed to create virtual environment
        pause
        exit /b 1
    )
    echo ✅ Virtual environment created
) else (
    echo ✅ Virtual environment already exists
)

REM Activate and install dependencies
echo [4/6] Installing Python dependencies...
call venv\Scripts\activate.bat
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ⚠️ Some packages failed to install. Trying individually...
    pip install fastapi uvicorn python-multipart moviepy requests Pillow
)
echo ✅ Dependencies installed

REM Create assets
echo [5/6] Creating assets...
if not exist assets (
    mkdir assets
)

REM Create a simple background image using Python
python -c "
from PIL import Image
# Create background image (1080x1920 gradient)
img = Image.new('RGB', (1080, 1920), (10, 10, 20))
img.save('assets/background.png')
print('✅ Background image created')
" 2>nul

REM Create uploads and output directories
if not exist uploads mkdir uploads
if not exist output mkdir output
echo ✅ Directories created

REM Check Ollama (optional)
echo [6/6] Checking Ollama (optional)...
curl -s http://localhost:11434/api/tags >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Ollama is running
) else (
    echo.
    echo ⚠️ Ollama not detected. For AI-powered rewrite features:
    echo   1. Download Ollama from: https://ollama.com/
    echo   2. Install and run: ollama pull llama3
    echo   3. Restart this setup
    echo.
    echo   Without Ollama, the generator will use template-based hooks (still works!)
)

cd ..
echo.
echo ============================================
echo    ✅ Setup Complete!
echo ============================================
echo.
echo To start the generator:
echo   1. cd backend
echo   2. venv\Scripts\activate
echo   3. python app.py
echo.
echo Then open http://localhost:8000 in your browser
echo.
pause
