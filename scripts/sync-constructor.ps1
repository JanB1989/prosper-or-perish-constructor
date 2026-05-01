Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot

function Get-TomlStringValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$Key
    )

    $content = Get-Content -LiteralPath $Path -Raw
    $pattern = "(?m)^\s*$([regex]::Escape($Key))\s*=\s*`"([^`"]+)`""
    $match = [regex]::Match($content, $pattern)
    if (-not $match.Success) {
        throw "Missing '$Key' in $Path."
    }

    return $match.Groups[1].Value
}

function Resolve-ProjectPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return [System.IO.Path]::GetFullPath($Path)
    }

    return [System.IO.Path]::GetFullPath((Join-Path $repoRoot $Path))
}

function Assert-SafeMirrorTarget {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Source,

        [Parameter(Mandatory = $true)]
        [string]$Target
    )

    $normalizedSource = $Source.TrimEnd('\', '/')
    $normalizedTarget = $Target.TrimEnd('\', '/')
    if ($normalizedSource -eq $normalizedTarget) {
        throw "Refusing to mirror: source and target are the same directory."
    }

    $targetInfo = [System.IO.DirectoryInfo]::new($normalizedTarget)
    if ($null -eq $targetInfo.Parent -or $targetInfo.Parent.Name -ne "mod") {
        throw "Refusing to mirror: deploy target must be a specific mod folder under an EU5 'mod' directory. Target: $Target"
    }

    if ($targetInfo.Name -ne ([System.IO.DirectoryInfo]::new($normalizedSource)).Name) {
        throw "Refusing to mirror: source and target folder names differ. Source: $Source Target: $Target"
    }
}

function Get-RelativeFileHashes {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Root
    )

    $rootPath = [System.IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
    $hashes = @{}
    if (-not (Test-Path -LiteralPath $rootPath)) {
        return $hashes
    }

    Get-ChildItem -LiteralPath $rootPath -Recurse -File | ForEach-Object {
        $relativePath = $_.FullName.Substring($rootPath.Length + 1)
        $hashes[$relativePath] = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
    }

    return $hashes
}

function Assert-MirroredDirectories {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Source,

        [Parameter(Mandatory = $true)]
        [string]$Target
    )

    $sourceHashes = Get-RelativeFileHashes -Root $Source
    $targetHashes = Get-RelativeFileHashes -Root $Target
    $allRelativePaths = @($sourceHashes.Keys + $targetHashes.Keys) | Sort-Object -Unique
    $differences = foreach ($relativePath in $allRelativePaths) {
        if (-not $sourceHashes.ContainsKey($relativePath)) {
            "Only in target: $relativePath"
        } elseif (-not $targetHashes.ContainsKey($relativePath)) {
            "Missing from target: $relativePath"
        } elseif ($sourceHashes[$relativePath] -ne $targetHashes[$relativePath]) {
            "Hash differs: $relativePath"
        }
    }

    if (@($differences).Count -gt 0) {
        $preview = ($differences | Select-Object -First 40) -join [Environment]::NewLine
        throw "Push verification failed. Constructor and live mod folders differ:$([Environment]::NewLine)$preview"
    }

    Write-Host "Push verification passed: $($sourceHashes.Count) files match exactly."
}

Push-Location $repoRoot
try {
    $projectConfig = Join-Path $repoRoot "constructor.toml"
    $localConfig = Join-Path $repoRoot "constructor.local.toml"
    $source = Resolve-ProjectPath (Get-TomlStringValue -Path $projectConfig -Key "mod_root")
    $target = Resolve-ProjectPath (Get-TomlStringValue -Path $localConfig -Key "target")

    Write-Host "Building accepted blueprints into the constructor mod copy..."
    uv run eu5-orchestrator build --project constructor.toml --overwrite
    if ($LASTEXITCODE -ne 0) {
        throw "Constructor build failed with exit code $LASTEXITCODE. Refusing to mirror into live mod folder."
    }

    if (-not (Test-Path -LiteralPath $source -PathType Container)) {
        throw "Constructor mod source does not exist: $source"
    }
    Assert-SafeMirrorTarget -Source $source -Target $target

    Write-Host "Mirroring constructor mod into live Paradox mod folder..."
    Write-Host "Source: $source"
    Write-Host "Target: $target"
    robocopy $source $target /MIR /R:2 /W:1 /DCOPY:DAT /COPY:DAT /XJ /NFL /NDL /NP
    $robocopyExitCode = $LASTEXITCODE
    if ($robocopyExitCode -ge 8) {
        throw "Robocopy failed with exit code $robocopyExitCode."
    }

    Assert-MirroredDirectories -Source $source -Target $target
    Write-Host "Push complete. The live Paradox mod folder is an exact mirror of the constructor output."
} finally {
    Pop-Location
}
