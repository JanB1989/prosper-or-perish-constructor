# Clones this repo the way Windows does by default (long paths off) under a root of the allowed length and fails if a file
# did not make it. A file that is too long does not always fail the git command, so the check is git status. Run from the repo.
$ErrorActionPreference = 'Continue'
$repo = git rev-parse --show-toplevel
$allowance = [int](python -B -c "import sys; sys.path.insert(0, sys.argv[1]); import check_path_lengths; print(check_path_lengths.ROOT_ALLOWANCE)" "$repo/tools")
$temp = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { $env:TEMP }
$root = "$temp\" + ('x' * ($allowance - $temp.Length - 2))

git clone --quiet -c core.longpaths=false -c core.autocrlf=false $repo $root
$clone = $LASTEXITCODE
$tracked = @(git -C $root ls-files).Count
$broken = @(git -C $root status --porcelain)
Set-Location $temp
cmd /c rd /s /q $root

"Root of $($root.Length + 1) characters, $tracked tracked files, $($broken.Count) not checked out, git clone exit $clone."
$broken | Select-Object -First 20
if ($clone -ne 0 -or $broken.Count -ne 0 -or $tracked -eq 0) { exit 1 }
exit 0
