@echo off
title Alpha Pro - Backend API
color 0B
cd /d "f:\New folder\backend"
echo.
echo  ====================================
echo    Backend API - http://localhost:8000
echo    API Docs  - http://localhost:8000/docs
echo  ====================================
echo.
if exist "f:\New folder\backend\venv\Scripts\uvicorn.exe" (
    "f:\New folder\backend\venv\Scripts\uvicorn.exe" app.main:app --reload --host 0.0.0.0 --port 8000
) else (
    python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
)
pause
