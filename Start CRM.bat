@echo off
title Alpha Pro MENA CRM - Starting...
color 0A

echo.
echo  =========================================
echo    Alpha Pro MENA CRM - Launching...
echo  =========================================
echo.
echo  Starting Backend API...
start "" "f:\New folder\start_backend.bat"

timeout /t 4 /nobreak >nul

echo  Starting Frontend...
start "" "f:\New folder\start_frontend.bat"

timeout /t 5 /nobreak >nul

echo  Opening browser...
start "" "http://localhost:5173"

echo.
echo  Done! Both servers are running in separate windows.
echo  Close those windows to shut down the CRM.
echo.
timeout /t 3 /nobreak >nul
exit
