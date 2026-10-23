# FaultDx Phase 1 — Ollama connectivity and model check
#
# Verifies that Ollama is running and the configured model is available.
# Works for both E2a (custom path) and E2b (default path).
#
# Usage:
#   cd <repo_root>
#   .\scripts\bootstrap\check_ollama.ps1

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path

Write-Host ""
Write-Host "=== FaultDx Ollama Check ===" -ForegroundColor Cyan

# ── Load .env ─────────────────────────────────────────────────────────────────
$EnvFile = Join-Path $RepoRoot ".env"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#")) {
            $line = ($line -split "#")[0].Trim()
            if ($line -match "^([^=]+)=(.*)$") {
                [System.Environment]::SetEnvironmentVariable($Matches[1].Trim(), $Matches[2].Trim(), "Process")
            }
        }
    }
}

$OllamaHost  = [System.Environment]::GetEnvironmentVariable("FAULTDX_OLLAMA_HOST",   "Process")
$TargetModel = [System.Environment]::GetEnvironmentVariable("FAULTDX_OLLAMA_MODEL",  "Process")
$ModelsDir   = [System.Environment]::GetEnvironmentVariable("FAULTDX_OLLAMA_MODELS_DIR", "Process")

if ([string]::IsNullOrWhiteSpace($OllamaHost)) { $OllamaHost = "http://localhost:11434" }

Write-Host ""
Write-Host "Config:"
Write-Host "  OLLAMA_HOST       : $OllamaHost"
Write-Host "  OLLAMA_MODEL      : $(if ($TargetModel) { $TargetModel } else { '(not set)' })"
Write-Host "  OLLAMA_MODELS_DIR : $(if ($ModelsDir) { $ModelsDir } else { '(default)' })"

$results = @()

# ── Check 1: HTTP reachability ────────────────────────────────────────────────
Write-Host ""
Write-Host "── Checks ────────────────────────────────────────────────────────────"
try {
    $versionResp = Invoke-RestMethod -Uri "$OllamaHost/api/version" -TimeoutSec 5
    $version = $versionResp.version
    Write-Host "  [PASS] Ollama HTTP reachable  (version=$version)" -ForegroundColor Green
    $results += $true
} catch {
    Write-Host "  [FAIL] Ollama not reachable at $OllamaHost" -ForegroundColor Red
    Write-Host "         Run: .\scripts\bootstrap\start_ollama_e2a.ps1"
    $results += $false
}

# ── Check 2: List available models ────────────────────────────────────────────
try {
    $tagsResp    = Invoke-RestMethod -Uri "$OllamaHost/api/tags" -TimeoutSec 5
    $modelNames  = $tagsResp.models | ForEach-Object { $_.name }
    $modelCount  = $modelNames.Count
    Write-Host "  [PASS] Available models ($modelCount):" -ForegroundColor Green
    $modelNames | ForEach-Object { Write-Host "           - $_" -ForegroundColor DarkGray }
    $results += $true
} catch {
    Write-Host "  [FAIL] Could not retrieve model list" -ForegroundColor Red
    $modelNames = @()
    $results += $false
}

# ── Check 3: Target model present ────────────────────────────────────────────
if (-not [string]::IsNullOrWhiteSpace($TargetModel)) {
    $found = $modelNames | Where-Object { $_ -like "$TargetModel*" }
    if ($found) {
        Write-Host "  [PASS] Target model '$TargetModel' is available" -ForegroundColor Green
        $results += $true
    } else {
        Write-Host "  [FAIL] Target model '$TargetModel' NOT found in available models" -ForegroundColor Red
        Write-Host "         To pull: ollama pull $TargetModel" -ForegroundColor Yellow
        Write-Host "         If model files exist in OLLAMA_MODELS_DIR, Ollama may not have" -ForegroundColor Yellow
        Write-Host "         been started with the correct path. Run start_ollama_e2a.ps1 first." -ForegroundColor Yellow
        $results += $false
    }
} else {
    Write-Host "  [SKIP] FAULTDX_OLLAMA_MODEL not set — skipping target model check" -ForegroundColor DarkGray
}

# ── Check 4: nomic-embed-text present (required for GraphRAG) ─────────────────
$embedFound = $modelNames | Where-Object { $_ -like "nomic-embed-text*" }
if ($embedFound) {
    Write-Host "  [PASS] nomic-embed-text available (required for GraphRAG embedding)" -ForegroundColor Green
    $results += $true
} else {
    Write-Host "  [WARN] nomic-embed-text not found — needed for GraphRAG indexing" -ForegroundColor Yellow
    Write-Host "         To pull: ollama pull nomic-embed-text" -ForegroundColor Yellow
    $results += $true  # warning, not hard fail
}

# ── Summary ───────────────────────────────────────────────────────────────────
Write-Host ""
$passed = ($results | Where-Object { $_ }).Count
$failed = ($results | Where-Object { -not $_ }).Count
Write-Host "── Summary ────────────────────────────────────────────────────────────"
Write-Host "  $passed/$($results.Count) checks passed"
if ($failed -gt 0) {
    Write-Host "  $failed check(s) FAILED" -ForegroundColor Red
    exit 1
} else {
    Write-Host "  Ollama is ready." -ForegroundColor Green
    exit 0
}
