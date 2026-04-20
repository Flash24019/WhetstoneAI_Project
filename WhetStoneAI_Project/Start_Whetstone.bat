@echo off

REM Always run from the folder this file is in
cd /d "%~dp0"

REM Check Python
where python >nul 2>nul
if errorlevel 1 (
    echo Python is not installed or not in PATH.
    pause
    exit /b
)

REM Check Ollama
where ollama >nul 2>nul
if errorlevel 1 (
    echo Ollama is not installed or not in PATH.
    pause
    exit /b
)

REM Start backend in new terminal
start cmd /k python -m uvicorn Main:app --reload

REM Wait a moment for server startup
timeout /t 3 >nul

REM Open app in browser
start http://127.0.0.1:8000