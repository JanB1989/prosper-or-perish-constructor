#!/usr/bin/env python3
"""Check tracked repository paths against the Windows path limits, with room for the folder the repo sits in.

Measured with Git for Windows 2.49, long paths off (its default), 2026-11-02: a file path of 259 characters checks out, 260
fails with "Filename too long"; a folder path of 247 works, 248 fails. There are no exceptions: a file that does not fit gets
a shorter name or folder. tools/check_windows_clone.ps1 proves the same on real Windows.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


WINDOWS_MAX_FILE_PATH = 259
WINDOWS_MAX_FOLDER_PATH = 247
# The folder the repo sits in, last backslash included. The worst case we plan for is 127 characters, a GitHub ZIP unpacked by
# Explorer (it doubles the folder) under a long user name and OneDrive:
# C:\Users\firstname.lastname\OneDrive - Company\Downloads\prosper-or-perish-constructor-main\prosper-or-perish-constructor-main\
ROOT_ALLOWANCE = 150
MAX_RELATIVE_PATH = WINDOWS_MAX_FILE_PATH - ROOT_ALLOWANCE
MAX_RELATIVE_FOLDER = WINDOWS_MAX_FOLDER_PATH - ROOT_ALLOWANCE
MAX_COMPONENT = 100
LABELS = {"path": "relative path", "folder": "folder", "component": "path component"}


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
    max_relative_folder: int = MAX_RELATIVE_FOLDER,
    max_component: int = MAX_COMPONENT,
) -> list[PathLengthIssue]:
    issues: list[PathLengthIssue] = []
    for path in paths:
        if len(path) > max_relative_path:
            issues.append(PathLengthIssue(path, "path", len(path), max_relative_path))
        folder = path.rpartition("/")[0]
        if len(folder) > max_relative_folder:
            issues.append(PathLengthIssue(path, "folder", len(folder), max_relative_folder))
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
    parser.add_argument("--max-relative-folder", type=int, default=MAX_RELATIVE_FOLDER)
    parser.add_argument("--max-component", type=int, default=MAX_COMPONENT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(argv or ()))
    repo = repo_root()
    issues = check_paths(
        tracked_paths(repo),
        max_relative_path=args.max_relative_path,
        max_relative_folder=args.max_relative_folder,
        max_component=args.max_component,
    )
    if not issues:
        return 0

    print(
        "Tracked paths exceed the Windows path budget, shorten them "
        f"(path <= {args.max_relative_path}, folder <= {args.max_relative_folder}, component <= {args.max_component}):",
        file=sys.stderr,
    )
    for issue in issues:
        print(f"  {issue.length:>3} > {issue.limit:<3} {LABELS[issue.kind]}: {issue.path}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
