@echo off
setlocal

set "PROJECT_DIR=%~dp0"
call :resolve_python
if errorlevel 1 goto :python_missing

pushd "%PROJECT_DIR%backend"

echo Starting Trip Helper backend...
echo Backend command: %PYTHON_CMD%
echo.

%PYTHON_CMD% -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload

pause
exit /b 0

:resolve_python
if defined PYTHON (
  "%PYTHON%" --version >nul 2>nul
  if not errorlevel 1 (
    set "PYTHON_CMD=^"%PYTHON%^""
    exit /b 0
  )
)
python --version >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_CMD=python"
  exit /b 0
)
py -3 --version >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_CMD=py -3"
  exit /b 0
)
where uv >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_CMD=uv run --python 3.11 --with-requirements ^"%PROJECT_DIR%backend\requirements.txt^" python"
  exit /b 0
)
exit /b 1

:python_missing
echo [ERROR] Python 3 was not found, and uv fallback is not available.
echo Install Python 3.11+ or install uv, or set PYTHON to a valid python.exe path, then run this script again.
pause
exit /b 1
