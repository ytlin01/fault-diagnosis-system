<#
.SYNOPSIS
Convert legacy .xls workbooks to .xlsx for the structured masking pipeline.

.DESCRIPTION
This helper is intended for a controlled local raw-data environment. It uses
Microsoft Excel COM automation, keeps conversion local, and does not send data
to any external service.

Examples:
  .\scripts\ingest\convert_xls_to_xlsx.ps1 -InputDir data\raw -Pattern "Repair SOP*.xls" -DryRun
  .\scripts\ingest\convert_xls_to_xlsx.ps1 -InputDir data\raw -Pattern "Repair SOP*.xls"
  .\scripts\ingest\convert_xls_to_xlsx.ps1 -InputPath "data\raw\Repair SOP_C1STN2_BZ.xls"
#>

[CmdletBinding()]
param(
    [string]$InputPath,
    [string]$InputDir = "data\raw",
    [string]$Pattern = "*.xls",
    [string]$OutputDir,
    [switch]$DryRun,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

function Resolve-WorkbookTargets {
    if ($InputPath) {
        $item = Get-Item -LiteralPath $InputPath
        if ($item.Extension -ieq ".xls") {
            return @($item)
        }
        throw "InputPath must point to a legacy .xls workbook: $InputPath"
    }

    if (-not (Test-Path -LiteralPath $InputDir)) {
        throw "InputDir does not exist: $InputDir"
    }

    return @(Get-ChildItem -LiteralPath $InputDir -Filter $Pattern -File |
        Where-Object { $_.Extension -ieq ".xls" })
}

$targets = Resolve-WorkbookTargets
if (-not $targets -or $targets.Count -eq 0) {
    Write-Host "No .xls files matched."
    exit 0
}

$resolvedOutputDir = $null
if ($OutputDir) {
    $resolvedOutputDir = Resolve-Path -LiteralPath $OutputDir -ErrorAction SilentlyContinue
    if (-not $resolvedOutputDir) {
        if ($DryRun) {
            Write-Host "[DRY-RUN] Would create output directory: $OutputDir"
        } else {
            New-Item -ItemType Directory -Path $OutputDir | Out-Null
            $resolvedOutputDir = Resolve-Path -LiteralPath $OutputDir
        }
    }
}

Write-Host "Matched $($targets.Count) .xls file(s)."

if ($DryRun) {
    foreach ($target in $targets) {
        $destinationDir = if ($resolvedOutputDir) { $resolvedOutputDir.Path } else { $target.DirectoryName }
        $destination = Join-Path $destinationDir ($target.BaseName + ".xlsx")
        Write-Host "[DRY-RUN] $($target.FullName) -> $destination"
    }
    Write-Host "[DRY-RUN] No files converted."
    exit 0
}

$excel = $null
try {
    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false

    foreach ($target in $targets) {
        $destinationDir = if ($resolvedOutputDir) { $resolvedOutputDir.Path } else { $target.DirectoryName }
        $destination = Join-Path $destinationDir ($target.BaseName + ".xlsx")

        if ((Test-Path -LiteralPath $destination) -and -not $Force) {
            throw "Destination exists. Use -Force to overwrite: $destination"
        }

        Write-Host "Converting $($target.Name) -> $(Split-Path -Leaf $destination)"
        $workbook = $excel.Workbooks.Open($target.FullName)
        try {
            # 51 = xlOpenXMLWorkbook (.xlsx)
            $workbook.SaveAs($destination, 51)
        } finally {
            $workbook.Close($false)
        }
    }
} finally {
    if ($excel) {
        $excel.Quit()
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($excel) | Out-Null
    }
}

Write-Host "Conversion complete."
