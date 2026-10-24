"""The Cookshop cap counts whole building levels (food_level_counts.py, 2026-10-24).

The engine scales raw_modifier by input fulfilment, so the level counters the farms and Yards carry read under a level
whenever an input is short; the cap then floored below the kitchens the start setup placed at it.
"""

from __future__ import annotations

from pathlib import Path

from prosper_or_perish_constructor import food_level_counts

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"


def test_generated_counts_are_current_and_cover_every_counter_building():
    found = food_level_counts.counters(MOD_ROOT)
    text, counted = food_level_counts.render(found)
    assert (MOD_ROOT / food_level_counts.OUTPUT).read_text(encoding="utf-8") == text
    assert counted["pp_location_farm_building_levels"] >= 40
    assert counted["pp_location_victualling_yard_building_levels"] >= 1
    for key in found:
        assert f"has_building = building_type:{key} }}" in text


def test_province_sums_read_whole_levels_never_the_scaled_counters():
    values = (MOD_ROOT / "in_game/common/script_values/pp_food_building_values.txt").read_text(encoding="utf-8-sig")
    for name in ("pp_province_farm_levels", "pp_province_victualling_yard_levels"):
        block = values[values.index(f"{name} = {{"):]
        block = block[:block.index("\n}\n")]
        assert "modifier:" not in block, name
        assert "_building_levels" in block, name


def test_render_weights_and_skips(tmp_path: Path):
    text, counted = food_level_counts.render({
        "a_farm": {"local_pp_farm_levels": 1.0},
        "b_flock": {"local_pp_staple_levels": 2.0},
        "c_yard": {"local_pp_victualling_yard_levels": 1.0},
    })
    assert counted == {"pp_location_farm_building_levels": 2, "pp_location_victualling_yard_building_levels": 1}
    assert 'add = "location_building_level(building_type:a_farm)"' in text
    assert 'add = { value = "location_building_level(building_type:b_flock)" multiply = 2 }' in text
    farm = text[text.index("pp_location_farm_building_levels"):text.index("pp_location_victualling_yard_building_levels")]
    assert "c_yard" not in farm
