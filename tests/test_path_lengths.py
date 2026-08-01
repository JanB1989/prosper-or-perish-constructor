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
    issues = check_path_lengths.check_paths(
        check_path_lengths.tracked_paths(ROOT),
        max_relative_path=check_path_lengths.MAX_RELATIVE_PATH,
        max_component=check_path_lengths.MAX_COMPONENT,
    )

    assert not issues, "\n".join(
        f"{issue.length} > {issue.limit} {issue.kind}: {issue.path}" for issue in issues
    )


def test_path_budget_exceptions_are_limited_to_engine_required_trade_good_illustrations() -> None:
    assert len(check_path_lengths.ENGINE_REQUIRED_PATH_LIMITS) == 3
    assert all(
        path.endswith(".dds") and "/trade_goods/illustrations/icon_goods_" in path
        for path in check_path_lengths.ENGINE_REQUIRED_PATH_LIMITS
    )
    assert check_path_lengths.check_paths(
        list(check_path_lengths.ENGINE_REQUIRED_PATH_LIMITS),
        max_relative_path=check_path_lengths.MAX_RELATIVE_PATH,
        max_component=check_path_lengths.MAX_COMPONENT,
    ) == []
