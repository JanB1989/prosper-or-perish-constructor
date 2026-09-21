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
    defs.write_text("arid = {\n\tcolor = x\n\tlocation_modifier = {\n\t\tlocal_population_capacity_modifier = 0.50\n\t\tlocal_food_decay = 0.001\n\t\tlocal_monthly_food_modifier = -0.33\n\t}\n}\nfarmland = {\n\tlocation_modifier = { local_population_capacity = 100 }\n}\n", encoding="utf-8")
    found = wb_modifiers.parse_class_capacity([defs])
    assert found["arid"] == {"local_population_capacity_modifier": 0.5, "local_monthly_food_modifier": -0.33} and found["farmland"] == {"local_population_capacity": 100.0}
    legacy = tmp_path / "climates.txt"
    legacy.write_text("TRY_INJECT:arid = {\n\tlocation_modifier = {\n\t\tlocal_population_capacity_modifier = -0.5\n\t\tlocal_monthly_food_modifier = 0.33\n\t\tfree_building_levels = -6\n\t}\n}\n", encoding="utf-8")
    assert wb_modifiers.parse_legacy_effects(legacy) == {"arid": {"free_building_levels": "-6"}}   # food never inherited


def test_cap_script_value_and_gate_use_game_keys(tmp_path):
    c = _contract(tmp_path)
    eq = json.loads(c.building_types["cap_equation_json"][0])
    text = wb_buildings.cap_script_value(c, "land_clearance", eq, 1.0, 20)
    assert "limit = { climate = arid }" in text and "limit = { has_location_modifier = pp_wb_fertility_high }" in text
    assert "value = development" in text and "multiply = 0.03" in text and "max = 20" in text
    assert wb_buildings.gate_trigger(c, [{"climate": ["arid", "continental"]}]) == ["OR = { climate = arid climate = continental }"]
    assert wb_buildings.gate_trigger(c, []) == ["always = yes"]
    assert wb_buildings.trigger_for(c, "river_level", "0") == "has_river = no"
    assert wb_buildings.trigger_for(c, "river_level", "3") == "has_location_modifier = river_flowing_through_3"


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
    cfg = WorldBuilderConfig(handover=tmp_path, geography_export=tmp_path, building_map={"clearing": "land_clearance"}, farm_land={"arable": {"land": 5, "reserve": 5}}, farm_classes={}, level_scale={}, level_limit=20, goods_floor=-0.2, sync_geography=False)
    mod_root = tmp_path / "mod"
    result = wb_buildings.write_setup(c, cfg, caps, {"a": "SWE"}, mod_root)
    text = (mod_root / wb_buildings.SETUP_PATH).read_text(encoding="utf-8-sig")
    assert result == {"rows": 1, "unowned_skipped": 0, "clamped_to_cap": 0} and "land_clearance = { tag = SWE level = 6 location = a }" in text


def test_location_templates_overlay_replaces_fields_by_tag():
    templates = parse_location_templates_text("a = { climate = arid raw_material = goods:wheat natural_harbor_suitability = 0.5 }\n# comment\nb = { climate = oceanic }\n")
    assert templates["a"] == {"climate": "arid", "raw_material": "wheat", "natural_harbor_suitability": 0.5}
    base = pl.DataFrame({"location_tag": ["a", "b", "c"], "climate": ["x", "y", "z"], "raw_material": ["fish", "fish", "fish"], "natural_harbor_suitability": [0.0, 0.0, 0.0]})
    out = apply_location_template_overlay(base, templates)
    assert out["climate"].to_list() == ["arid", "oceanic", "z"] and out["raw_material"].to_list() == ["wheat", "fish", "fish"]
    assert out["natural_harbor_suitability"].to_list() == [0.5, 0.0, 0.0]


def test_farm_constants_by_class(tmp_path):
    from prosper_or_perish_constructor.worldbuilder.contract import WorldBuilderConfig
    cfg = WorldBuilderConfig(handover=tmp_path, geography_export=tmp_path, building_map={}, farm_land={"arable": {"land": 5, "reserve": 5}, "herd": {"land": 2, "reserve": 1}}, farm_classes={"herd": ["sheep_farms"]}, level_scale={}, level_limit=20, goods_floor=-0.2, sync_geography=False)
    assert wb_buildings.farm_constants(cfg, "sheep_farms") == (2.0, 1.0) and wb_buildings.farm_constants(cfg, "farming_village") == (5.0, 5.0)


def _cfg(tmp_path: Path, niche: dict | None = None):
    from prosper_or_perish_constructor.worldbuilder.contract import WorldBuilderConfig

    return WorldBuilderConfig(
        handover=tmp_path, geography_export=tmp_path, building_map={"clearing": "land_clearance"}, niche=niche or {},
        farm_land={"arable": {"land": 5.0, "reserve": 5.0}}, farm_classes={}, level_scale={}, level_limit=20, goods_floor=-0.2,
        sync_geography=False,
    )


def test_niche_buildings_share_the_family_cap_and_are_stronger(tmp_path):
    c = _contract(tmp_path)
    cfg = _cfg(tmp_path, {"terraces_x": {"family": "land_clearance", "strength": 1.5, "lock": ["dominant_culture ?= culture:x"]}})
    caps = wb_buildings.write_caps(c, cfg, tmp_path)
    text = (tmp_path / wb_buildings.CAPS_PATH).read_text(encoding="utf-8-sig")
    assert "pp_wb_cap_land_clearance_shared = {" in text
    assert "pp_wb_cap_land_clearance = {\n\tvalue = pp_wb_cap_land_clearance_shared\n\tsubtract = {\n\t\tdesc = \"BUILDING_LEVEL_WB_SHARED_TERRACES_X\"\n\t\tvalue = modifier:pp_wb_levels_terraces_x" in text
    assert "pp_wb_cap_terraces_x = {\n\tvalue = pp_wb_cap_land_clearance_shared\n\tsubtract = {\n\t\tdesc = \"BUILDING_LEVEL_WB_SHARED_LAND_CLEARANCE\"\n\t\tvalue = modifier:pp_wb_levels_land_clearance" in text
    assert caps["terraces_x"]["unit_units"] == round(5.2 * 1.5, 2) and caps["terraces_x"]["niche"] and caps["terraces_x"]["family"] == "land_clearance"
    types = (tmp_path / wb_buildings.LEVELS_TYPES_PATH).read_text(encoding="utf-8-sig")
    assert "pp_wb_levels_land_clearance = {" in types and "pp_wb_levels_terraces_x = {" in types
    loc = (tmp_path / "main_menu/localization/english/pp_wb_building_caps_l_english.yml").read_text(encoding="utf-8-sig")
    assert 'BUILDING_LEVEL_WB_SHARED_TERRACES_X: "Levels of $terraces_x$"' in loc
    # setup rows only come from the general member (the niche shares its kind)
    owners = {"a": "SWE"}
    out = wb_buildings.write_setup(c, cfg, caps, owners, tmp_path)
    rows = (tmp_path / wb_buildings.SETUP_PATH).read_text(encoding="utf-8-sig")
    assert out["rows"] == 1 and "land_clearance = { tag = SWE level = 3 location = a }" in rows and "terraces_x" not in rows


def test_niche_blueprint_gets_lock_gate_counter_and_must_be_replace(tmp_path):
    import yaml

    c = _contract(tmp_path)
    cfg = _cfg(tmp_path, {"terraces_x": {"family": "land_clearance", "strength": 1.5, "lock": ["dominant_culture ?= culture:x"]}})
    bp = tmp_path / wb_buildings.BLUEPRINTS
    bp.mkdir(parents=True)
    body = "    is_foreign = no\n    max_levels = 1\n    location_potential = {\n      always = yes\n    }\n    modifier = {\n    }\n"
    for key, mode in (("land_clearance", "REPLACE"), ("terraces_x", "REPLACE")):
        (bp / f"{key}.yml").write_text(yaml.safe_dump({"version": 2, "tag": key, "building": {"key": key, "mode": mode, "body": body}}, sort_keys=False), encoding="utf-8")
    (tmp_path / wb_buildings.MANIFEST).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / wb_buildings.MANIFEST).write_text("enabled: {}\n", encoding="utf-8")
    caps = wb_buildings.write_caps(c, cfg, tmp_path)
    patched = wb_buildings.patch_improvement_blueprints(c, cfg, tmp_path, caps)
    assert set(patched) == {"land_clearance", "terraces_x"}
    niche = yaml.safe_load((bp / "terraces_x.yml").read_text(encoding="utf-8"))["building"]["body"]
    assert "max_levels = pp_wb_cap_terraces_x" in niche
    assert "local_population_capacity = 7.8" in niche and "pp_wb_levels_terraces_x = 1" in niche
    assert "location_potential = {\n      dominant_culture ?= culture:x\n      OR = { climate = arid climate = continental }\n    }" in niche
    general = yaml.safe_load((bp / "land_clearance.yml").read_text(encoding="utf-8"))["building"]["body"]
    assert "pp_wb_levels_land_clearance = 1" in general and "dominant_culture" not in general
    (bp / "terraces_x.yml").write_text(yaml.safe_dump({"version": 2, "tag": "terraces_x", "building": {"key": "terraces_x", "mode": "TRY_INJECT", "body": body}}, sort_keys=False), encoding="utf-8")
    with pytest.raises(ValueError, match="REPLACE"):
        wb_buildings.patch_improvement_blueprints(c, cfg, tmp_path, caps)


def test_vanilla_capacity_leaks_need_replace_blueprints(tmp_path):
    import yaml

    vanilla = tmp_path / "vanilla"
    folder = vanilla / "game/in_game/common/building_types"
    folder.mkdir(parents=True)
    (folder / "unique.txt").write_text(
        "﻿bund = {\n\tmax_levels = 3\n\tmodifier = {\n\t\tlocal_population_capacity = 0.5\n\t}\n}\n\npolders = {\n\tmodifier = {\n\t\tlocal_population_capacity_modifier = 0.025\n\t}\n}\n\nmill = {\n\tmodifier = {\n\t\tlocal_grain_output_modifier = 0.1\n\t}\n}\n",
        encoding="utf-8",
    )
    assert wb_buildings.vanilla_capacity_buildings(vanilla) == {"bund": "unique.txt", "polders": "unique.txt"}
    repo = tmp_path / "repo"
    bp = repo / wb_buildings.BLUEPRINTS
    bp.mkdir(parents=True)
    (bp / "bund.yml").write_text(yaml.safe_dump({"building": {"key": "bund", "mode": "INJECT", "body": "x"}}), encoding="utf-8")
    (bp / "polders.yml").write_text(yaml.safe_dump({"building": {"key": "polders", "mode": "REPLACE", "body": "x"}}), encoding="utf-8")
    (repo / wb_buildings.MANIFEST).write_text("enabled:\n  buildings/bund.yml: true\n  buildings/polders.yml: true\n", encoding="utf-8")
    leaks = wb_buildings.vanilla_capacity_leaks(repo, vanilla)
    assert set(leaks) == {"bund"} and "INJECT" in leaks["bund"]
    (bp / "bund.yml").write_text(yaml.safe_dump({"building": {"key": "bund", "mode": "REPLACE", "body": "x"}}), encoding="utf-8")
    assert wb_buildings.vanilla_capacity_leaks(repo, vanilla) == {}
    (repo / wb_buildings.MANIFEST).write_text("enabled:\n  buildings/bund.yml: false\n  buildings/polders.yml: true\n", encoding="utf-8")
    assert "disabled" in wb_buildings.vanilla_capacity_leaks(repo, vanilla)["bund"]


def test_setup_never_places_more_levels_than_the_cap(tmp_path):
    c = _contract(tmp_path)
    eq = json.loads(c.building_types["cap_equation_json"][0])
    # location a: arid (+1), fertility moderate (0), development 20 -> base 2 + 1 + 0.6 = 3.6 -> 3 at scale 1, 7 at scale 2
    assert wb_buildings.cap_levels(eq, {"climate": "arid", "fertility": "moderate", "development": 20.0}, 1.0, 20) == 3
    assert wb_buildings.cap_levels(eq, {"climate": "arid", "fertility": "moderate", "development": 20.0}, 2.0, 40) == 7
    caps = {"land_clearance": {"kind": "clearing", "unit_people": 5200.0, "unit_units": 5.2, "scale": 1.0, "limit": 20}}
    lb = c.location_buildings.with_columns(pl.when(pl.col("location_tag") == "a").then(9).otherwise(pl.col("starting_levels")).alias("starting_levels"))
    c2 = Contract(root=c.root, meta=c.meta, attribute_rows=c.attribute_rows, building_types=c.building_types, location_buildings=lb, location_targets=c.location_targets, location_attributes=c.location_attributes, goods_floor=c.goods_floor)
    out = wb_buildings.write_setup(c2, _cfg(tmp_path), caps, {"a": "SWE"}, tmp_path)
    assert out["clamped_to_cap"] == 1
    assert "land_clearance = { tag = SWE level = 3 location = a }" in (tmp_path / wb_buildings.SETUP_PATH).read_text(encoding="utf-8-sig")


def test_static_modifiers_cover_reference_classes_and_are_placed_in_the_setup(tmp_path):
    c = _contract(tmp_path)
    vanilla = tmp_path / "vanilla"
    (vanilla / "game/main_menu/common/static_modifiers").mkdir(parents=True)
    (vanilla / "game/main_menu/common/static_modifiers/location.txt").write_text("river_flowing_through_1 = {\n\tlocal_population_capacity_modifier = 0.1\n}\n", encoding="utf-8")
    wb_modifiers.write_static_modifiers(c, _cfg(tmp_path), tmp_path, vanilla, {})
    statics = (tmp_path / wb_modifiers.STATIC_MODIFIERS_PATH).read_text(encoding="utf-8-sig")
    assert "pp_wb_fertility_high = {" in statics and "pp_wb_fertility_moderate = {" in statics   # reference class too
    setup = (tmp_path / wb_modifiers.SETUP_MODIFIERS_PATH).read_text(encoding="utf-8-sig")
    assert "locations = {" in setup
    assert '{ modifier = "pp_wb_fertility_high" start_date = 1111.1.1 date = 9999.1.1 size = 1 }' in setup
    assert "\ta = {" in setup and "\tb = {" in setup


def test_class_injects_cancel_vanilla_food_exactly_and_rivers_drop_food(tmp_path):
    c = _contract(tmp_path)
    export = tmp_path / "export"
    (export / "in_game/common/climates").mkdir(parents=True)
    (export / "in_game/common/climates/00_default.txt").write_text("arid = {\n\tlocation_modifier = {\n\t\tlocal_monthly_food_modifier = -0.33\n\t}\n}\ncontinental = {\n}\n", encoding="utf-8")
    for d in ("vegetation", "topography"):
        (export / "in_game/common" / d).mkdir(parents=True)
    wb_modifiers.write_class_injects(c, export, tmp_path, tmp_path)
    text = (tmp_path / "in_game/common/climates/pp_wb_attribute_rows.txt").read_text(encoding="utf-8-sig")
    arid = text[text.index("TRY_INJECT:arid"):]
    arid = arid[: arid.index("\n}") + 2]
    assert "local_monthly_food_modifier = 0.33" in arid      # vanilla -0.33 cancelled exactly
    assert "local_monthly_food_modifier" not in text.replace(arid, "")   # nowhere else
    vanilla = tmp_path / "vanilla"
    (vanilla / "game/main_menu/common/static_modifiers").mkdir(parents=True)
    (vanilla / "game/main_menu/common/static_modifiers/location.txt").write_text("river_flowing_through_2 = {\n\tgame_data = {\n\t\tcategory = location\n\t}\n\tlocal_population_capacity_modifier = 0.2\n\tlocal_monthly_food_modifier = 0.10\n\tlocal_supply_limit_modifier = 0.10\n}\n", encoding="utf-8")
    assert wb_modifiers.river_bodies(vanilla)[2] == ["game_data = {", "category = location", "}", "local_supply_limit_modifier = 0.10"]


def test_effective_class_files_keep_vanilla_definitions_the_export_does_not_replace(tmp_path):
    vanilla = tmp_path / "vanilla"
    export = tmp_path / "export"
    (vanilla / "game/in_game/common/topography").mkdir(parents=True)
    (export / "in_game/common/topography").mkdir(parents=True)
    (vanilla / "game/in_game/common/topography/00_default.txt").write_text("hills = {\n\tlocation_modifier = {\n\t\tlocal_monthly_food_modifier = -0.1\n\t\tlocal_population_capacity_modifier = -0.2\n\t}\n}\n", encoding="utf-8")
    (export / "in_game/common/topography/ha1300_topography.txt").write_text("ha1300_topo_deltas = {\n\tlocation_modifier = {\n\t}\n}\nhills = {\n\tlocation_modifier = {\n\t\tlocal_monthly_food_modifier = -0.3\n\t}\n}\n", encoding="utf-8")
    files = wb_modifiers.effective_class_files(Path("topography"), export, vanilla)
    assert [f.name for f in files] == ["00_default.txt", "ha1300_topography.txt"]
    defs = wb_modifiers.parse_class_capacity(files)
    assert defs["hills"] == {"local_monthly_food_modifier": -0.3}      # later file replaces the class definition
    assert defs["ha1300_topo_deltas"] == {}
    # the export replacing 00_default.txt wins over vanilla's copy
    (export / "in_game/common/topography/00_default.txt").write_text("hills = {\n\tlocation_modifier = {\n\t\tlocal_monthly_food_modifier = -0.5\n\t}\n}\n", encoding="utf-8")
    (export / "in_game/common/topography/ha1300_topography.txt").write_text("ha1300_topo_deltas = {\n}\n", encoding="utf-8")
    defs = wb_modifiers.parse_class_capacity(wb_modifiers.effective_class_files(Path("topography"), export, vanilla))
    assert defs["hills"] == {"local_monthly_food_modifier": -0.5}


def test_expand_attribute_tests_widens_parents_once_and_leaves_the_rest(tmp_path):
    from prosper_or_perish_constructor.worldbuilder import compat as wb_compat

    fam = {"vegetation": {"forest": ["ha1300_veg_coniferous_forest", "ha1300_veg_swamp"]}, "climate": {"tropical": ["ha1300_climate_savanna"]}, "topography": {}}
    text = "x = {\n\tvegetation = forest\n\tNOT = { climate = tropical }   # keep this comment: climate = tropical\n\tvegetation = jungle\n\tOR = { vegetation = forest vegetation = ha1300_veg_coniferous_forest vegetation = ha1300_veg_swamp }\n}\n"
    out, n = wb_compat.expand_attribute_tests(text, fam)
    assert n == 2
    assert "\tOR = { vegetation = forest vegetation = ha1300_veg_coniferous_forest vegetation = ha1300_veg_swamp }\n" in out
    assert "NOT = { OR = { climate = tropical climate = ha1300_climate_savanna } }   # keep this comment: climate = tropical" in out
    assert "vegetation = jungle" in out
    again, m = wb_compat.expand_attribute_tests(out, fam)
    assert m == 0 and again == out
    vanilla = tmp_path / "vanilla"
    (vanilla / "game/in_game/common/diseases").mkdir(parents=True)
    (vanilla / "game/in_game/common/diseases/malaria.txt").write_text(text, encoding="utf-8")
    (vanilla / "game/in_game/common/diseases/none.txt").write_text("y = { vegetation = jungle }\n", encoding="utf-8")
    mod = tmp_path / "mod"
    report = wb_compat.write_compat_patches(vanilla, mod, tmp_path, fam, ["in_game/common/diseases/malaria.txt", "in_game/common/diseases/none.txt"])
    assert report == {"files": 1, "tests_widened": 2, "unchanged": ["in_game/common/diseases/none.txt"]}
    assert (mod / "in_game/common/diseases/malaria.txt").is_file() and not (mod / "in_game/common/diseases/none.txt").exists()



def test_population_capacity_cell_bands_the_gauge_and_names_both_sides_of_the_ratio():
    from prosper_or_perish_constructor.worldbuilder import geography as wb_geography

    cell = "\t\t\t\t\t\tsize = { 120 28 }\n"
    text = "\t\t\t\t\t\tsize = { 90 28 }\n" + cell + wb_geography._POP_VBOX + "\n" + wb_geography._POP_TEXT + "\n" + wb_geography._CAPACITY_BAR + "\n"
    out = wb_geography.merge_population_capacity(text)

    assert "\t\t\t\t\t\tsize = { 90 28 }\n" in out             # the other header cells keep their width
    assert "\t\t\t\t\t\tsize = { 185 28 }\n" in out            # only the population cell widens
    assert "ignoreinvisible = yes" in out                       # the hidden gauges must not reserve rows
    assert "GetTotalPopulation]@population!" not in out

    # raw_text, not a loc key: a loc key resolved to an empty cell in game.
    assert 'raw_text = "[Location.GetTotalPopulation]/[Location.GetPopulationCapacity] · [Location.GetCapacityPercentage|0]%"' in out
    assert out.count('block "location_population_sort_highlight" {}') == 1
    assert "using = progress_bar_green_alt" not in out         # replaced by four explicitly textured bars
    assert out.count('name = "pp_pop_capacity_bar_') == 4
    assert out.count("gfx/interface/progressbars/progress_bar_red_alt.dds") == 1

    # GetCapacityPercentage is 0..100, so the bars restate the range rather than rescaling the value.
    assert out.count("\t\t\t\t\t\t\t\t\tmin = 0\n\t\t\t\t\t\t\t\t\tmax = 100\n") == 4

    # Half-open bands: every fill lights exactly one bar, with no overlap and no gap.
    percent = "Location.GetCapacityPercentage"
    assert f"And(HasPopBreakdownIntelOn(Location.Self), LessThan_float({percent}, '(float)70'))" in out
    assert f"And3(HasPopBreakdownIntelOn(Location.Self), GreaterThanOrEqualTo_float({percent}, '(float)70'), LessThan_float({percent}, '(float)90'))" in out
    assert f"And(HasPopBreakdownIntelOn(Location.Self), GreaterThanOrEqualTo_float({percent}, '(float)100'))" in out

    with pytest.raises(ValueError, match="population-cell anchor"):
        wb_geography.merge_population_capacity(out)


def test_development_row_from_the_handover(tmp_path):
    c = _contract(tmp_path)
    c.meta["attributes"]["capacity_people_per_development_point"] = 1000.0
    assert c.people_per_development_point == 1000.0
    vanilla = tmp_path / "vanilla"
    (vanilla / "game/main_menu/common/static_modifiers").mkdir(parents=True)
    (vanilla / "game/main_menu/common/static_modifiers/location.txt").write_text("river_flowing_through_1 = {\n\tlocal_population_capacity_modifier = 0.1\n}\n", encoding="utf-8")
    adj = tmp_path / wb_modifiers.ADJUSTMENTS_PATH
    adj.parent.mkdir(parents=True, exist_ok=True)
    adj.write_text("\ufeffTRY_REPLACE:development = {\n\tgame_data = {\n\t\tcategory = location\n\t}\n\tlocal_supply_limit_modifier = 0.02\n\tlocal_population_capacity = 0\n\tlocal_population_capacity_modifier = 0.00125\n}\n\nTRY_INJECT:river_flowing_through_1 = {\n\tfree_building_levels = 10\n}\n", encoding="utf-8")
    wb_modifiers.write_static_modifiers(c, _cfg(tmp_path), tmp_path, vanilla, {})
    text = adj.read_text(encoding="utf-8-sig")
    block = text[text.index("TRY_REPLACE:development"): text.index("TRY_INJECT:river")]
    assert block.count("local_population_capacity") == 1 and "local_population_capacity = 1\n" in block and "0.00125" not in block
    assert "local_supply_limit_modifier = 0.02" in block and "free_building_levels = 10" in text
    assert not (tmp_path / "main_menu/common/static_modifiers/pp_wb_development.txt").exists()
    c.meta["attributes"]["capacity_people_per_development_point"] = 0.0
    wb_modifiers.write_static_modifiers(c, _cfg(tmp_path), tmp_path, vanilla, {})
    block = adj.read_text(encoding="utf-8-sig").split("TRY_INJECT:river")[0]
    assert "local_population_capacity" not in block and "no population capacity from development" in block


def test_river_replacements_fold_in_the_hand_authored_injects(tmp_path):
    c = _contract(tmp_path)
    vanilla = tmp_path / "vanilla"
    (vanilla / "game/main_menu/common/static_modifiers").mkdir(parents=True)
    (vanilla / "game/main_menu/common/static_modifiers/location.txt").write_text("river_flowing_through_2 = {\n\tgame_data = {\n\t\tcategory = location\n\t}\n\tlocal_population_capacity_modifier = 0.2\n\tlocal_monthly_food_modifier = 0.10\n\tlocal_supply_limit_modifier = 0.10\n}\n", encoding="utf-8")
    adj = tmp_path / wb_modifiers.ADJUSTMENTS_PATH
    adj.parent.mkdir(parents=True, exist_ok=True)
    adj.write_text("TRY_REPLACE:development = {\n\tgame_data = {\n\t\tcategory = location\n\t}\n}\n\nTRY_INJECT:river_flowing_through_2 = {\n\tlocal_population_capacity_modifier = -0.2\n\tfarm_capacity_from_river_size = 1\n\tfree_building_levels = 15\n\tlocal_supply_limit_modifier = 0.05 # vanilla 0.10\n}\n", encoding="utf-8")
    wb_modifiers.write_static_modifiers(c, _cfg(tmp_path), tmp_path, vanilla, {})
    text = (tmp_path / wb_modifiers.RIVER_MODIFIERS_PATH).read_text(encoding="utf-8-sig")
    block = text[text.index("TRY_REPLACE:river_flowing_through_2"):]
    assert "free_building_levels = 15" in block and "farm_capacity_from_river_size = 1" in block
    assert "local_supply_limit_modifier = 0.15" in block            # vanilla 0.10 + the additive inject 0.05
    assert "local_population_capacity_modifier" not in block and "local_monthly_food_modifier" not in block


def test_location_window_chips_show_their_modifier_effects():
    from prosper_or_perish_constructor.worldbuilder import geography as wb_geography

    gui = (
        'blockoverride "tooltip_content" { TooltipFlavorTextBlock = { blockoverride "text" { text = "[LocationView.GetLocation.Custom(\'ha1300_fertility_desc\')]" } } }\n'
        'blockoverride "tooltip_content" { TooltipTextBlock = { blockoverride "text" { text = "HA1300_LAKE_HELP" } } }\n'
        'x textcontext = "[ShowModifierEffect(\'coastal\')]"\n    } }\n'
    )
    out = wb_geography.add_attribute_effect_rows(gui)
    assert out.count("ShowModifierEffect('pp_wb_fertility_") == 5 and "pp_wb_fertility_very_high" in out
    assert "ShowModifierEffect('pp_wb_lake')" in out and "HA1300_LAKESIDE" in out
    assert "ShowModifierEffect('pp_wb_coastal')" in out and out.count("ShowModifierEffect('coastal')") == 1
    assert out.count("{") - out.count("}") == gui.count("{") - gui.count("}")   # the rows are balanced

