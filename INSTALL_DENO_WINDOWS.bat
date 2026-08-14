@echo off
setlocal
where deno >nul 2>nul
if not errorlevel 1 (
  deno --version
  echo Deno is already installed.
  pause
  exit /b 0
)

where winget >nul 2>nul
if errorlevel 1 (
  echo winget was not found. Install Deno manually, then reopen PowerShell.
  pause
  exit /b 1
)

winget install --id DenoLand.Deno -e --scope user --accept-package-agreements --accept-source-agreements
echo.
echo Close and reopen PowerShell after installation, then run app.py doctor.
pause
