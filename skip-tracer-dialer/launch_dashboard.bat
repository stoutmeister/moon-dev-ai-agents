@echo off
REM Skip Tracer Dashboard Launcher for Windows

cd /d "%~dp0"

echo.
echo ======================================
echo 🌙 Skip Tracer Dashboard
echo ======================================
echo.
echo Starting dashboard server...
echo.

python launch_dashboard.py

pause
