Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    Write-Host "Exporting latest EU5 savegame facts and savegame explorer..."
    uv run eu5-orchestrator savegame --project constructor.toml
} finally {
    Pop-Location
}
