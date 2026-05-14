@echo off

cd /d "%~dp0frontend"

echo Starting Travel Invoice Assistant frontend...
echo.

call npm run dev

pause