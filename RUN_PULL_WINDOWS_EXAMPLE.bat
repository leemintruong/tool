@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Chua co .venv. Hay chay SETUP_WINDOWS.ps1 truoc.
  pause
  exit /b 1
)
rem Thay URL ben duoi bang noi dung ban co quyen tai va su dung.
".venv\Scripts\python.exe" app.py pull --url "PASTE_URL_HERE" --out assets\stock_videos --archive data\download_archive.txt --restrict-filenames
pause
