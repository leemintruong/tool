@echo off
setlocal
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0SETUP_GEMINI_FREE_WINDOWS.ps1"
if errorlevel 1 (
  echo.
  echo Gemini Free setup failed.
  pause
  exit /b 1
)

echo.
echo Close every PowerShell window and open a new one before running Gemini rewrite.
pause
