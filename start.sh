#!/bin/bash
# Quick start script for Linux/Mac

echo "========================================"
echo "Audio Pipeline Web App - Quick Start"
echo "========================================"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "[1/4] Setting up environment..."
    python setup_env.py
    echo ""
else
    echo "[1/4] Environment file found (skip setup)"
    echo ""
fi

# Check if venv exists
VENV_DIR=""
if [ -d ".venv311" ]; then VENV_DIR=".venv311"; fi
if [ -z "$VENV_DIR" ] && [ -d ".venv" ]; then VENV_DIR=".venv"; fi
if [ -z "$VENV_DIR" ] && [ -d "venv" ]; then VENV_DIR="venv"; fi

if [ -z "$VENV_DIR" ]; then
    echo "[ERROR] Virtual environment not found!"
    echo "Please run: py -3.11 -m venv .venv311"
    echo "Then run: .venv311/bin/pip install -r requirements.txt"
    exit 1
fi

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Stopping services..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    wait
    echo "All services stopped."
    exit
}

# Trap Ctrl+C
trap cleanup INT TERM

# Start backend (background)
echo "[2/4] Starting backend..."
source "$VENV_DIR/bin/activate"
python -m uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Wait for backend to start
echo "[3/4] Waiting for backend to start..."
sleep 5

# Start frontend (background)
echo "[4/4] Starting frontend..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "========================================"
echo "Services started!"
echo "========================================"
echo ""
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo "API Docs:  http://localhost:8000/api/docs"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Wait for processes
wait $BACKEND_PID $FRONTEND_PID
