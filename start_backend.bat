@echo off
title Alpha Pro - Backend API
color 0B
set "ROOT=%~dp0"
cd /d "%ROOT%backend"
echo.
echo  ====================================
echo    Backend API - http://localhost:8000
echo    API Docs  - http://localhost:8000/api/docs
echo  ====================================
echo.
if exist "%ROOT%backend\.venv\Scripts\python.exe" (
    "%ROOT%backend\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
) else if exist "%ROOT%backend\venv\Scripts\python.exe" (
    "%ROOT%backend\venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
) else (
    echo  No virtual environment found. Create one with:
    echo    cd backend ^&^& python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
    echo  Falling back to the system Python...
    python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
)
pause
