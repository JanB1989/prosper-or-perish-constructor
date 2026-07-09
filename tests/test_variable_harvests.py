from __future__ import annotations

import re
import tomllib
from pathlib import Path

import polars as pl
from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.domain.eu5 import load_eu5_data

from scripts.generate_variable_harvests import (
    ACTIVE_SEVERITIES,
    LAND_SUPER_REGIONS,
    PROFILE,
    ROOT,
    _regions_by_subcontinent,
)
from test_project_config import LAND_FARM_BUILDINGS


MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
CONFIG_PATH = ROOT / "variable_harvests.toml"
HARVEST_MODIFIERS = (
    MOD_ROOT / "in_game" / "common" / "static_modifiers" / "pp_variable_harvest_modifiers.txt"
)
HARVEST_EFFECTS = (
    MOD_ROOT / "in_game" / "common" / "scripted_effects" / "pp_variable_harvest_effects.txt"
)
HARVEST_SITUATION = (
    MOD_ROOT / "in_game" / "common" / "situations" / "pp_variable_harvest_situation.txt"
)
HARVEST_LOCALIZATION = (
    MOD_ROOT
    / "main_menu"
    / "localization"
    / "english"
    / "pp_variable_harvest_modifiers_l_english.yml"
)
EUROPEDIA_LOCALIZATION = MOD_ROOT / "main_menu" / "localization" / "english" / "pp_europedia_l_english.yml"
SITUATION_LOCALIZATION = MOD_ROOT / "main_menu" / "localization" / "english" / "pp_situations_l_english.yml"
MODIFIER_LOCALIZATION = MOD_ROOT / "main_menu" / "localization" / "english" / "pp_modifiers_l_english.yml"
ENCYCLOPEDIA_LATERALVIEW = MOD_ROOT / "in_game" / "gui" / "encyclopedia_lateralview.gui"
AGENTS = ROOT / "AGENTS.md"


def test_variable_harvest_profiles_are_balanced() -> None:
    config = _load_config()
    scores = config["severity_scores"]
    profiles = config["profiles"]

    for name, weights in profiles.items():
        assert sum(weights.values()) == 100, name

    assert _expected_score(profiles["neutral"], scores) == 0
    assert _expected_score(profiles["shock_bad"], scores) == -_expected_score(
        profiles["shock_good"], scores
    )
    assert _expected_score(profiles["memory_bad"], scores) == -_expected_score(
        profiles["memory_good"], scores
    )
    assert _expected_score(profiles["bad_persistent"], scores) == -_expected_score(
        profiles["good_persistent"], scores
    )

    shock_weights = config["shock_weights"]
    assert sum(shock_weights.values()) == 100
    assert shock_weights["bad"] == shock_weights["good"]


def test_variable_harvest_modifiers_cover_all_farmed_goods() -> None:
    config = _load_config()
    farmed_goods = _parser_confirmed_farmed_goods()
    configured_goods = set(config["goods"])
    fallback_goods = {"fish", "fur", "wild_game"}
    assert farmed_goods <= configured_goods
    assert {"dyes", "elephants", "medicaments", "wine"} <= farmed_goods
    assert fallback_goods <= configured_goods

    entries = _modifier_entries()
    for subcontinent in config["subcontinents"]:
        for severity in ACTIVE_SEVERITIES:
            key = f"pp_harvest_{subcontinent}_{severity}"
            assert key in entries
            covered = _output_goods(entries[key])
            assert configured_goods == covered
            assert farmed_goods <= covered
            assert fallback_goods <= covered


def test_variable_harvest_crop_families_capture_historical_adjustments() -> None:
    config = _load_config()
    overrides = config["reviewed_tier_overrides"]

    assert config["goods"]["rice"]["family"] == "rice"
    assert {config["goods"][good]["family"] for good in ("wheat", "millet", "maize")} == {"dry_cereals"}
    assert {config["goods"][good]["family"] for good in ("fruit", "olives", "wine")} == {"orchards"}
    assert {config["goods"][good]["family"] for good in ("cocoa", "coffee", "tea", "sugar")} == {"plantations"}

    assert overrides["east_asia"]["rice"] == "low"
    assert overrides["south_east_asia"]["rice"] == "standard"
    assert overrides["south_asia"]["rice"] == "standard"
    assert overrides["middle_east"]["rice"] == "low"
    assert overrides["north_africa"]["rice"] == "low"
    assert overrides["west_africa"]["dry_cereals"] == "high"
    assert overrides["middle_east"]["dry_cereals"] == "high"
    assert overrides["north_africa"]["dry_cereals"] == "high"


def test_variable_harvest_values_are_mirrored() -> None:
    config = _load_config()
    entries = _modifier_entries()
    mirrored_pairs = (
        ("abysmal", "bountiful"),
        ("very_poor", "very_good"),
        ("poor", "good"),
    )

    for subcontinent in config["subcontinents"]:
        for bad, good in mirrored_pairs:
            bad_values = _entry_values(entries[f"pp_harvest_{subcontinent}_{bad}"])
            good_values = _entry_values(entries[f"pp_harvest_{subcontinent}_{good}"])
            for key, value in bad_values.items():
                if not key.startswith("local_"):
                    continue
                assert key in good_values
                assert value == -good_values[key]


def test_variable_harvest_output_values_are_globally_scaled_without_food_scaling() -> None:
    config = _load_config()
    entries = _modifier_entries()
    target = config["output_scaling"]["max_abs_output_modifier"]
    output_values: list[float] = []

    for subcontinent in config["subcontinents"]:
        for severity in ACTIVE_SEVERITIES:
            values = _entry_values(entries[f"pp_harvest_{subcontinent}_{severity}"])
            assert values["local_peasants_food_consumption"] == config["food_consumption"][severity]
            output_values.extend(
                value
                for key, value in values.items()
                if key.startswith("local_") and key.endswith("_output_modifier")
            )

    assert max(output_values) == target
    assert min(output_values) == -target
    assert all(-target <= value <= target for value in output_values)


def test_variable_harvest_effects_are_global_ownable_and_memory_based() -> None:
    config = _load_config()
    text = HARVEST_EFFECTS.read_text(encoding="utf-8-sig")
    situation = HARVEST_SITUATION.read_text(encoding="utf-8-sig")

    assert "continent:europe" not in text
    assert "every_area_in_region" not in text
    assert "is_ownable = yes" in text
    assert "has_province_modifier = russian_famine" in text
    assert "months = 13" in text
    assert "any_location_in_region" in text
    assert "$subcontinent$" in text
    assert "$severity$" in text
    assert "modifier = pp_harvest_$subcontinent$_$severity$" in text
    assert "modifier = $severity$_harvest_modifier" not in text
    assert "pp_harvest_$subcontinent$_normal" not in text
    assert "has_location_modifier = pp_harvest_$subcontinent$_abysmal" in text
    assert "has_location_modifier = pp_harvest_$subcontinent$_bountiful" in text
    assert "PP_HARVEST_LEGEND_KEY_AVERAGE" in situation
    assert 'desc = "LEGEND_KEY_' not in situation
    for severity in ACTIVE_SEVERITIES:
        assert f'PP_HARVEST_LEGEND_KEY_{severity.upper()}' in situation
    for subcontinent in config["subcontinents"]:
        assert f"sub_continent:{subcontinent}" in text
        assert f"has_location_modifier = pp_harvest_{subcontinent}_abysmal" in situation
        assert f"has_location_modifier = pp_harvest_{subcontinent}_bountiful" in situation
    for family in config["families"]:
        assert f"modifier = pp_harvest_$subcontinent$_{family}_$severity$" not in text


def test_variable_harvest_has_no_legacy_modifiers_or_migration_paths() -> None:
    config = _load_config()
    generated_text = "\n".join(
        [
            HARVEST_MODIFIERS.read_text(encoding="utf-8-sig"),
            HARVEST_EFFECTS.read_text(encoding="utf-8-sig"),
            HARVEST_SITUATION.read_text(encoding="utf-8-sig"),
            HARVEST_LOCALIZATION.read_text(encoding="utf-8-sig"),
            MODIFIER_LOCALIZATION.read_text(encoding="utf-8-sig"),
        ]
    )
    situation = HARVEST_SITUATION.read_text(encoding="utf-8-sig")

    assert "pp_migrate_regional_harvest_ui_cleanup = yes" not in situation
    assert "legacy" not in generated_text.lower()
    assert "migrate" not in generated_text.lower()
    assert "clear_legacy_variable_harvest_effects_in_region" not in generated_text
    family_names = "|".join(re.escape(family) for family in config["families"])
    severity_names = "|".join(ACTIVE_SEVERITIES)
    family_pattern = re.compile(rf"pp_harvest_[a-z_]+_({family_names})_({severity_names})")
    assert not family_pattern.search(generated_text)
    for severity in ACTIVE_SEVERITIES:
        assert f"{severity}_harvest_modifier" not in generated_text


def test_variable_harvest_combined_modifiers_are_localized() -> None:
    config = _load_config()
    text = HARVEST_LOCALIZATION.read_text(encoding="utf-8-sig")

    for subcontinent in config["subcontinents"]:
        for severity in ACTIVE_SEVERITIES:
            key = f"pp_harvest_{subcontinent}_{severity}"
            assert f"STATIC_MODIFIER_NAME_{key}:" in text
            assert f"STATIC_MODIFIER_DESC_{key}:" in text


def test_variable_harvest_generated_pp_modifiers_are_localized() -> None:
    localization_keys = _localization_keys(HARVEST_LOCALIZATION)
    missing: list[str] = []

    for modifier in _modifier_entries():
        if not modifier.startswith("pp_harvest_"):
            continue
        name_key = f"STATIC_MODIFIER_NAME_{modifier}"
        desc_key = f"STATIC_MODIFIER_DESC_{modifier}"
        if name_key not in localization_keys:
            missing.append(name_key)
        if desc_key not in localization_keys:
            missing.append(desc_key)

    assert not missing


def test_variable_harvest_localization_is_player_facing_and_value_free() -> None:
    generated_text = HARVEST_LOCALIZATION.read_text(encoding="utf-8-sig")
    europedia_lines = _harvest_localization_lines(EUROPEDIA_LOCALIZATION)
    europedia_text = "\n".join(europedia_lines)
    rule_text = AGENTS.read_text(encoding="utf-8-sig")

    forbidden_phrases = (
        "single P&P harvest modifier",
        "listed effects",
        "current values",
        "implementation",
        "technical",
    )
    for text in (generated_text, europedia_text):
        for phrase in forbidden_phrases:
            assert phrase not in text

    value_pattern = re.compile(r"[-+]?\d+(?:\.\d+)?%?")
    for line in generated_text.splitlines():
        if line.strip().startswith("#"):
            continue
        assert not value_pattern.search(line), line
    for line in europedia_lines:
        assert not value_pattern.search(line), line

    assert "Localization is player-facing in-game text" in rule_text
    assert "Do not hardcode balance values in localization" in rule_text
    assert "unsupported formatter tags spam" in rule_text
    assert "broad harvest areas" in europedia_text
    assert "each [region|e] inside it still receives its own harvest result" in europedia_text
    assert "without forcing every region to share the same outcome" in europedia_text


def test_variable_harvest_situation_text_uses_plain_formatter_text() -> None:
    generated_text = HARVEST_LOCALIZATION.read_text(encoding="utf-8-sig")
    situation_script = HARVEST_SITUATION.read_text(encoding="utf-8-sig")
    situation_text = "\n".join(
        _situation_localization_lines(EUROPEDIA_LOCALIZATION)
        + _situation_localization_lines(SITUATION_LOCALIZATION)
    )
    unsupported_link_pattern = re.compile(r"\[[^\]]+\|[eElL]\]|\[Link\(")
    lowercase_formatter_pattern = re.compile(r"#[a-z][A-Za-z_]*")

    assert not unsupported_link_pattern.search(generated_text)
    assert not unsupported_link_pattern.search(situation_text)
    assert not lowercase_formatter_pattern.search(situation_text)
    assert "custom_tooltip = province_is_starving_tt" not in situation_script
    assert "custom_tooltip = market_negative_food_balance_tt" not in situation_script
    assert "custom_tooltip = affected_by_extended_winters_tt" not in situation_script
    assert 'desc = "LEGEND_KEY_STARVING"' not in situation_script
    assert 'desc = "LEGEND_KEY_FOOD_NEG"' not in situation_script
    assert 'desc = "LEGEND_KEY_' not in situation_script
    assert "pp_harvest_province_is_starving_tt" in situation_text
    assert "PP_HARVEST_LEGEND_KEY_ABYSMAL" in situation_text
    assert "PP_HARVEST_LEGEND_KEY_AVERAGE" in situation_text
    assert "PP_HARVEST_LEGEND_KEY_FOOD_NEG" in situation_text


def test_variable_harvest_situation_gui_does_not_use_formatter_as_default_style() -> None:
    gui_text = ENCYCLOPEDIA_LATERALVIEW.read_text(encoding="utf-8-sig")

    assert 'default_format = "#' not in gui_text
    assert 'default_format = "yellow_titles"' in gui_text


def test_variable_harvest_generated_regions_cover_land_subcontinents() -> None:
    config = _load_config()
    from eu5gameparser.savegame.hierarchy import load_location_hierarchy

    hierarchy = load_location_hierarchy(profile=PROFILE, load_order_path=ROOT / "constructor.load_order.toml")
    expected_regions = {
        row["region"]
        for row in hierarchy.values()
        if row.get("super_region") in LAND_SUPER_REGIONS
        and row.get("macro_region") in config["subcontinents"]
        and row.get("region")
    }
    generated_regions = {
        region
        for regions in _regions_by_subcontinent(config, hierarchy).values()
        for region in regions
    }

    assert expected_regions == generated_regions


def _load_config() -> dict:
    with CONFIG_PATH.open("rb") as handle:
        return tomllib.load(handle)


def _expected_score(weights: dict[str, int], scores: dict[str, int]) -> int:
    return sum(weights[severity] * scores[severity] for severity in scores)


def _modifier_entries() -> dict[str, CList]:
    return {
        entry.key: entry.value
        for entry in parse_file(HARVEST_MODIFIERS).entries
        if isinstance(entry.value, CList)
    }


def _entry_values(block: CList) -> dict[str, object]:
    return {entry.key: entry.value for entry in block.entries}


def _output_goods(block: CList) -> set[str]:
    return {
        key.removeprefix("local_").removesuffix("_output_modifier")
        for key in _entry_values(block)
        if key.startswith("local_") and key.endswith("_output_modifier")
    }


def _parser_confirmed_farmed_goods() -> set[str]:
    data = load_eu5_data(profile="constructor", load_order_path=ROOT / "constructor.load_order.toml")
    methods = data.building_data.production_methods
    return set(
        methods.filter(
            pl.col("building").is_in(LAND_FARM_BUILDINGS)
            & pl.col("produced").is_not_null()
            & (pl.col("produced") != "victuals")
        )["produced"].unique()
    )


def _harvest_localization_lines(path: Path) -> list[str]:
    prefixes = (
        "game_concept_harvest_situation_desc:",
        "game_concept_pp_variable_harvests_desc:",
        "harvest_situation_desc:",
        "harvest_situation_monthly:",
        "game_concept_abysmal_harvest_desc:",
        "game_concept_very_poor_harvest_desc:",
        "game_concept_poor_harvest_desc:",
        "game_concept_good_harvest_desc:",
        "game_concept_very_good_harvest_desc:",
        "game_concept_bountiful_harvest_desc:",
    )
    return [
        line
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.startswith(prefixes)
    ]


def _situation_localization_lines(path: Path) -> list[str]:
    prefixes = (
        "pp_mod_welcome_situation:",
        "pp_mod_welcome_situation_desc:",
        "pp_harvest_province_is_starving_tt:",
        "pp_harvest_market_negative_food_balance_tt:",
        "pp_harvest_affected_by_extended_winters_tt:",
        "PP_HARVEST_LEGEND_KEY_ABYSMAL:",
        "PP_HARVEST_LEGEND_KEY_VERY_POOR:",
        "PP_HARVEST_LEGEND_KEY_POOR:",
        "PP_HARVEST_LEGEND_KEY_GOOD:",
        "PP_HARVEST_LEGEND_KEY_VERY_GOOD:",
        "PP_HARVEST_LEGEND_KEY_BOUNTIFUL:",
        "PP_HARVEST_LEGEND_KEY_AVERAGE:",
        "PP_HARVEST_LEGEND_KEY_STARVING:",
        "PP_HARVEST_LEGEND_KEY_FOOD_NEG:",
        "harvest_situation:",
        "harvest_situation_desc:",
        "harvest_situation_monthly:",
    )
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip().startswith(prefixes)
    ]


def _localization_keys(path: Path) -> set[str]:
    pattern = re.compile(
        r"^\s*(STATIC_MODIFIER_(?:NAME|DESC)_[^:]+):",
        re.MULTILINE,
    )
    return {
        match.group(1)
        for match in pattern.finditer(path.read_text(encoding="utf-8-sig"))
    }
