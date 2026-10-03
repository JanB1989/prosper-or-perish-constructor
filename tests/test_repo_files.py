from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECK_REPO_FILES = ROOT / "tools" / "check_repo_files.py"

spec = importlib.util.spec_from_file_location("check_repo_files", CHECK_REPO_FILES)
assert spec is not None
check_repo_files = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = check_repo_files
spec.loader.exec_module(check_repo_files)


def test_tracked_files_clone_cleanly() -> None:
    # 2026-10-03: no file over GitHub's 50 MB warning, no scratch files, no names Windows cannot check out
    issues = check_repo_files.check_files(check_repo_files.tracked_files(ROOT))

    assert not issues, "\n".join(f"{issue.kind} {issue.detail}: {issue.path}" for issue in issues)


def test_check_flags_size_temp_and_windows_names() -> None:
    files = [
        ("docs/examples/savegame_explorer.html", 82_000_000),
        ("tmp/china_start_before.csv", 10),
        ("tmp_raw_material_base_pm_coverage.py", 10),
        ("scripts/run.log", 10),
        ("src/pkg/__pycache__/x.cpython-314.pyc", 10),
        ("docs/nul", 0),
        ("docs/aux.txt", 0),
        ("docs/what?.md", 0),
        ("docs/trailing. ", 0),
        ("docs/Readme.md", 0),
        ("docs/README.md", 0),
        ("Assets/a.png", 0),
        ("assets/b.png", 0),
    ]
    kinds = {(issue.kind, issue.path) for issue in check_repo_files.check_files(files)}

    assert ("size", "docs/examples/savegame_explorer.html") in kinds
    for path in ("tmp/china_start_before.csv", "tmp_raw_material_base_pm_coverage.py", "scripts/run.log",
                 "src/pkg/__pycache__/x.cpython-314.pyc"):
        assert ("temp", path) in kinds
    for path in ("docs/nul", "docs/aux.txt", "docs/what?.md", "docs/trailing. ", "Assets"):
        assert ("windows", path) in kinds
    assert ("windows", "docs/README.md") in kinds   # case-only twins: the first in sort order is named
    # ordinary files pass, including names that merely start with "temp" and setup templates
    ok = [("blueprints/accepted/buildings/temple.yml", 10), ("mod/x/main_menu/setup/templates/expl_china.txt", 10),
          ("docs/examples/savegame_explorer.html", 6_500_000), ("assets/icon_references/fish.png", 400_000)]
    assert check_repo_files.check_files(ok) == []
