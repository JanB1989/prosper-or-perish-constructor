from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECK_PATH_LENGTHS = ROOT / "tools" / "check_path_lengths.py"

spec = importlib.util.spec_from_file_location("check_path_lengths", CHECK_PATH_LENGTHS)
assert spec is not None
check_path_lengths = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = check_path_lengths
spec.loader.exec_module(check_path_lengths)


def test_tracked_paths_fit_windows_path_budget() -> None:
    issues = check_path_lengths.check_paths(check_path_lengths.tracked_paths(ROOT))

    assert not issues, "\n".join(
        f"{issue.length} > {issue.limit} {issue.kind}: {issue.path}" for issue in issues
    )


def test_budget_leaves_room_for_the_worst_folder_people_put_the_repo_in() -> None:
    # 2026-11-02: a GitHub ZIP unpacked by Explorer (doubled folder) under a long user name and OneDrive
    root = "C:\\Users\\firstname.lastname\\OneDrive - Company\\Downloads\\" + "prosper-or-perish-constructor-main\\" * 2
    assert len(root) <= check_path_lengths.ROOT_ALLOWANCE
    assert check_path_lengths.ROOT_ALLOWANCE + check_path_lengths.MAX_RELATIVE_PATH <= 259
    assert check_path_lengths.ROOT_ALLOWANCE + check_path_lengths.MAX_RELATIVE_FOLDER <= 247


def test_check_flags_paths_and_folders_over_the_budget_without_exceptions() -> None:
    limit, folder_limit = check_path_lengths.MAX_RELATIVE_PATH, check_path_lengths.MAX_RELATIVE_FOLDER
    at_limit = "a" * 50 + "/" + "b" * (limit - 51)
    deep = "a" * 50 + "/" + "b" * (folder_limit - 50) + "/f"

    assert check_path_lengths.check_paths([at_limit]) == []
    assert [issue.kind for issue in check_path_lengths.check_paths([at_limit + "c"])] == ["path"]
    assert [issue.kind for issue in check_path_lengths.check_paths([deep])] == ["folder"]
    assert [issue.kind for issue in check_path_lengths.check_paths(["c" * (check_path_lengths.MAX_COMPONENT + 1)])] == ["component"]
