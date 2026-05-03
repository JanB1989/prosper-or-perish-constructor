param(
    [string[]] $Examples = @(
        "goods_flow_explorer.html",
        "savegame_explorer.html"
    )
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$graphsDir = Join-Path $repoRoot "graphs"
$examplesDir = Join-Path $repoRoot "docs/examples"

New-Item -ItemType Directory -Force -Path $examplesDir | Out-Null

foreach ($example in $Examples) {
    $source = Join-Path $graphsDir $example
    $destination = Join-Path $examplesDir $example

    if (-not (Test-Path -LiteralPath $source)) {
        throw "Missing generated graph output: $source"
    }

    Copy-Item -LiteralPath $source -Destination $destination -Force
    Write-Host "Updated docs/examples/$example"
}

$graphAssetsDir = Join-Path $graphsDir "assets"
if (Test-Path -LiteralPath $graphAssetsDir) {
    $exampleAssetsDir = Join-Path $examplesDir "assets"
    New-Item -ItemType Directory -Force -Path $exampleAssetsDir | Out-Null
    Copy-Item -Path (Join-Path $graphAssetsDir "*") -Destination $exampleAssetsDir -Recurse -Force
    Write-Host "Updated docs/examples/assets"
}
