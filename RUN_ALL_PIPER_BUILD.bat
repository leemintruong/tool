@echo off
setlocal
cd /d "%~dp0"

echo ================================
echo AUTO YOUTUBE VIDEO BUILDER V7.1
echo ================================

if not exist ".venv\Scripts\python.exe" (
  echo Chua co .venv. Hay chay SETUP_WINDOWS.ps1 truoc.
  pause
  exit /b 1
)
if not exist "input\script.txt" (
  echo Khong tim thay input\script.txt.
  echo Hay copy input\script.example.txt thanh input\script.txt va thay noi dung mau.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\piper.exe" (
  echo Khong tim thay Piper. Hay chay INSTALL_PIPER_WINDOWS.bat truoc.
  pause
  exit /b 1
)
if not exist "voices\en_US-lessac-medium.onnx" (
  echo Khong tim thay Piper model: voices\en_US-lessac-medium.onnx
  pause
  exit /b 1
)
if not exist "voices\en_US-lessac-medium.onnx.json" (
  echo Khong tim thay Piper model config. Hay chay INSTALL_PIPER_WINDOWS.bat.
  pause
  exit /b 1
)

echo.
echo [1/1] Tao voice va build video bang pipeline...
".venv\Scripts\python.exe" app.py build --script input/script.txt --tts-model voices/en_US-lessac-medium.onnx --media assets/stock_images --out output/video_auto --thumbnail-text "KICKED OUT" --burn-subtitles
if errorlevel 1 (
  echo BUILD THAT BAI.
  pause
  exit /b 1
)

echo.
echo HOAN TAT: output\video_auto\final_video.mp4
pause
