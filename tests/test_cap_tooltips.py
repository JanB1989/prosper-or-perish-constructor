"""Building max-level tooltips (cap_tooltips.py): every term is one clean, labelled row; numbers never change.

In game (2026-10-03) every step of a described script-value row is drawn as its own row ("missing key" without a
desc), and a script value read through ``this.`` is one number. These tests keep every cap of the load order clean.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from eu5gameparser.clausewitz.parser import parse_text

from prosper_or_perish_constructor import cap_tooltips
from prosper_or_perish_constructor.rural_capacity import LAND_FARM_BUILDINGS

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
FARMING = MOD_ROOT / "in_game/common/script_values/pp_farming_capacity.txt"
LOCALIZATION = MOD_ROOT / "main_menu/localization/english"


@pytest.fixture(scope="module")
def vanilla() -> Path:
    from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

    root = cap_tooltips.game_root(vanilla_root(ROOT, ROOT / "constructor.toml"))
    if not (root / "in_game/common/script_values").is_dir():
        pytest.skip("no vanilla game files")
    return root


def test_every_max_level_tooltip_row_is_one_labelled_number(vanilla: Path) -> None:
    problems = cap_tooltips.problems([vanilla, MOD_ROOT])
    assert [str(p) for p in problems] == []


def test_the_generated_caps_are_current(vanilla: Path) -> None:
    assert cap_tooltips.apply(MOD_ROOT, vanilla, write=False).changed == ()


def test_fix_keeps_the_label_and_moves_the_steps_into_a_helper() -> None:
    values = {"other_cap": None}
    text = (
        "my_cap = {\n"
        "\tadd = {\n\t\tdesc = \"BUILDING_LEVEL_BASE\"\n\t\tvalue = 1\n\t}\n"
        "\tadd = {\n\t\tdesc = \"BUILDING_LEVEL_DEVELOPMENT\"\n\t\tvalue = development\n\t\tmultiply = 0.2\n\t}\n"
        "\tif = {\n\t\tlimit = { is_coastal = yes }\n"
        "\t\tadd = { desc = X_HARBOR value = modifier:harbor max = 3 multiply = 2 }\n\t}\n"
        "\tmin = { desc = \"BUILDING_LEVEL_WB_MINIMUM\" value = 0 }\n"
        "}\n"
    )
    script_values = {name: (None, "") for name in values}
    fixed, rows = cap_tooltips.fix_text(text, {"my_cap"}, script_values)
    assert rows == 2
    document = {e.key: e.value for e in parse_text(fixed).entries}
    assert set(document) == {"my_cap", "my_cap_building_level_development", "my_cap_x_harbor"}
    assert 'desc = "BUILDING_LEVEL_DEVELOPMENT"\n\t\tvalue = this.my_cap_building_level_development' in fixed
    assert "my_cap_building_level_development = {\n\tvalue = development\n\tmultiply = 0.2\n}" in fixed
    assert "my_cap_x_harbor = {\n\tvalue = modifier:harbor max = 3 multiply = 2\n}" in fixed
    # clean rows stay as they are, and a second pass changes nothing
    assert 'desc = "BUILDING_LEVEL_BASE"\n\t\tvalue = 1' in fixed
    assert cap_tooltips.fix_text(fixed, {"my_cap"}, script_values) == (fixed, 0)


def test_farm_max_levels_read_in_levels_of_the_farm() -> None:
    text = FARMING.read_text(encoding="utf-8-sig")
    for building in LAND_FARM_BUILDINGS:
        block = re.search(rf"(?ms)^farm_capacity_max_{building} = \{{\n(.*?)^\}}", text).group(1)
        rows = re.findall(r"^\t(\w+) = \{ desc = \"(\w+)\" value = this\.(\w+) \}$", block, flags=re.M)
        assert [(op, desc) for op, desc, _ in rows] == [
            ("add", "PP_BUILDING_LEVEL_FARMLAND"), ("subtract", "PP_BUILDING_LEVEL_FARMLAND_OTHER_FARMS")
        ], building
        farmland, others = rows[0][2], rows[1][2]
        # Farmland = floor((flat - reserve) / land) + all farms' land / land; Used by other farms = that land / land
        # less this farm's (and its replaceable tiers') own levels: the difference is the old cap exactly
        land = re.search(rf"(?ms)^{farmland} = \{{.*?divide = ([\d.]+)\n.*?floor = yes", text).group(1)
        assert re.search(rf"(?ms)^{farmland} = \{{.*?add = \{{ value = modifier:local_pp_farmland_used divide = {land} \}}", text)
        other = re.search(rf"(?ms)^{others} = \{{\n(.*?)^\}}", text).group(1)
        assert f"value = modifier:local_pp_farmland_used\n\tdivide = {land}" in other
        assert f"add = modifier:farm_capacity_from_{building}" in other


def test_every_land_farm_records_the_land_it_uses() -> None:
    root = MOD_ROOT / "in_game/common/building_types"
    found = {}
    for path in root.glob("*.txt"):
        for block in re.findall(r"raw_modifier = \{([^}]*)\}", path.read_text(encoding="utf-8-sig")):
            counter = re.search(r"farm_capacity_from_(\w+) = -1", block)
            land = re.search(r"local_population_capacity = (-[\d.]+)", block)
            if counter and land:
                used = re.search(r"local_pp_farmland_used = ([\d.]+)", block)
                assert used and float(used.group(1)) == -float(land.group(1)), (path.name, counter.group(1))
                found[counter.group(1)] = True
    assert {b for b in LAND_FARM_BUILDINGS if b in found} == set(found)
    assert len(found) >= 60


def test_farm_cap_rows_link_arable_land() -> None:
    """The farm max-level rows speak of Arable Land (the population capacity, renamed 2026-10-10; the Farmland concept
    is gone): the row label links the vanilla concept, which reads "Arable Land"."""
    text = "".join(p.read_text(encoding="utf-8-sig") for p in LOCALIZATION.glob("*.yml"))
    for key in ("PP_BUILDING_LEVEL_FARMLAND", "PP_BUILDING_LEVEL_FARMLAND_OTHER_FARMS", "MODIFIER_TYPE_NAME_local_pp_farmland_used"):
        assert f"\n  {key}:" in text, key
    assert "[population_capacity|e]" in re.search(r'PP_BUILDING_LEVEL_FARMLAND: "([^"]*)"', text).group(1)
    assert re.search(r'game_concept_population_capacity: "Arable Land"', text)
    assert not (MOD_ROOT / "main_menu/common/game_concepts/pp_farmland.txt").exists()
