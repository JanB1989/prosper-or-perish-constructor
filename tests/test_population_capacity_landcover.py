from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
import pytest

from prosper_or_perish_constructor import cli
from prosper_or_perish_constructor.population_capacity_landcover import (
    _placed_forest_fraction,
    audit_landcover_capacity_artifact,
)


def test_pnv_forest_placement_conserves_each_luh2_cell() -> None:
    potential = np.array(
        [
            [1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ]
    )
    historical = np.array([[0.2], [0.7]])
    coarse_potential = np.full((2, 1), 1.0 / 3.0)

    placed = _placed_forest_fraction(
        historical,
        potential,
        coarse_potential,
    )

    assert placed.mean(axis=1) == pytest.approx([0.2, 0.7])
    assert np.all((placed >= 0.0) & (placed <= 1.0))


def test_landcover_audit_checks_allocation_and_monotone_bands(tmp_path: Path) -> None:
    artifact = tmp_path / "landcover.parquet"
    data: dict[str, object] = {
        "location_tag": ["alpha", "beta"],
        "forest_fraction_1300": [0.4, 0.1],
        "potential_forest_fraction": [0.8, 0.2],
        "allocated_woodland_fraction": [0.4, 0.1],
        "forest_crop_suitability_share": [0.5, 0.1],
        "open_crop_suitability_share": [0.5, 0.9],
        "landcover_coverage_fraction": [1.0, 1.0],
        "land_allocation_sum_1300": [1.0, 0.95],
        "landcover_year": [1300, 1300],
        "landcover_source_hash": ["a" * 64, "a" * 64],
        "landcover_status": ["complete", "complete"],
    }
    for stem in (
        "open_rainfed_capacity_people",
        "extensive_livestock_capacity_people",
        "retained_wild_capacity_people",
        "clearing_increment_capacity_people",
        "clearing_gross_crop_capacity_people",
        "clearing_displaced_wild_capacity_people",
        "clearing_displaced_livestock_capacity_people",
    ):
        data[f"{stem}_p10"] = [1.0, 2.0]
        data[f"{stem}_p50"] = [2.0, 3.0]
        data[f"{stem}_p90"] = [3.0, 4.0]
    pl.DataFrame(data).write_parquet(artifact)

    result = audit_landcover_capacity_artifact(
        artifact_path=artifact,
        expected_locations=2,
    )

    assert result["passed"] is True
    assert result["landcover_year"] == 1300
    assert result["complete_coverage_locations"] == 2
    assert result["max_land_allocation_overflow"] == pytest.approx(0.0)


@pytest.mark.parametrize(
    ("command", "handler"),
    (
        ("fetch-landcover-sources", cli._population_capacity_fetch_landcover_sources),
        ("build-landcover", cli._population_capacity_build_landcover),
        ("landcover-audit", cli._population_capacity_landcover_audit),
    ),
)
def test_landcover_commands_are_registered(command: str, handler) -> None:
    args, extra = cli._build_parser().parse_known_args(
        ["population-capacity", command]
    )

    assert extra == []
    assert args.population_capacity_command == command
    assert args.handler is handler
