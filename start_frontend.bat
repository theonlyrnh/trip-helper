@echo off
setlocal

set "PROJECT_DIR=%~dp0"

where npm >nul 2>nul
if errorlevel 1 goto :npm_missing

cd /d "%PROJECT_DIR%frontend"

if not exist "node_modules" (
  echo [INFO] node_modules not found. Installing frontend dependencies...
  call npm install
  if errorlevel 1 goto :install_failed
)

echo Starting Trip Helper frontend...
echo.

call npm run dev

pause
exit /b 0

:npm_missing
echo [ERROR] npm was not found. Please install Node.js 18+ and npm.
pause
exit /b 1

:install_failed
echo [ERROR] Failed to install frontend dependencies.
pause
exit /b 1
