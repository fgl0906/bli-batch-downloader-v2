@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] .venv not found. Run install_and_run.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" "%~dp0main.py"
pause
