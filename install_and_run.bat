@echo off
REM ASCII-only launcher
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python not found in PATH.
  pause
  exit /b 1
)

if exist ".venv\Scripts\python.exe" goto HAVE_VENV
echo [1/3] Creating virtual environment...
python -m venv .venv
if errorlevel 1 (
  echo [ERROR] Failed to create .venv
  pause
  exit /b 1
)

:HAVE_VENV
set "PY=%~dp0.venv\Scripts\python.exe"

echo [2/3] Installing dependencies...
"%PY%" -m pip install --upgrade pip
"%PY%" -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 (
  echo [ERROR] pip install failed
  pause
  exit /b 1
)

"%PY%" -m playwright install chromium

echo [3/3] Starting app...
"%PY%" "%~dp0main.py"
pause
