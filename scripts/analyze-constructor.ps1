Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    Write-Host "Exporting Prosper or Perish Constructor parser facts and goods-flow explorer..."
    uv run eu5-orchestrator analyze --project constructor.toml
    & .\scripts\publish-docs-examples.ps1 -Examples goods_flow_explorer.html
} finally {
    Pop-Location
}
