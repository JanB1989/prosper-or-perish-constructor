from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "research/population_capacity/crosswalks/fanta_2018_validation_points.csv"
MANIFEST_PATH = ROOT / "research/population_capacity/crosswalks/fanta_2018_validation_points.json"


def test_fanta_validation_crosswalk_is_explicitly_non_training() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["record_count"] == 88
    assert manifest["role"] == "validation_only"
    assert manifest["training_eligible"] is False
    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8", newline="")))
    assert len(rows) == manifest["record_count"]
    assert {row["mapping_status"] for row in rows} == {"nearest_point_diagnostic"}
    assert {row["training_eligible"] for row in rows} == {"False"}
    assert all(float(row["eu5_centroid_distance_km"]) >= 0 for row in rows)
