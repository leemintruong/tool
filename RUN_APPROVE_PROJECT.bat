@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo .venv was not found. Run SETUP_WINDOWS.ps1 first.
  pause
  exit /b 1
)

set /p PROJECT_ID=Enter the project ID to approve: 
if "%PROJECT_ID%"=="" (
  echo Project ID cannot be empty.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" app.py approve-script --project "%PROJECT_ID%"
if errorlevel 1 (
  echo.
  echo Approval failed. Review the message above and edit or rewrite the script.
  pause
  exit /b 1
)

echo.
echo Project approved. It can now be built with app.py build-project.
pause
