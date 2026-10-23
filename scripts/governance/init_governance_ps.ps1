# Compatibility wrapper for the Python governance initializer.
# Canonical storage is data/governance/source_inventory.csv, not data_governance.xlsx.

param(
    [switch]$DryRun,
    [switch]$Reset
)

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$ArgsList = @("-m", "scripts.governance.init_governance")
if ($DryRun) { $ArgsList += "--dry-run" }
if ($Reset) { $ArgsList += "--reset" }

Push-Location $ProjectRoot
try {
    python @ArgsList
}
finally {
    Pop-Location
}
