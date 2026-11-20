@echo off
title TalkType - Voice Typing
cd /d "%~dp0"

echo ======================================================
echo            TalkType - Local Voice Typing
echo ======================================================
echo.

:: Ensure HF endpoint mirror is configured for reliable model downloads
set "HF_ENDPOINT=https://hf-mirror.com"
set "HF_HUB_DISABLE_SYMLINKS_WARNING=1"

:: Check if venv exists
if not exist "venv\Scripts\python.exe" (
    echo [1/3] Creating Python virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtualenv.
        echo Please ensure Python is installed and added to PATH.
        pause
        exit /b 1
    )
    echo [2/3] Installing dependencies...
    venv\Scripts\pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
)

echo [3/3] Starting TalkType...
echo.
echo Control:
echo   - Hold RIGHT CTRL for ~1.0 second to START recording.
echo   - Release and speak freely into your microphone.
echo   - Tap or hold RIGHT CTRL to STOP, transcribe, and paste formatted text.
echo Languages: English, Bengali (বাংলা), Hindi (हिन्दी) + 95 languages.
echo Tray icon active in your Windows notification area.
echo.

venv\Scripts\python.exe main.py

if errorlevel 1 (
    echo.
    echo [TalkType exited with an error]
    pause
)
