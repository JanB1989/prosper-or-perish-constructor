"""Location Profiles (script side: storage, edits, assignment, the monthly pass). Contract: docs/location_profiles.md."""

from __future__ import annotations

from pathlib import Path


def apply(repo: Path, project: Path, mod_root: Path, vanilla_root: Path, write: bool = True) -> int:
    """Writes the generated files; returns how many changed."""
    return 0
