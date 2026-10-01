"""Stored-food tiers (EU5 1.4 carrier of the 1.3 stored-food effects; docs/historical_growth_calibration.md 6.2)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.syntax import CList

from prosper_or_perish_constructor import cli, stored_food
from prosper_or_perish_constructor.worldbuilder import migration

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
ON_ACTION = MOD_ROOT / "in_game/common/on_action/pp_stored_food.txt"
GAME_START = MOD_ROOT / "in_game/common/on_action/pp_game_start.txt"
STORAGE_VALUES = MOD_ROOT / "in_game/common/script_values/pp_province_food_storage.txt"
DEFINES = MOD_ROOT / "loading_screen/common/defines/pp_defines_adjustments.txt"

# The EU5 1.3 positive_province_food_growth values per stored year, growth included (the engine's storage term
# NPop.FOOD_STORAGE_POP_GROWTH is 0 since growth moved onto the tiers).
PAYLOAD_1_3 = {
    "local_population_growth": 0.0075,
    "local_province_food_sales_output_modifier": 8.0,
    "local_province_food_purchase_output_modifier": -8.0,
    "local_devastation_recovery": 0.003,
    "local_migration_attraction": 0.045,
    "local_monthly_prosperity": 0.0025,
}


def _config() -> stored_food.StoredFoodConfig:
    return stored_food.load_config(PROJECT)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _block(text: str, name: str) -> str:
    start = text.index(f"\n{name} = {{") + 1
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"unclosed block {name}")


def _define(name: str) -> float:
    return float(re.search(rf"^\s*{name}\s*=\s*(-?[\d.]+)", _read(DEFINES), flags=re.MULTILINE).group(1))


def test_payload_is_the_1_3_stored_food_modifier() -> None:
    config = _config()
    assert dict(config.per_year) == PAYLOAD_1_3


def test_growth_rides_the_tiers_and_the_engine_term_is_off() -> None:
    # same law as the old define term: 0.0075 per stored year = FOOD_STORAGE_POP_GROWTH 0.015 at the 2-year cap
    config = _config()
    cap_years = _define("GROWTH_FROM_FOOD_MULTIPLIER_MAX")
    assert stored_food.growth_per_year(config) * cap_years == pytest.approx(0.015)
    assert stored_food.tier_values(config, 24)["local_population_growth"] == pytest.approx(0.015)
    assert stored_food.tier_values(config, 1)["local_population_growth"] == pytest.approx(0.000625, abs=5.1e-6)
    # the engine's own storage term would add the growth a second time
    assert _define("FOOD_STORAGE_POP_GROWTH") == 0
    assert _define("FOOD_SURPLUS_POP_GROWTH") == 0


def test_24_monthly_tiers_reach_the_growth_cap() -> None:
    config = _config()
    assert (config.tiers, config.months_per_tier) == (24, 1)
    cap_years = float(re.search(r"GROWTH_FROM_FOOD_MULTIPLIER_MAX\s*=\s*([\d.]+)", _read(DEFINES)).group(1))
    assert config.tiers * config.months_per_tier == cap_years * 12


def test_tier_values_are_the_payload_times_months_over_twelve() -> None:
    config = _config()
    text = _read(MOD_ROOT / stored_food.STATIC_MODIFIERS)
    names = re.findall(r"^(pp_stored_food_tier_\d+) = \{", text, flags=re.MULTILINE)
    assert names == [f"pp_stored_food_tier_{t}" for t in range(1, 25)]
    for tier in range(1, 25):
        block = _block("\n" + text, f"pp_stored_food_tier_{tier}")
        assert "game_data = { category = province }" in block
        values = dict(re.findall(r"^\t(local_\w+) = (-?[\d.]+)$", block, flags=re.MULTILINE))
        assert set(values) == set(PAYLOAD_1_3)
        for key, per_year in PAYLOAD_1_3.items():
            assert float(values[key]) == pytest.approx(per_year * tier / 12, abs=5.1e-6)
            assert len(values[key].split(".")[1]) <= 5   # never more than five decimals (EU5 1.4 rejects six)
    last = _block("\n" + text, "pp_stored_food_tier_24")
    for key, per_year in PAYLOAD_1_3.items():   # tier 24 = two stored years, the 1.3 cap
        assert f"\t{key} = {stored_food.format_value(per_year * 2)}\n" in last
    assert stored_food.tier_values(config, 12) == pytest.approx(PAYLOAD_1_3)


def test_generated_files_match_the_configuration() -> None:
    result = stored_food.apply(PROJECT, MOD_ROOT, write=False)
    assert result.changed == ()


def test_localization_names_every_tier_without_numbers_in_the_description() -> None:
    loc = _read(MOD_ROOT / stored_food.LOCALIZATION)
    assert '  STATIC_MODIFIER_NAME_pp_stored_food_tier_1: "Stored Food: 1 month"' in loc
    assert '  STATIC_MODIFIER_NAME_pp_stored_food_tier_24: "Stored Food: 24 months"' in loc
    for tier in range(1, 25):
        assert f"\n  STATIC_MODIFIER_NAME_pp_stored_food_tier_{tier}:" in loc
        assert f"\n  STATIC_MODIFIER_DESC_pp_stored_food_tier_{tier}:" in loc
    assert not re.search(r"\d", stored_food.DESCRIPTION)
    assert "[" not in stored_food.DESCRIPTION and "#" not in stored_food.DESCRIPTION


def test_refresh_effect_covers_every_tier_and_only_acts_on_change() -> None:
    text = _read(MOD_ROOT / stored_food.SCRIPTED_EFFECTS)
    effect = _block("\n" + text, "pp_refresh_stored_food_tier")
    for tier in range(1, 25):
        name = f"pp_stored_food_tier_{tier}"
        assert effect.count(f"remove_province_modifier = {name}\n") == 1
        assert effect.count(f"add_province_modifier = {{ modifier = {name} }}") == 1
        assert f"var:pp_stored_food_tier > {100 + tier - 0.5} var:pp_stored_food_tier < {100 + tier + 0.5}" in effect
        assert (
            f"var:pp_stored_food_tier_next > {100 + tier - 0.5} var:pp_stored_food_tier_next < {100 + tier + 0.5}"
            in effect
        )
    assert "pp_stored_food_tier_0" not in effect and "pp_stored_food_tier_25" not in effect
    # +100 offsets (a variable at 0 counts as unset) and no `var:x = n` (a scope comparison in game)
    assert "value = { value = pp_stored_food_tier_target add = 100 }" in effect
    assert "value = { value = var:pp_stored_food_tier_next subtract = var:pp_stored_food_tier add = 100 }" in effect
    assert "var:pp_stored_food_tier_change < 99.5 var:pp_stored_food_tier_change > 100.5" in effect
    assert not re.search(r"var:\w+ = ", effect)
    # the modifiers are touched only inside the change branch, and the new tier is stored there
    change = effect[effect.index("var:pp_stored_food_tier_change < 99.5") :]
    assert change.count("remove_province_modifier") == 24 and change.count("add_province_modifier") == 24
    assert "set_variable = { name = pp_stored_food_tier value = var:pp_stored_food_tier_next }" in change
    parse_file(MOD_ROOT / stored_food.SCRIPTED_EFFECTS)   # well formed


def test_growth_display_value_reads_the_carried_tier() -> None:
    text = "\n" + _read(MOD_ROOT / stored_food.SCRIPT_VALUES)
    value = _block(text, "pp_province_food_storage_growth")
    assert re.search(
        r"province \?= \{\s*if = \{\s*limit = \{ has_variable = pp_stored_food_tier \}\s*"
        r"add = var:pp_stored_food_tier\s*subtract = 100\s*\}\s*\}",
        value,
    )
    assert "multiply = 0.0075" in value and "divide = 12" in value
    assert "FOOD_STORAGE_POP_GROWTH" not in value
    # the hand-written storage values no longer model an engine term
    storage = "\n" + _read(STORAGE_VALUES)
    assert "\npp_province_food_storage_growth = {" not in storage
    assert re.search(r"pp_population_growth_map_value = \{\s*value = modifier:local_population_growth\s*\}", storage)
    parse_file(MOD_ROOT / stored_food.SCRIPT_VALUES)


def test_custom_localization_names_the_carried_tier() -> None:
    text = _read(MOD_ROOT / stored_food.CUSTOM_LOCALIZATION)
    block = _block("\n" + text, "pp_stored_food_tier")
    assert "type = location" in block
    for tier in range(1, 25):
        name = f"pp_stored_food_tier_{tier}"
        assert (
            f"text = {{ localization_key = STATIC_MODIFIER_NAME_{name} "
            f"trigger = {{ province ?= {{ has_province_modifier = {name} }} }} }}"
        ) in block
    assert block.rstrip().endswith("text = { localization_key = PP_STORED_FOOD_TIER_NONE fallback = yes }\n}")
    loc = _read(MOD_ROOT / stored_food.LOCALIZATION)
    assert '  PP_STORED_FOOD_TIER_NONE: "none"' in loc
    parse_file(MOD_ROOT / stored_food.CUSTOM_LOCALIZATION)


def test_tier_target_is_whole_months_capped_at_the_last_tier() -> None:
    value = _block("\n" + _read(MOD_ROOT / stored_food.SCRIPT_VALUES), "pp_stored_food_tier_target")
    assert "value = pp_stored_food_province_months" in value
    assert "floor = yes" in value and "min = 0" in value and "max = 24" in value
    assert "divide" not in value   # one month per tier


def test_consumption_is_sign_flipped_and_both_scopes_agree() -> None:
    text = "\n" + _read(STORAGE_VALUES)
    consumption = _block(text, "pp_stored_food_province_consumption")
    # the location value food_consumption is negative: the province sum is multiplied by -1
    assert re.search(r"every_location_in_province = \{\s*add = food_consumption\s*\}\s*multiply = -1", consumption)
    months = _block(text, "pp_stored_food_province_months")
    assert "limit = { pp_stored_food_province_consumption > 0 }" in months
    assert "value = province_food" in months and "divide = pp_stored_food_province_consumption" in months
    assert "multiply = 12" in months and "define:NEconomy|GROWTH_FROM_FOOD_MULTIPLIER_MAX" in months
    # the location-scope values the GUI, map mode and chips read delegate to the province ones
    location_consumption = _block(text, "pp_province_monthly_food_consumption")
    assert re.search(r"province \?= \{\s*add = pp_stored_food_province_consumption\s*\}", location_consumption)
    location_months = _block(text, "pp_province_food_storage_months")
    assert re.search(r"province \?= \{\s*add = pp_stored_food_province_months\s*\}", location_months)
    assert "food_consumption" not in location_months
    parse_file(STORAGE_VALUES)


def test_monthly_country_pulse_hook_is_staggered() -> None:
    text = _read(ON_ACTION)
    entries = {entry.key: entry.value for entry in parse_file(ON_ACTION).entries}
    assert set(entries) == {"monthly_country_pulse", "pp_stored_food_country_refresh"}
    pulse = _block("\n" + text, "monthly_country_pulse")
    assert re.search(
        r"on_actions = \{\s*delay = \{ days = \{ 0 29 \} \}\s*pp_stored_food_country_refresh\s*\}", pulse
    )
    assert "effect" not in pulse   # merged into vanilla's pulse: on_actions only
    refresh = _block("\n" + text, "pp_stored_food_country_refresh")
    assert re.search(r"every_province = \{\s*pp_refresh_stored_food_tier = yes\s*\}", refresh)
    assert "no pulsing scripts" in text and "approved by Jan on 2026-10-01" in text


def test_game_start_sets_the_tiers() -> None:
    entries = {entry.key: entry.value for entry in parse_file(GAME_START).entries}
    start = entries["on_game_start"]
    assert isinstance(start, CList)
    on_actions = {entry.key: entry.value for entry in start.entries}["on_actions"]
    assert isinstance(on_actions, CList)
    assert "pp_stored_food_game_start" in on_actions.items
    init = _block("\n" + _read(GAME_START), "pp_stored_food_game_start")
    assert re.search(r"every_country = \{\s*every_province = \{\s*pp_refresh_stored_food_tier = yes\s*\}\s*\}", init)


def test_tooling_reads_the_tier_payload() -> None:
    assert cli._province_food_sales_stored_food_per_year(PROJECT) == PAYLOAD_1_3[
        "local_province_food_sales_output_modifier"
    ]
    assert migration.DYNAMIC_TERMS["food_years"] == PAYLOAD_1_3["local_migration_attraction"]
    # whole months, capped at two years
    assert migration.stored_food_tier_years(0.5 / 12) == 0.0
    assert migration.stored_food_tier_years(13.9 / 12) == pytest.approx(13 / 12)
    assert migration.stored_food_tier_years(5.0) == 2.0
    base = migration.dynamic_attraction(starving=False, pop_k=10, capacity_k=10)
    assert migration.dynamic_attraction(starving=False, pop_k=10, capacity_k=10, food_years=1.0) == pytest.approx(
        base + 0.045
    )


def test_no_dead_1_3_carrier_is_left() -> None:
    offenders = []
    for root in (MOD_ROOT / "in_game", MOD_ROOT / "main_menu/common"):
        for path in sorted(root.rglob("*.txt")):
            if re.search(r"(?<![\w])positive_province_food_growth\s*=", _read(path)):
                offenders.append(str(path.relative_to(MOD_ROOT)))
    assert offenders == []
