@echo off
REM Quick start script for Windows
REM Run this to start backend and frontend

echo ========================================
echo Audio Pipeline Web App - Quick Start
echo ========================================
echo.

REM Check if .env exists
if not exist .env (
    echo [1/4] Setting up environment...
    python setup_env.py
    echo.
) else (
    echo [1/4] Environment file found (skip setup)
    echo.
)

REM Check if venv exists
set "VENV_DIR="
if exist .venv311 set "VENV_DIR=.venv311"
if "%VENV_DIR%"=="" if exist .venv set "VENV_DIR=.venv"
if "%VENV_DIR%"=="" if exist venv set "VENV_DIR=venv"

if "%VENV_DIR%"=="" (
    echo [ERROR] Virtual environment not found!
    echo Please run: py -3.11 -m venv .venv311
    echo Then run: .venv311\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

REM Start backend (new window)
echo [2/4] Starting backend...
start "Audio Pipeline Backend" cmd /k "cd /d %~dp0 && %VENV_DIR%\Scripts\activate && python -m uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000"

REM Wait for backend to start
echo [3/4] Waiting for backend to start...
timeout /t 5 /nobreak > nul

REM Start frontend
echo [4/4] Starting frontend...
cd frontend
start "Audio Pipeline Frontend" cmd /k "npm run dev"
cd ..

echo.
echo ========================================
echo Services started!
echo ========================================
echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
echo API Docs:  http://localhost:8000/api/docs
echo.
echo Press any key to stop all services (close windows manually)
pause
