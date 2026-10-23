# FaultDx Phase 1 — Start Ollama with environment-configured model path
#
# Compatible with E2a (custom OLLAMA_MODELS) and E2b (default path).
# Reads FAULTDX_OLLAMA_* variables from .env before starting the service.
#
# Usage:
#   cd <repo_root>
#   .\scripts\bootstrap\start_ollama_e2a.ps1
#
# After starting, verify with:
#   .\scripts\bootstrap\check_ollama.ps1

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path

Write-Host ""
Write-Host "=== FaultDx Ollama Startup ===" -ForegroundColor Cyan

# ── Load .env ─────────────────────────────────────────────────────────────────
$EnvFile = Join-Path $RepoRoot ".env"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        $line = $_.Trim()
        # Skip blank lines and comments
        if ($line -and -not $line.StartsWith("#")) {
            # Strip inline comments
            $line = ($line -split "#")[0].Trim()
            if ($line -match "^([^=]+)=(.*)$") {
                $key   = $Matches[1].Trim()
                $value = $Matches[2].Trim()
                [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
            }
        }
    }
    Write-Host "Loaded: $EnvFile"
} else {
    Write-Host "WARNING: .env not found — using system environment variables only." -ForegroundColor Yellow
}

# ── Locate ollama.exe ─────────────────────────────────────────────────────────
$OllamaExe = (Get-Command ollama -ErrorAction SilentlyContinue).Source
if (-not $OllamaExe) {
    Write-Host "ERROR: ollama not found on PATH." -ForegroundColor Red
    Write-Host "Install from: https://ollama.com/download"
    exit 1
}
Write-Host "Ollama   : $OllamaExe"

# ── Stop existing Ollama processes ────────────────────────────────────────────
$existing = Get-Process -Name "ollama" -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Stopping existing Ollama process(es)..." -ForegroundColor Yellow
    $existing | Stop-Process -Force
    Start-Sleep -Seconds 2
    Write-Host "Stopped."
}

# ── Set OLLAMA_MODELS if custom dir is configured ────────────────────────────
$OllamaModelsDir = [System.Environment]::GetEnvironmentVariable("FAULTDX_OLLAMA_MODELS_DIR", "Process")

if (-not [string]::IsNullOrWhiteSpace($OllamaModelsDir)) {
    if (-not (Test-Path $OllamaModelsDir)) {
        Write-Host "WARNING: FAULTDX_OLLAMA_MODELS_DIR='$OllamaModelsDir' does not exist." -ForegroundColor Yellow
        Write-Host "         Continuing — Ollama may fall back to its default path."
    }
    $env:OLLAMA_MODELS = $OllamaModelsDir
    Write-Host "OLLAMA_MODELS : $OllamaModelsDir  (E2a custom path)" -ForegroundColor Green
} else {
    Write-Host "OLLAMA_MODELS : (default — E2b or unset)" -ForegroundColor DarkGray
}

# ── Set optional parallelism parameters ──────────────────────────────────────
$numParallel      = [System.Environment]::GetEnvironmentVariable("FAULTDX_OLLAMA_NUM_PARALLEL",      "Process")
$maxLoadedModels  = [System.Environment]::GetEnvironmentVariable("FAULTDX_OLLAMA_MAX_LOADED_MODELS", "Process")
$maxQueue         = [System.Environment]::GetEnvironmentVariable("FAULTDX_OLLAMA_MAX_QUEUE",         "Process")

if (-not [string]::IsNullOrWhiteSpace($numParallel))     { $env:OLLAMA_NUM_PARALLEL      = $numParallel;     Write-Host "OLLAMA_NUM_PARALLEL      : $numParallel" }
if (-not [string]::IsNullOrWhiteSpace($maxLoadedModels)) { $env:OLLAMA_MAX_LOADED_MODELS = $maxLoadedModels; Write-Host "OLLAMA_MAX_LOADED_MODELS : $maxLoadedModels" }
if (-not [string]::IsNullOrWhiteSpace($maxQueue))        { $env:OLLAMA_MAX_QUEUE         = $maxQueue;        Write-Host "OLLAMA_MAX_QUEUE         : $maxQueue" }

# ── Start ollama serve ────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Starting: ollama serve" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop."
Write-Host ""

& $OllamaExe serve
