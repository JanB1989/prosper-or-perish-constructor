"""Ship upkeep = the value of its maintenance goods (src/prosper_or_perish_constructor/ship_upkeep.py)."""

from __future__ import annotations

from pathlib import Path

import pytest

from prosper_or_perish_constructor import ship_upkeep

REPO = Path(__file__).resolve().parents[1]
PROJECT = REPO / "constructor.toml"
MOD = REPO / "mod" / ship_upkeep.MOD_FOLDER


@pytest.fixture(scope="module")
def ships() -> list[ship_upkeep.Ship]:
    return ship_upkeep.plan(REPO, PROJECT)


def test_price_file_is_current() -> None:
    _, changed = ship_upkeep.apply(REPO, PROJECT, write=False)
    assert not changed, "run uv run ppc ship-upkeep apply"


def test_every_new_price_has_modifier_type_icon_and_name(ships: list[ship_upkeep.Ship]) -> None:
    """The engine logs "Missing modifier type for price" and a missing price name for every price without them."""
    import re

    prices = re.findall(r"(?m)^(n_\w+_maintenance) = \{", (MOD / ship_upkeep.OUTPUT).read_text(encoding="utf-8-sig"))
    assert len(prices) == sum(1 for s in ships if s.vanilla_entry is None) > 50
    types = (MOD / ship_upkeep.MODIFIER_TYPES).read_text(encoding="utf-8-sig")
    icons = (MOD / ship_upkeep.MODIFIER_ICONS).read_text(encoding="utf-8-sig")
    loc = (MOD / ship_upkeep.LOCALIZATION).read_text(encoding="utf-8-sig")
    assert loc.startswith("l_english:")
    for price in prices:
        unit = price.removesuffix("_maintenance")
        assert re.search(rf"(?m)^{price}_cost_modifier=\{{", types), price
        assert re.search(rf"(?m)^{price}_cost_modifier = \{{", icons), price
        assert f'  {price}: "${unit}$ Maintenance Cost"' in loc, price
        assert f"MODIFIER_TYPE_NAME_{price}_cost_modifier:" in loc and f"MODIFIER_TYPE_DESC_{price}_cost_modifier:" in loc
    # vanilla already defines type, icon and name for the prices it has itself
    assert "n_panokseon" not in types + icons + loc
    text = re.sub(r"\$[^$]*\$|\[[^\]]*\]", "", "".join(re.findall(r'"([^"]*)"', loc)))
    assert not re.search(r"\d", text)  # player-facing text carries no numbers


def test_every_ship_costs_its_goods(ships: list[ship_upkeep.Ship]) -> None:
    assert len(ships) > 50
    off = [(s.unit, round(s.new_base, 3), round(s.basket_value, 3)) for s in ships if abs(s.new_base - s.basket_value) > 0.001]
    assert not off


def test_late_ships_no_longer_cost_the_age_doubling(ships: list[ship_upkeep.Ship]) -> None:
    by_unit = {s.unit: s for s in ships}
    assert by_unit["n_threedecker"].old_base == pytest.approx(32)
    assert 9 < by_unit["n_threedecker"].new_base < 14
    assert by_unit["n_brig"].new_base < by_unit["n_brig"].old_base


def test_age_doubling_define_left_at_vanilla() -> None:
    defines = MOD / "loading_screen" / "common" / "defines"
    for path in defines.glob("*.txt"):
        assert "BASE_SCALE_SHIP_DOUBLE_PER_AGE" not in path.read_text(encoding="utf-8-sig"), path.name
