# FaultDx Phase 1 — Windows environment setup
# Creates a Python 3.11 virtual environment with uv and installs all dependencies.
#
# Prerequisites:
#   - Python 3.11 installed (https://www.python.org/downloads/)
#   - uv installed: pip install uv  OR  winget install astral-sh.uv
#   - Visual C++ Build Tools (required by graspologic, a GraphRAG dependency)
#     https://visualstudio.microsoft.com/visual-cpp-build-tools/
#
# Usage:
#   cd <repo_root>
#   .\scripts\bootstrap\setup_env.ps1
#
# After setup, verify with:
#   .\scripts\bootstrap\verify_env.ps1

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path

Write-Host ""
Write-Host "=== FaultDx Phase 1 — Windows Environment Setup ===" -ForegroundColor Cyan
Write-Host "Repo root: $RepoRoot"
Set-Location $RepoRoot

# ── 1. Check uv ───────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "── Step 1: Checking uv ───────────────────────────────────────────────" -ForegroundColor DarkCyan
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: uv not found." -ForegroundColor Red
    Write-Host "Install uv:  pip install uv   OR   winget install astral-sh.uv"
    exit 1
}
Write-Host "uv: $(uv --version)"

# ── 2. Check Python 3.11 ──────────────────────────────────────────────────────
Write-Host ""
Write-Host "── Step 2: Checking Python 3.11 ──────────────────────────────────────" -ForegroundColor DarkCyan
try {
    $pyVersion = python --version 2>&1
    Write-Host "System Python: $pyVersion"
} catch {
    Write-Host "WARNING: 'python' not found on PATH; uv will try to locate 3.11 independently." -ForegroundColor Yellow
}

# ── 3. Create virtual environment ─────────────────────────────────────────────
Write-Host ""
Write-Host "── Step 3: Creating .venv (Python 3.11) ──────────────────────────────" -ForegroundColor DarkCyan
if (Test-Path ".venv") {
    Write-Host ".venv already exists — skipping creation. Delete .venv to force recreate."
} else {
    uv venv --python 3.11 .venv
    Write-Host ".venv created."
}

# ── 4. Install base dependencies ──────────────────────────────────────────────
Write-Host ""
Write-Host "── Step 4: Installing base dependencies ──────────────────────────────" -ForegroundColor DarkCyan
Write-Host "This includes graphrag (latest). May take a few minutes on first run."
Write-Host "If graspologic fails to build, install Visual C++ Build Tools first."
Write-Host "See docs/runbooks/install_guide_windows.md for details."
Write-Host ""
uv pip install --python .venv\Scripts\python.exe -r requirements\base.txt

# ── 5. Install dev dependencies ───────────────────────────────────────────────
Write-Host ""
Write-Host "── Step 5: Installing dev dependencies ───────────────────────────────" -ForegroundColor DarkCyan
uv pip install --python .venv\Scripts\python.exe -r requirements\dev.txt

# ── 6. .env setup reminder ────────────────────────────────────────────────────
Write-Host ""
Write-Host "── Step 6: .env setup ────────────────────────────────────────────────" -ForegroundColor DarkCyan
if (-not (Test-Path ".env")) {
    Write-Host "No .env found. Creating from .env.example ..."
    Copy-Item ".env.example" ".env"
    Write-Host ".env created. Open it and set FAULTDX_PROVIDER_TYPE and other values." -ForegroundColor Yellow
} else {
    Write-Host ".env already exists."
}

# ── Done ──────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== Setup complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Edit .env and set FAULTDX_PROVIDER_TYPE (stub | ollama | company_api)"
Write-Host "  2. Run: .\scripts\bootstrap\verify_env.ps1"
Write-Host ""
