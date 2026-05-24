@echo off
setlocal
title Trip Helper

set "PROJECT_DIR=%~dp0"

where npm >nul 2>nul
if errorlevel 1 goto :npm_missing

if not exist "%PROJECT_DIR%frontend\node_modules" (
  echo [INFO] frontend\node_modules not found. Installing frontend dependencies...
  pushd "%PROJECT_DIR%frontend"
  call npm install
  if errorlevel 1 goto :frontend_install_failed
  popd
)

echo ============================================
echo   Trip Helper
echo ============================================
echo Project dir: %PROJECT_DIR%
echo.

echo [1/2] Starting backend (port 8000)...
start "Trip Helper Backend" "%PROJECT_DIR%start_backend.bat"

echo [2/2] Starting frontend (port 5173)...
start "Trip Helper Frontend" "%PROJECT_DIR%start_frontend.bat"

echo.
echo ============================================
echo   Backend:  http://127.0.0.1:8000/docs
echo   Frontend: http://localhost:5173/workspace
echo ============================================
echo.
echo PaddleOCR is optional. If OCR is unavailable, use manual review and correction in the workspace.
echo Close the two terminal windows to stop services.
pause
exit /b 0

:npm_missing
echo [ERROR] npm was not found. Please install Node.js 18+ and npm.
pause
exit /b 1

:frontend_install_failed
echo [ERROR] Failed to install frontend dependencies.
popd
pause
exit /b 1
