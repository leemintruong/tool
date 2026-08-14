@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo .venv was not found. Run SETUP_WINDOWS.ps1 first.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -m pip install -r requirements-transcription.txt
if errorlevel 1 (
  echo Whisper installation failed.
  pause
  exit /b 1
)

echo.
echo faster-whisper installation completed.
".venv\Scripts\python.exe" app.py doctor
pause
