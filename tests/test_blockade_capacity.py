"""Blockade capacity x10 for every non-levy ship (src/prosper_or_perish_constructor/blockade_capacity.py)."""

from __future__ import annotations

from pathlib import Path

import pytest

from prosper_or_perish_constructor import blockade_capacity

REPO = Path(__file__).resolve().parents[1]
PROJECT = REPO / "constructor.toml"


@pytest.fixture(scope="module")
def ships() -> list[blockade_capacity.Ship]:
    return blockade_capacity.plan(REPO, PROJECT)


def test_unit_type_file_is_current() -> None:
    _, changed = blockade_capacity.apply(REPO, PROJECT, write=False)
    assert not changed, "run uv run ppc blockade apply"


def test_non_levy_ships_scaled_levy_ships_kept(ships: list[blockade_capacity.Ship]) -> None:
    scale = blockade_capacity.factor(PROJECT)
    assert len(ships) > 30
    by_unit = {s.unit: s for s in ships}
    assert by_unit["n_age_1_traditions_galley"].new == pytest.approx(0.1 * scale)
    assert by_unit["n_traditional_galley"].new == pytest.approx(0.1 * scale)  # copy_from resolved
    assert not [s.unit for s in ships if not s.levy and s.new != pytest.approx(s.vanilla * scale)]
    assert not [s.unit for s in ships if s.levy and s.new != s.vanilla]
