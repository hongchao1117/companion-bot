# One-shot: venv, deps, check, run bot
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

if (-not (Test-Path .venv)) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

Write-Host "Installing dependencies..."
.\.venv\Scripts\pip install -q -r requirements.txt

Write-Host "Checking setup..."
.\.venv\Scripts\python scripts\check_setup.py
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Setup incomplete. Run:"
    Write-Host "  .\.venv\Scripts\python scripts\setup_wizard.py"
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Starting Companion bot (Ctrl+C to stop)..."
.\.venv\Scripts\python run.py
