@echo off
title Alpha Pro - Frontend
color 0E
set "ROOT=%~dp0"
cd /d "%ROOT%frontend"
echo.
echo  ====================================
echo    Frontend - http://localhost:5173
echo  ====================================
echo.
if not exist "%ROOT%frontend\node_modules" (
    echo  Installing npm dependencies...
    call npm ci
)
npm run dev
pause
