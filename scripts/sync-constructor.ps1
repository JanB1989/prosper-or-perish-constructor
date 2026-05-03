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

function Invoke-FusedPopulationCapacityInjection {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,

        [Parameter(Mandatory = $true)]
        [string]$ModRoot
    )

    $scoresPath = Join-Path $RepoRoot "artifacts\data\population_capacity\current_capacity_map\population_capacity_scores.csv"
    $modifiersPath = Join-Path $ModRoot "main_menu\common\static_modifiers\pp_location_modifiers.txt"
    if (-not (Test-Path -LiteralPath $scoresPath -PathType Leaf)) {
        Write-Warning "Skipping fused population-capacity injection: missing $scoresPath"
        return
    }
    if (-not (Test-Path -LiteralPath $modifiersPath -PathType Leaf)) {
        throw "Cannot inject fused population capacity; missing generated modifiers file: $modifiersPath"
    }

    $scores = @{}
    Import-Csv -LiteralPath $scoresPath | ForEach-Object {
        $tag = [string]$_.location_tag
        $rawCapacity = [double]$_.final_local_population_capacity
        if ([string]::IsNullOrWhiteSpace($tag)) {
            return
        }

        # The fusion dashboard stores human counts. EU5's static modifier displays these
        # values as thousands, so 229000 becomes local_population_capacity = 229.
        $scores[$tag.ToLowerInvariant()] = [int][Math]::Round($rawCapacity / 1000.0)
    }

    if ($scores.Count -eq 0) {
        throw "Cannot inject fused population capacity; no scores were read from $scoresPath"
    }

    $lines = Get-Content -LiteralPath $modifiersPath
    $patched = 0
    $inserted = 0
    $currentTag = $null
    $blockHasCapacity = $false
    $output = [System.Collections.Generic.List[string]]::new()

    foreach ($line in $lines) {
        $blockMatch = [regex]::Match($line, '^\s*pp_loc_(\S+)\s*=\s*\{\s*$')
        if ($blockMatch.Success) {
            $currentTag = $blockMatch.Groups[1].Value.ToLowerInvariant()
            $blockHasCapacity = $false
            $output.Add($line)
            continue
        }

        if ($null -ne $currentTag -and $scores.ContainsKey($currentTag)) {
            if ($line -match '^\s*local_population_capacity\s*=') {
                $output.Add("`tlocal_population_capacity = $($scores[$currentTag])")
                $blockHasCapacity = $true
                $patched++
                continue
            }

            if ($line -match '^\s*local_[a-z0-9_]+_output_modifier\s*=' -and -not $blockHasCapacity) {
                $output.Add("`tlocal_population_capacity = $($scores[$currentTag])")
                $blockHasCapacity = $true
                $inserted++
            }
        }

        if ($null -ne $currentTag -and $line -match '^\s*\}\s*$') {
            if ($scores.ContainsKey($currentTag) -and -not $blockHasCapacity) {
                $output.Add("`tlocal_population_capacity = $($scores[$currentTag])")
                $inserted++
            }
            $currentTag = $null
            $blockHasCapacity = $false
        }

        $output.Add($line)
    }

    Set-Content -LiteralPath $modifiersPath -Value $output -Encoding UTF8
    Write-Host "Injected fused population capacity into pp_location_modifiers.txt: patched=$patched inserted=$inserted scores=$($scores.Count)"
}

function Upsert-GeneratedLocalizationBlock {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$StartMarker,

        [Parameter(Mandatory = $true)]
        [string]$EndMarker,

        [Parameter(Mandatory = $true)]
        [string[]]$Lines,

        [string[]]$KeysToRemove = @()
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Cannot inject localization; missing file: $Path"
    }

    $content = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    $newline = if ($content.Contains("`r`n")) { "`r`n" } else { "`n" }
    $block = ($Lines -join $newline) + $newline
    $pattern = "(?s)^[ `t]*$([regex]::Escape($StartMarker))\r?\n.*?^[ `t]*$([regex]::Escape($EndMarker))\r?\n?"

    if ([regex]::IsMatch($content, $pattern, [System.Text.RegularExpressions.RegexOptions]::Multiline)) {
        $content = [regex]::Replace(
            $content,
            $pattern,
            [System.Text.RegularExpressions.MatchEvaluator]{ param($match) $block },
            [System.Text.RegularExpressions.RegexOptions]::Multiline
        )
    } else {
        foreach ($key in $KeysToRemove) {
            $keyPattern = "(?m)^[ `t]*$([regex]::Escape($key)):\s*`"[^`"]*`"\r?\n?"
            $content = [regex]::Replace($content, $keyPattern, "")
        }

        $bomPattern = [regex]::Escape([string][char]0xFEFF)
        $headerPattern = "(?m)^${bomPattern}?l_english:\s*\r?\n"
        if (-not [regex]::IsMatch($content, $headerPattern)) {
            throw "Cannot inject localization; missing l_english header in $Path"
        }
        $content = [regex]::Replace(
            $content,
            $headerPattern,
            [System.Text.RegularExpressions.MatchEvaluator]{ param($match) $match.Value + $block },
            1
        )
    }

    Set-Content -LiteralPath $Path -Value $content -Encoding UTF8 -NoNewline
}

function Invoke-LocationPotentialLocalizationInjection {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ModRoot
    )

    $localizationRoot = Join-Path $ModRoot "main_menu\localization\english"
    $modifierLocalizationPath = Join-Path $localizationRoot "pp_location_modifiers_l_english.yml"
    $europediaLocalizationPath = Join-Path $localizationRoot "pp_europedia_l_english.yml"

    Upsert-GeneratedLocalizationBlock `
        -Path $modifierLocalizationPath `
        -StartMarker "  # Start generated location potential modifier help" `
        -EndMarker "  # End generated location potential modifier help" `
        -KeysToRemove @("pp_location_modifiers_title", "pp_location_modifiers_title_desc") `
        -Lines @(
            "  # Start generated location potential modifier help",
            '  pp_location_modifiers_title: "Prosper or Perish per-location suitability"',
            '  pp_location_modifiers_title_desc: "Population capacity and local output modifiers for this location are calculated from [pp_location_potential|e]."',
            "  # End generated location potential modifier help"
        )

    Upsert-GeneratedLocalizationBlock `
        -Path $europediaLocalizationPath `
        -StartMarker "  # Start generated location potential concept" `
        -EndMarker "  # End generated location potential concept" `
        -KeysToRemove @("game_concept_pp_location_potential", "game_concept_pp_location_potential_desc") `
        -Lines @(
            "  # Start generated location potential concept",
            '  game_concept_pp_location_potential: "Location Potential"',
            '  game_concept_pp_location_potential_desc: "Location Potential is the shared calculation behind Prosper or Perish per-location population capacity and local output modifiers.\n\nThe values combine in-game geography with external map-derived evidence. They are meant to represent how suitable each location is for supporting people and producing local raw materials.\n\n#T In-game factors:#!\n$BULLET$ Topography\n$BULLET$ Climate\n$BULLET$ Vegetation\n$BULLET$ River access\n$BULLET$ Lake access\n$BULLET$ Coastal access\n$BULLET$ Location RGO\n$BULLET$ Soil data\n\n#T Out-of-game maps and pipeline evidence:#!\n$BULLET$ GAEZ crop potential and suitability maps\n$BULLET$ HYDE historical population coverage\n$BULLET$ Freshwater food support maps\n$BULLET$ Marine food support maps\n$BULLET$ Livestock food support maps\n$BULLET$ Plant food support maps\n$BULLET$ Wild subsistence support maps\n$BULLET$ Land-use confidence maps\n$BULLET$ Water confidence maps\n$BULLET$ Calibration and control-point data from the population-capacity pipeline\n\nThe final numbers are generated by the constructor pipeline, then injected into the shared per-location static modifiers used by the mod."',
            "  # End generated location potential concept"
        )

    Write-Host "Injected shared Location Potential localization."
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
    Invoke-FusedPopulationCapacityInjection -RepoRoot $repoRoot -ModRoot $source
    Invoke-LocationPotentialLocalizationInjection -ModRoot $source
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
