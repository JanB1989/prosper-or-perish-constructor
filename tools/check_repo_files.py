#!/usr/bin/env python3
"""Check tracked files for what breaks a clone: GitHub's file size warning, temp junk, names Windows cannot check out.

Path lengths have their own check (check_path_lengths.py).
"""

from __future__ import annotations

import collections
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


# GitHub warns on push above 50 MB (GH001 "Large files detected") and rejects files above 100 MB.
MAX_FILE_BYTES = 50_000_000
# Scratch folders and files: local work only, never tracked (also in .gitignore).
TEMP_DIRS = ("tmp", ".tmp", "__pycache__")
TEMP_NAME = re.compile(r"^(tmp_.*|.*\.(tmp|bak|orig|rej|swp|log|pyc)|.*~|\.DS_Store|Thumbs\.db|desktop\.ini)$", re.IGNORECASE)
# Windows: reserved device names (with any extension), forbidden characters, trailing dot or space.
RESERVED = re.compile(r"^(con|prn|aux|nul|com[0-9]|lpt[0-9])(\..*)?$", re.IGNORECASE)
FORBIDDEN = re.compile(r'[<>:"|?*\\\x00-\x1f]')


@dataclass(frozen=True)
class FileIssue:
    path: str
    kind: str
    detail: str


def tracked_files(repo: Path) -> list[tuple[str, int]]:
    """Tracked paths with their size in the working tree (the index entry's size when the file is missing)."""
    out = subprocess.run(["git", "ls-files", "-z", "--cached", "--stage"], cwd=repo, check=True, stdout=subprocess.PIPE).stdout
    files: list[tuple[str, int]] = []
    for record in out.split(b"\0"):
        if not record:
            continue
        meta, raw = record.split(b"\t", 1)
        if meta.startswith(b"160000"):   # submodule
            continue
        path = raw.decode("utf-8", errors="surrogateescape")
        target = repo / path
        files.append((path, target.stat().st_size if target.is_file() else 0))
    return files


def check_files(files: list[tuple[str, int]], max_file_bytes: int = MAX_FILE_BYTES) -> list[FileIssue]:
    issues: list[FileIssue] = []
    folded: dict[str, set[str]] = collections.defaultdict(set)
    for path, size in files:
        parts = path.split("/")
        if size > max_file_bytes:
            issues.append(FileIssue(path, "size", f"{size / 1e6:.1f} MB > {max_file_bytes / 1e6:.0f} MB"))
        if any(part in TEMP_DIRS for part in parts[:-1]) or TEMP_NAME.match(parts[-1]):
            issues.append(FileIssue(path, "temp", "scratch file or folder"))
        for part in parts:
            if RESERVED.match(part):
                issues.append(FileIssue(path, "windows", f"reserved name {part!r}"))
            elif FORBIDDEN.search(part):
                issues.append(FileIssue(path, "windows", f"forbidden character in {part!r}"))
            elif part.endswith((".", " ")):
                issues.append(FileIssue(path, "windows", f"trailing dot or space in {part!r}"))
        for depth in range(1, len(parts) + 1):
            prefix = "/".join(parts[:depth])
            folded[prefix.lower()].add(prefix)
    for variants in folded.values():
        if len(variants) > 1:
            issues.append(FileIssue(sorted(variants)[0], "windows", "differs only in case from " + ", ".join(sorted(variants)[1:])))
    return sorted(issues, key=lambda issue: (issue.kind, issue.path))


def main() -> int:
    repo = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], check=True, stdout=subprocess.PIPE, text=True).stdout.strip())
    issues = check_files(tracked_files(repo))
    if not issues:
        return 0
    print("Tracked files that break a clone (size: publish smaller or keep untracked; temp: untrack and ignore; "
          "windows: rename):", file=sys.stderr)
    for issue in issues:
        print(f"  {issue.kind:<7} {issue.detail}: {issue.path}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
