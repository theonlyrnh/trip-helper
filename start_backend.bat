@echo off
set PYTHON=D:\ProgramData\anaconda3\envs\fapiao\python.exe

cd /d "%~dp0backend"

echo Starting Travel Invoice Assistant backend...
echo Python: %PYTHON%
echo.

"%PYTHON%" -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload

pause