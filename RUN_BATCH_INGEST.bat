@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo .venv was not found. Run SETUP_WINDOWS.ps1 first.
  pause
  exit /b 1
)
if not exist "input\youtube_urls.txt" (
  echo input\youtube_urls.txt was not found.
  echo Copy input\youtube_urls.example.txt to input\youtube_urls.txt and add one URL per line.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" app.py batch-ingest --file input\youtube_urls.txt --projects-root projects --languages "en,en-US,en-GB,vi"
pause
