Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    Write-Host "Building accepted blueprints into the constructor mod copy..."
    uv run eu5-orchestrator build --project constructor.toml --overwrite

    Write-Host "Deploying the local mod copy into the live Paradox mod folder..."
    uv run eu5-orchestrator deploy --project constructor.toml --clean

    Write-Host "Refreshing parser facts and goods-flow explorer..."
    uv run eu5-orchestrator analyze --project constructor.toml
} finally {
    Pop-Location
}
