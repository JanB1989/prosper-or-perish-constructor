"""The shipped map csv files (World Builder geography export) must have only well-formed rows.

The engine reads every line of `in_game/map_data/adjacencies.csv` and `ports.csv` as a row; a trailing newline or a
blank line becomes a row for location " " ("Unknown reference to location! Key: ' ', File Location:
'map_data/adjacencies.csv(998)'", EU5 1.4). Vanilla's files end without a newline.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

from prosper_or_perish_constructor.worldbuilder import spline_network as sn

REPO = Path(__file__).resolve().parents[1]
MAP_DATA = REPO / "mod/Prosper or Perish (Population Growth & Food Rework)/in_game/map_data"
# file -> (header, fields per row)
FILES = {
    "adjacencies.csv": ("From;To;Type;Through;start_x;start_y;stop_x;stop_y;Comment", 9),
    "ports.csv": ("LandProvince;SeaZone;x;y;", 5),
}
INTEGER = re.compile(r"-?\d+")


@pytest.fixture(scope="module")
def locations():
    if not (MAP_DATA / "definitions.txt").is_file():
        pytest.skip("mod not built")
    return set(sn.location_order(MAP_DATA / "definitions.txt"))


def _lines(name):
    path = MAP_DATA / name
    if not path.is_file():
        pytest.skip(f"{name} not shipped")
    return path.read_text(encoding="utf-8-sig").split("\n")


@pytest.mark.parametrize("name", sorted(FILES))
def test_map_csv_has_no_empty_or_malformed_rows(name, locations):
    header, width = FILES[name]
    lines = _lines(name)
    assert lines[0].rstrip("\r") == header
    problems = []
    for number, line in enumerate(lines[1:], 2):
        fields = line.rstrip("\r").split(";")
        if not line.strip():
            problems.append((number, "empty row (a trailing newline counts)"))
        elif len(fields) != width:
            problems.append((number, f"{len(fields)} fields"))
        elif not all(INTEGER.fullmatch(v) for v in (fields[4:8] if name == "adjacencies.csv" else fields[2:4])):
            problems.append((number, "coordinates are not integers"))
        else:
            named = fields[:2] + ([fields[3]] if name == "adjacencies.csv" and fields[2] == "sea" else [])
            unknown = [v for v in named if v not in locations]
            if unknown:
                problems.append((number, f"unknown locations {unknown}"))
    assert problems == []


def test_adjacency_types_and_one_port_per_location(locations):
    adjacencies = [line.split(";") for line in _lines("adjacencies.csv")[1:]]
    assert {row[2] for row in adjacencies} <= {"sea", "canal"}
    ports = Counter(line.split(";")[0] for line in _lines("ports.csv")[1:])
    assert sorted(p for p, n in ports.items() if n > 1) == []
