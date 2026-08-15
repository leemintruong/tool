@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo .venv was not found. Running setup first...
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0SETUP_WINDOWS.ps1"
  if errorlevel 1 pause & exit /b 1
)

".venv\Scripts\python.exe" app.py ingest --url "https://www.youtube.com/watch?v=Ce3G2LHKkNk" --projects-root projects --languages "en,en-US,en-GB,vi"

echo.
echo When successful, open:
echo projects\Ce3G2LHKkNk\transcript\transcript_clean.txt
echo projects\Ce3G2LHKkNk\prompts\rewrite_prompt.txt
echo Or run Gemini rewrite with:
echo .venv\Scripts\python.exe app.py rewrite --project Ce3G2LHKkNk
pause
