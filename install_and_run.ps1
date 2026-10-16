# Setup + run (more reliable than CMD encoding)
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Write-Host "[ERROR] Python not found. Install Python 3.10+ and add to PATH."
  Read-Host "Press Enter to exit"
  exit 1
}

$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
  Write-Host "[1/3] Creating .venv ..."
  python -m venv .venv
}

Write-Host "[2/3] Installing packages ..."
& $py -m pip install --upgrade pip
& $py -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
& $py -m playwright install chromium

Write-Host "[3/3] Starting app ..."
& $py (Join-Path $PSScriptRoot "main.py")
Read-Host "Press Enter to exit"
