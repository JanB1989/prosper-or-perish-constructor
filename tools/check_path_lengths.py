#!/usr/bin/env python3
"""Check tracked repository paths against a conservative Windows path budget."""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


MAX_RELATIVE_PATH = 140
MAX_COMPONENT = 100
ENGINE_REQUIRED_PATH_LIMITS = {
    (
        "mod/Prosper or Perish (Population Growth & Food Rework)/main_menu/gfx/interface/"
        "icons/trade_goods/illustrations/icon_goods_manual_labor_cost.dds"
    ): 150,
    (
        "mod/Prosper or Perish (Population Growth & Food Rework)/main_menu/gfx/interface/"
        "icons/trade_goods/illustrations/icon_goods_province_food_purchase.dds"
    ): 150,
    (
        "mod/Prosper or Perish (Population Growth & Food Rework)/main_menu/gfx/interface/"
        "icons/trade_goods/illustrations/icon_goods_province_food_sales.dds"
    ): 150,
}


@dataclass(frozen=True)
class PathLengthIssue:
    path: str
    kind: str
    length: int
    limit: int


def tracked_paths(repo: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files", "-z", "--cached"],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
    )
    paths: list[str] = []
    for item in completed.stdout.split(b"\0"):
        if not item:
            continue
        path = item.decode("utf-8", errors="surrogateescape").replace("\\", "/")
        if (repo / path).exists():
            paths.append(path)
    return paths


def check_paths(
    paths: list[str],
    *,
    max_relative_path: int = MAX_RELATIVE_PATH,
    max_component: int = MAX_COMPONENT,
) -> list[PathLengthIssue]:
    issues: list[PathLengthIssue] = []
    for path in paths:
        path_limit = ENGINE_REQUIRED_PATH_LIMITS.get(path, max_relative_path)
        if len(path) > path_limit:
            issues.append(PathLengthIssue(path, "path", len(path), path_limit))
        longest_component = max((len(part) for part in path.split("/")), default=0)
        if longest_component > max_component:
            issues.append(PathLengthIssue(path, "component", longest_component, max_component))
    return sorted(issues, key=lambda issue: (issue.length, issue.path), reverse=True)


def repo_root() -> Path:
    completed = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    return Path(completed.stdout.strip())


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-relative-path", type=int, default=MAX_RELATIVE_PATH)
    parser.add_argument("--max-component", type=int, default=MAX_COMPONENT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(argv or ()))
    repo = repo_root()
    issues = check_paths(
        tracked_paths(repo),
        max_relative_path=args.max_relative_path,
        max_component=args.max_component,
    )
    if not issues:
        return 0

    print(
        "Tracked paths exceed the Windows path budget "
        f"(path <= {args.max_relative_path}, component <= {args.max_component}):",
        file=sys.stderr,
    )
    for issue in issues:
        label = "relative path" if issue.kind == "path" else "path component"
        print(f"  {issue.length:>3} > {issue.limit:<3} {label}: {issue.path}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
