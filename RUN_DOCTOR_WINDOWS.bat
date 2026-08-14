@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Chua co .venv. Hay chay SETUP_WINDOWS.ps1 truoc.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" app.py doctor
pause
