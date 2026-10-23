# FaultDx Phase 1 — Windows environment verification wrapper
# Activates the project venv and delegates to verify_env.py.
#
# Usage:
#   cd <repo_root>
#   .\scripts\bootstrap\verify_env.ps1

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path

Write-Host ""
Write-Host "=== FaultDx Environment Verification (Windows) ===" -ForegroundColor Cyan
Write-Host "Repo root : $RepoRoot"
Write-Host "Platform  : Windows / PowerShell $($PSVersionTable.PSVersion)"
Write-Host ""

# ── Locate Python ──────────────────────────────────────────────────────────────
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (Test-Path $VenvPython) {
    $PythonExe = $VenvPython
    Write-Host "Using venv  : $PythonExe" -ForegroundColor DarkGray
} else {
    # Fall back to system Python if venv not yet created
    $PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $PythonExe) {
        Write-Host "ERROR: Python not found. Run setup_env.ps1 first." -ForegroundColor Red
        exit 1
    }
    Write-Host "WARNING: .venv not found — using system Python: $PythonExe" -ForegroundColor Yellow
}

Write-Host "Python    : $( & $PythonExe --version 2>&1 )"
Write-Host ""

# ── Run verify_env.py ──────────────────────────────────────────────────────────
$VerifyScript = Join-Path $RepoRoot "scripts\bootstrap\verify_env.py"
& $PythonExe $VerifyScript

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Verification FAILED. Fix the issues above before proceeding." -ForegroundColor Red
    exit 1
} else {
    Write-Host ""
    Write-Host "Verification PASSED. Environment is ready." -ForegroundColor Green
    exit 0
}
