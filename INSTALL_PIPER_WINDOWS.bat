@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo .venv was not found. Running the main setup first...
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0SETUP_WINDOWS.ps1"
  if errorlevel 1 pause & exit /b 1
)

echo Installing Piper TTS...
".venv\Scripts\python.exe" -m pip install --upgrade "piper-tts==1.6.1"
if errorlevel 1 (
  echo Piper installation failed. Use Python 3.10 through 3.13, preferably Python 3.12.
  pause
  exit /b 1
)

if not exist "voices" mkdir "voices"
echo Downloading en_US-lessac-medium voice model...
".venv\Scripts\python.exe" -m piper.download_voices --download-dir "voices" en_US-lessac-medium
if errorlevel 1 (
  echo Voice model download failed.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\piper.exe" (
  echo Piper executable was not created in .venv\Scripts.
  pause
  exit /b 1
)
if not exist "voices\en_US-lessac-medium.onnx" (
  echo Piper voice model is missing after download.
  pause
  exit /b 1
)
if not exist "voices\en_US-lessac-medium.onnx.json" (
  echo Piper voice configuration is missing after download.
  pause
  exit /b 1
)

echo.
echo Piper and en_US-lessac-medium are ready.
".venv\Scripts\python.exe" app.py doctor
pause
