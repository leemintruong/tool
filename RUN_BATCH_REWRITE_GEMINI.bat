@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo .venv was not found. Run SETUP_WINDOWS.ps1 first.
  pause
  exit /b 1
)
if "%GEMINI_API_KEY%"=="" (
  echo GEMINI_API_KEY is not available in this terminal.
  echo Run SETUP_GEMINI_FREE_WINDOWS.bat, then close and reopen PowerShell.
  pause
  exit /b 1
)

echo Rewriting all projects currently waiting for AI...
echo No script will be approved or rendered automatically.
".venv\Scripts\python.exe" app.py batch-rewrite --projects-root projects --delay-seconds 10
if errorlevel 1 (
  echo.
  echo One or more rewrites failed. Check each project's logs\rewrite.log.
  pause
  exit /b 1
)

echo.
echo Gemini batch rewrite completed. Run app.py list-projects to review statuses.
pause
