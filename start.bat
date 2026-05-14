@echo off
title Travel Invoice Assistant

set PYTHON=D:\ProgramData\anaconda3\envs\fapiao\python.exe
set PROJECT_DIR=%~dp0

echo ============================================
echo   Travel Invoice Assistant
echo ============================================
echo.

echo [1/2] Starting backend (port 8000)...
start "Backend" cmd /c "cd /d %PROJECT_DIR%backend && %PYTHON% -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload"

echo [2/2] Starting frontend (port 5173)...
start "Frontend" cmd /c "cd /d %PROJECT_DIR%frontend && npm run dev"

echo.
echo ============================================
echo   Backend:  http://127.0.0.1:8000/docs
echo   Frontend: http://localhost:5173/workspace
echo ============================================
echo.
echo Close this window or the two terminal windows to stop.
pause