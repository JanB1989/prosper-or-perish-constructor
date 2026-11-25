#!/usr/bin/env python3
"""Write the placeholder country table of the starting technology ladder (2026-11-25).

`config/starting_technology_countries.csv` gets one row per country block of the effective 1337 `10_countries.txt`,
the group taken from the country's vanilla effective level (0 -> 1, 1 -> 2, 2 -> 5, 3 -> 9), basis "placeholder from
the vanilla level". The researched table replaces it; this only keeps the build working until then.

    uv run python tools/start_technology_placeholder.py
"""

from __future__ import annotations

from pathlib import Path

from prosper_or_perish_constructor import start_technology
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

REPO = Path(__file__).resolve().parents[1]


def main() -> int:
    rows = start_technology.write_placeholder_countries(
        REPO, vanilla_root(REPO, REPO / "constructor.toml"), REPO / "mod" / start_technology.MOD_FOLDER
    )
    print(f"{start_technology.COUNTRIES_CSV}: {rows} placeholder rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
