@echo off
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" app.py list-projects --projects-root projects
pause
