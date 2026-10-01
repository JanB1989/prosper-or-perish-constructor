"""Stored Food (EU5 1.4 carrier of the 1.3 stored-food effects; docs/historical_growth_calibration.md 6.2)."""

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
# NPop.FOOD_STORAGE_POP_GROWTH is 0 since growth moved onto the modifier).
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
    assert stored_food.payload(config) == PAYLOAD_1_3   # five decimals hold every per-year value exactly


def test_growth_rides_the_modifier_and_the_engine_term_is_off() -> None:
    # same law as the old define term: 0.0075 per stored year = FOOD_STORAGE_POP_GROWTH 0.015 at the 2-year cap
    config = _config()
    cap_years = _define("GROWTH_FROM_FOOD_MULTIPLIER_MAX")
    assert stored_food.growth_per_year(config) * cap_years == pytest.approx(0.015)
    # the engine's own storage term would add the growth a second time
    assert _define("FOOD_STORAGE_POP_GROWTH") == 0
    assert _define("FOOD_SURPLUS_POP_GROWTH") == 0


def test_one_scaled_modifier_carries_one_stored_year() -> None:
    text = _read(MOD_ROOT / stored_food.STATIC_MODIFIERS)
    block = _block("\n" + text, "pp_stored_food")
    assert "game_data = { category = province }" in block
    values = dict(re.findall(r"^\t(local_\w+) = (-?[\d.]+)$", block, flags=re.MULTILINE))
    assert {key: float(value) for key, value in values.items()} == PAYLOAD_1_3
    assert all(len(value.split(".")[1]) <= 5 for value in values.values())   # EU5 1.4 rejects six decimals
    parse_file(MOD_ROOT / stored_food.STATIC_MODIFIERS)


def test_old_save_tier_names_stay_defined_without_effects() -> None:
    text = _read(MOD_ROOT / stored_food.STATIC_MODIFIERS)
    names = re.findall(r"^(pp_stored_food_tier_\d+) = \{ game_data = \{ category = province \} \}$", text, flags=re.MULTILINE)
    assert names == [f"pp_stored_food_tier_{t}" for t in range(1, 25)]
    loc = _read(MOD_ROOT / stored_food.LOCALIZATION)
    for tier in range(1, 25):
        assert f"\n  STATIC_MODIFIER_NAME_pp_stored_food_tier_{tier}:" in loc


def test_generated_files_match_the_configuration_and_the_tier_files_are_gone() -> None:
    result = stored_food.apply(PROJECT, MOD_ROOT, write=False)
    assert result.changed == ()
    for path in stored_food.LEGACY_FILES:
        assert not (MOD_ROOT / path).exists()


def test_localization_names_the_modifier_without_numbers_in_the_description() -> None:
    loc = _read(MOD_ROOT / stored_food.LOCALIZATION)
    assert '  STATIC_MODIFIER_NAME_pp_stored_food: "Stored Food"' in loc
    assert "\n  STATIC_MODIFIER_DESC_pp_stored_food:" in loc
    for text in (stored_food.DESCRIPTION, stored_food.LEGACY_DESCRIPTION):
        assert not re.search(r"\d", text)
        assert "[" not in text and "#" not in text


def test_refresh_works_out_consumption_once_and_scales_the_modifier() -> None:
    effect = _block("\n" + _read(MOD_ROOT / stored_food.SCRIPTED_EFFECTS), "pp_refresh_stored_food")
    # the location loop runs once per refresh; province_food is divided by the stored local
    assert effect.count("pp_stored_food_province_consumption") == 1
    assert "pp_stored_food_province_months" not in effect
    assert "value = { value = pp_stored_food_province_consumption add = 100 }" in effect
    assert "divide = { value = local_var:pp_stored_food_consumption subtract = 100 }" in effect
    assert "min = 0" in effect and "max = { value = define:NEconomy|GROWTH_FROM_FOOD_MULTIPLIER_MAX multiply = 12 }" in effect
    # size = stored years (the payload is per year), applied only from the change branch
    add = (
        "add_province_modifier = { modifier = pp_stored_food size = { value = local_var:pp_stored_food_target "
        "subtract = 100 divide = 12 } }"
    )
    assert effect.count(add) == 1
    change = effect[effect.index("local_var:pp_stored_food_change > 100.05") :]
    assert add in change and "remove_province_modifier = pp_stored_food }" in change
    assert "set_variable = { name = pp_stored_food_size value = local_var:pp_stored_food_target }" in change
    # deadband both ways, and an emptied store always drops the modifier
    assert "local_var:pp_stored_food_change < 99.95" in effect
    assert "AND = { local_var:pp_stored_food_target < 100.00001 var:pp_stored_food_size > 100.00001 }" in effect
    # +100 offsets (a variable at 0 counts as unset) and no `var:x = n` (a scope comparison in game)
    assert not re.search(r"var:\w+ = ", effect)
    parse_file(MOD_ROOT / stored_food.SCRIPTED_EFFECTS)   # well formed


def test_refresh_clears_old_save_tiers_once() -> None:
    effect = _block("\n" + _read(MOD_ROOT / stored_food.SCRIPTED_EFFECTS), "pp_refresh_stored_food")
    legacy = effect[: effect.index("set_local_variable")]
    assert "limit = { has_variable = pp_stored_food_tier }" in legacy
    for tier in range(1, 25):
        name = f"pp_stored_food_tier_{tier}"
        assert f"if = {{ limit = {{ has_province_modifier = {name} }} remove_province_modifier = {name} }}" in legacy
    for variable in stored_food.LEGACY_VARIABLES:
        assert f"if = {{ limit = {{ has_variable = {variable} }} remove_variable = {variable} }}" in legacy
    assert "add_province_modifier" not in legacy


def test_display_values_read_the_applied_size() -> None:
    text = "\n" + _read(MOD_ROOT / stored_food.SCRIPT_VALUES)
    years = _block(text, "pp_stored_food_years")
    assert re.search(
        r"province \?= \{\s*if = \{\s*limit = \{ has_variable = pp_stored_food_size \}\s*"
        r"add = var:pp_stored_food_size\s*subtract = 100\s*\}\s*\}\s*divide = 12",
        years,
    )
    growth = _block(text, "pp_province_food_storage_growth")
    assert "value = pp_stored_food_years" in growth and "multiply = 0.0075" in growth
    assert "FOOD_STORAGE_POP_GROWTH" not in growth
    # the hand-written storage values no longer model an engine term
    storage = "\n" + _read(STORAGE_VALUES)
    assert "\npp_province_food_storage_growth = {" not in storage
    assert re.search(r"pp_population_growth_map_value = \{\s*value = modifier:local_population_growth\s*\}", storage)
    parse_file(MOD_ROOT / stored_food.SCRIPT_VALUES)


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
    assert re.search(r"every_province = \{\s*pp_refresh_stored_food = yes\s*\}", refresh)
    assert "no pulsing scripts" in text and "approved by Jan on 2026-10-01" in text


def test_game_start_sets_the_modifier() -> None:
    entries = {entry.key: entry.value for entry in parse_file(GAME_START).entries}
    start = entries["on_game_start"]
    assert isinstance(start, CList)
    on_actions = {entry.key: entry.value for entry in start.entries}["on_actions"]
    assert isinstance(on_actions, CList)
    assert "pp_stored_food_game_start" in on_actions.items
    init = _block("\n" + _read(GAME_START), "pp_stored_food_game_start")
    assert re.search(r"every_country = \{\s*every_province = \{\s*pp_refresh_stored_food = yes\s*\}\s*\}", init)


def test_tooling_reads_the_payload() -> None:
    assert cli._province_food_sales_stored_food_per_year(PROJECT) == PAYLOAD_1_3[
        "local_province_food_sales_output_modifier"
    ]
    assert migration.DYNAMIC_TERMS["food_years"] == PAYLOAD_1_3["local_migration_attraction"]
    # continuous, capped at two years
    assert migration.stored_food_years(0.3 / 12) == pytest.approx(0.3 / 12)
    assert migration.stored_food_years(13.9 / 12) == pytest.approx(13.9 / 12)
    assert migration.stored_food_years(5.0) == 2.0 and migration.stored_food_years(-1.0) == 0.0
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
