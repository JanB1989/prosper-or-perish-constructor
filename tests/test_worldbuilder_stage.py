"""Unit tests for the World Builder handover stage (no game files needed)."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from prosper_or_perish_constructor.location_baseline import apply_location_template_overlay, parse_location_templates_text
from prosper_or_perish_constructor.worldbuilder import buildings as wb_buildings
from prosper_or_perish_constructor.worldbuilder import modifiers as wb_modifiers
from prosper_or_perish_constructor.worldbuilder.contract import Contract, units


def _contract(tmp_path: Path) -> Contract:
    meta = {"schema_version": "1.0", "version": "test", "attributes": {"features": ["climate", "fertility"], "reference_classes": {"climate": "continental", "fertility": "moderate"}, "capacity_percent_per_point": 0.01}}
    rows = pl.DataFrame({
        "attribute": ["reference", "climate", "fertility"], "value": ["intercept", "arid", "high"], "capacity_people": [20000.0, -9000.0, 2400.0],
        "game_key": ["", "arid", "ha1300_fertility_is_high"], "output_wheat": [0.05, -0.2, 0.12], "output_incense": [-0.1, 0.4, None],
    })
    types = pl.DataFrame({"building": ["clearing"], "unit_people_per_level": [5200.0], "level_limit": [20], "gate_json": ['[{"climate": ["arid", "continental"]}]'],
                          "cap_equation_json": [json.dumps({"base_levels": 2, "levels_per_development_point": 0.03, "class_terms": [{"attribute": "climate", "value": "arid", "levels": 1}, {"attribute": "fertility", "value": "high", "levels": 2}]})]})
    lb = pl.DataFrame({"location_tag": ["a", "b"], "building": ["clearing", "clearing"], "starting_levels": [3, 0], "cap_at_start": [3, 1], "cap_at_reference_development": [4, 2]})
    lt = pl.DataFrame({"location_tag": ["a", "b"], "attribute_flat_people": [11000.0, 22400.0], "starting_target_people": [30000.0, 25000.0], "maximum_target_people": [40000.0, 30000.0], "development": [20.0, 40.0]})
    la = pl.DataFrame({"location_tag": ["a", "b"], "climate": ["arid", "continental"], "fertility": ["moderate", "high"]})
    floors = pl.DataFrame({"location_tag": ["a"], "good": ["incense"], "predicted": [-0.4], "target": [None], "reason": ["predicted below floor -0.2"]})
    return Contract(root=tmp_path, meta=meta, attribute_rows=rows, building_types=types, location_buildings=lb, location_targets=lt, location_attributes=la, goods_floor=floors)


def test_units_and_class_rows_fold_capacity_intercept_into_climate_only(tmp_path):
    c = _contract(tmp_path)
    assert units(5200) == 5.2
    rows = wb_modifiers.class_rows(c)
    assert rows[("climate", "arid")]["local_population_capacity"] == units(20000 - 9000)
    assert rows[("climate", "arid")]["local_wheat_output_modifier"] == -0.2       # no goods intercept on the class
    assert rows[("climate", "continental")]["local_population_capacity"] == 20.0  # reference class carries the intercept
    assert rows[("fertility", "high")] == {"local_population_capacity": 2.4, "local_wheat_output_modifier": 0.12}
    assert wb_modifiers.goods_intercepts(c) == {"wheat": 0.05, "incense": -0.1}


def test_parse_class_capacity_reads_vanilla_values_and_legacy_effects(tmp_path):
    defs = tmp_path / "00_default.txt"
    defs.write_text("arid = {\n\tcolor = x\n\tlocation_modifier = {\n\t\tlocal_population_capacity_modifier = 0.50\n\t\tlocal_food_decay = 0.001\n\t}\n}\nfarmland = {\n\tlocation_modifier = { local_population_capacity = 100 }\n}\n", encoding="utf-8")
    found = wb_modifiers.parse_class_capacity([defs])
    assert found["arid"] == {"local_population_capacity_modifier": 0.5} and found["farmland"] == {"local_population_capacity": 100.0}
    legacy = tmp_path / "climates.txt"
    legacy.write_text("TRY_INJECT:arid = {\n\tlocation_modifier = {\n\t\tlocal_population_capacity_modifier = -0.5\n\t\tfree_building_levels = -6\n\t}\n}\n", encoding="utf-8")
    assert wb_modifiers.parse_legacy_effects(legacy) == {"arid": {"free_building_levels": "-6"}}


def test_cap_script_value_and_gate_use_game_keys(tmp_path):
    c = _contract(tmp_path)
    eq = json.loads(c.building_types["cap_equation_json"][0])
    text = wb_buildings.cap_script_value(c, "land_clearance", eq, 1.0, 20)
    assert "limit = { climate = arid }" in text and "limit = { ha1300_fertility_is_high = yes }" in text
    assert "value = development" in text and "multiply = 0.03" in text and "max = 20" in text
    assert wb_buildings.gate_trigger(c, [{"climate": ["arid", "continental"]}]) == ["OR = { climate = arid climate = continental }"]
    assert wb_buildings.gate_trigger(c, []) == ["always = yes"]


def test_raw_modifier_replacement_merges_duplicate_blocks_and_drops_bridges():
    body = "    max_levels = 5\n    raw_modifier = {\n      farm_capacity_from_land_clearance = 0.60\n      local_population_capacity = 7.65\n    }\n\n      raw_modifier = {\n          farm_capacity_from_x = -1\n        }\n\n    modifier = {\n    }\n"
    out = wb_buildings._replace_raw_modifier(body, {"local_population_capacity": "2.8"}, drop_prefixes=("farm_capacity_from_land",))
    assert out.count("raw_modifier = {") == 1
    assert "local_population_capacity = 2.8" in out and "farm_capacity_from_x = -1" in out and "farm_capacity_from_land_clearance" not in out
    assert wb_buildings._set_max_levels(body, "pp_wb_cap_land_clearance").startswith("    max_levels = pp_wb_cap_land_clearance")
    without = "    is_foreign = no\n    pop_type = peasants\n"
    assert "max_levels = pp_wb_cap_bund" in wb_buildings._set_max_levels(without, "pp_wb_cap_bund")


def test_setup_rows_use_owner_tags_and_scale(tmp_path):
    c = _contract(tmp_path)
    caps = {"land_clearance": {"kind": "clearing", "unit_people": 5200.0, "unit_units": 5.2, "scale": 2.0, "limit": 40}}
    from prosper_or_perish_constructor.worldbuilder.contract import WorldBuilderConfig
    cfg = WorldBuilderConfig(handover=tmp_path, geography_export=tmp_path, building_map={"clearing": "land_clearance"}, farm_land={"arable": {"land": 5, "reserve": 5}}, farm_classes={}, level_scale={}, level_limit=20, goods_floor=-0.2, overpopulation_peasant_unrest=0.1, sync_geography=False)
    mod_root = tmp_path / "mod"
    result = wb_buildings.write_setup(c, cfg, caps, {"a": "SWE"}, mod_root)
    text = (mod_root / wb_buildings.SETUP_PATH).read_text(encoding="utf-8-sig")
    assert result == {"rows": 1, "unowned_skipped": 0} and "land_clearance = { tag = SWE level = 6 location = a }" in text


def test_location_templates_overlay_replaces_fields_by_tag():
    templates = parse_location_templates_text("a = { climate = arid raw_material = goods:wheat natural_harbor_suitability = 0.5 }\n# comment\nb = { climate = oceanic }\n")
    assert templates["a"] == {"climate": "arid", "raw_material": "wheat", "natural_harbor_suitability": 0.5}
    base = pl.DataFrame({"location_tag": ["a", "b", "c"], "climate": ["x", "y", "z"], "raw_material": ["fish", "fish", "fish"], "natural_harbor_suitability": [0.0, 0.0, 0.0]})
    out = apply_location_template_overlay(base, templates)
    assert out["climate"].to_list() == ["arid", "oceanic", "z"] and out["raw_material"].to_list() == ["wheat", "fish", "fish"]
    assert out["natural_harbor_suitability"].to_list() == [0.5, 0.0, 0.0]


def test_farm_constants_by_class(tmp_path):
    from prosper_or_perish_constructor.worldbuilder.contract import WorldBuilderConfig
    cfg = WorldBuilderConfig(handover=tmp_path, geography_export=tmp_path, building_map={}, farm_land={"arable": {"land": 5, "reserve": 5}, "herd": {"land": 2, "reserve": 1}}, farm_classes={"herd": ["sheep_farms"]}, level_scale={}, level_limit=20, goods_floor=-0.2, overpopulation_peasant_unrest=0.1, sync_geography=False)
    assert wb_buildings.farm_constants(cfg, "sheep_farms") == (2.0, 1.0) and wb_buildings.farm_constants(cfg, "farming_village") == (5.0, 5.0)
