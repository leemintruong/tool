@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Chua co .venv. Hay chay SETUP_WINDOWS.ps1 truoc.
  pause
  exit /b 1
)
if not exist "input\script.txt" (
  echo Khong tim thay input\script.txt. Hay copy tu input\script.example.txt.
  pause
  exit /b 1
)
if not exist "input\voice.wav" (
  echo Khong tim thay input\voice.wav.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" app.py build --script input/script.txt --voice input/voice.wav --media assets/stock_images --out output/video_001 --thumbnail-text "KICKED OUT" --burn-subtitles
pause
