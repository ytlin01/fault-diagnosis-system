<#
.SYNOPSIS
    FaultDx structured data masking — PowerShell wrapper.

.DESCRIPTION
    Activates the project venv and runs the structured masking pipeline.
    Loads .env automatically.

.EXAMPLE
    # Inspect workbook sheets (no masking, just metadata)
    .\scripts\ingest\run_structured_masking.ps1 -Source y25_downtime -Inspect

    # Inspect with different header row
    .\scripts\ingest\run_structured_masking.ps1 -Source y25_downtime -Inspect -HeaderRow 1

    # Dry-run preview
    .\scripts\ingest\run_structured_masking.ps1 -Source y25_downtime -DryRun

    # Dry-run preview with local name mapping
    .\scripts\ingest\run_structured_masking.ps1 -Source y25_downtime -DryRun -ApplyNameMapping

    # Temporarily override file patterns
    .\scripts\ingest\run_structured_masking.ps1 -Source y25_downtime -FilePatterns "C1STN DT*.xlsx"

    # Full run
    .\scripts\ingest\run_structured_masking.ps1 -Source y25_downtime

    # List available sources
    .\scripts\ingest\run_structured_masking.ps1 -ListSources

    # Preview rules only (no data needed)
    .\scripts\ingest\run_structured_masking.ps1 -Source y25_downtime -RulesOnly
#>

param(
    [string]$Source,
    [switch]$DryRun,
    [int]$Rows = 5,
    [switch]$ListSources,
    [switch]$RulesOnly,
    [switch]$Inspect,
    [int]$HeaderRow = -1,
    [string]$RawDir,
    [string]$Config,
    [switch]$ApplyNameMapping,
    [string]$NameMappingFile,
    [string]$FilePatterns
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path "$PSScriptRoot\..\..").Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Error "Python venv not found at $VenvPython. Run setup_env first."
    exit 1
}

if ($ListSources) {
    $args_list = @("$ProjectRoot\scripts\ingest\run_mask_structured.py", "--list-sources")
}
elseif ($Inspect) {
    if (-not $Source) { Write-Error "-Source is required with -Inspect"; exit 1 }
    $args_list = @("$ProjectRoot\scripts\ingest\preview_masking.py", "inspect", "--source", $Source)
    if ($HeaderRow -ge 0) {
        $args_list += "--header-row"
        $args_list += $HeaderRow.ToString()
    }
    if ($FilePatterns) {
        $args_list += "--file-patterns"
        $args_list += $FilePatterns
    }
}
elseif ($RulesOnly) {
    if (-not $Source) { Write-Error "-Source is required with -RulesOnly"; exit 1 }
    $args_list = @("$ProjectRoot\scripts\ingest\preview_masking.py", "rules", "--source", $Source)
}
else {
    if (-not $Source) { Write-Error "-Source is required. Use -ListSources to see options."; exit 1 }
    $args_list = @("$ProjectRoot\scripts\ingest\run_mask_structured.py", "--source", $Source)

    if ($DryRun) {
        $args_list += "--dry-run"
        $args_list += "--rows"
        $args_list += $Rows.ToString()
    }

    if ($ApplyNameMapping) {
        $args_list += "--apply-name-mapping"
    }
    if ($NameMappingFile) {
        $args_list += "--name-mapping-file"
        $args_list += $NameMappingFile
    }
    if ($FilePatterns) {
        $args_list += "--file-patterns"
        $args_list += $FilePatterns
    }
}

if ($RawDir) {
    $args_list += "--raw-dir"
    $args_list += $RawDir
}
if ($Config) {
    $args_list += "--config"
    $args_list += $Config
}

Write-Host "[FaultDx] Running structured masking..." -ForegroundColor Cyan
Write-Host "[FaultDx] Command: $VenvPython $($args_list -join ' ')" -ForegroundColor DarkGray

& $VenvPython $args_list

if ($LASTEXITCODE -ne 0) {
    Write-Error "Masking pipeline exited with code $LASTEXITCODE"
    exit $LASTEXITCODE
}
