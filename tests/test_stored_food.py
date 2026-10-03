"""Stored Food and the store lever (EU5 1.4 carriers of the stored-food effects; docs/historical_growth_calibration.md 6.2)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.syntax import CList

from prosper_or_perish_constructor import cli, provisioning, stored_food
from prosper_or_perish_constructor.worldbuilder import migration

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
ON_ACTION = MOD_ROOT / "in_game/common/on_action/pp_stored_food.txt"
GAME_START = MOD_ROOT / "in_game/common/on_action/pp_game_start.txt"
STORAGE_VALUES = MOD_ROOT / "in_game/common/script_values/pp_province_food_storage.txt"
DEFINES = MOD_ROOT / "loading_screen/common/defines/pp_defines_adjustments.txt"

# Stored Food: the EU5 1.3 positive_province_food_growth values per stored year, growth included (the engine's storage
# term NPop.FOOD_STORAGE_POP_GROWTH is 0 since growth moved onto the modifier). The storage legs it once carried
# (Surplus Sales +8.0, Scarcity Premium -8.0 per year) are gone: the store lever (Low Stores / Full Stores) replaced them.
PAYLOAD_1_3 = {
    "local_population_growth": 0.006,   # 2026-10-03 Mini World calibration (was the 1.3 value 0.0075)
    "local_devastation_recovery": 0.003,
    "local_migration_attraction": 0.045,
    "local_monthly_prosperity": 0.0025,
}
FOOD = "local_local_food_output_modifier"
SALES = "local_province_food_sales_output_modifier"
PURCHASE = "local_province_food_purchase_output_modifier"


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
    # 0.006 per stored year = FOOD_STORAGE_POP_GROWTH 0.012 at the 2-year cap (the 1.3 law was 0.0075 = 0.015)
    config = _config()
    cap_years = _define("GROWTH_FROM_FOOD_MULTIPLIER_MAX")
    assert stored_food.growth_per_year(config) * cap_years == pytest.approx(0.012)
    # the engine's own storage term would add the growth a second time
    assert _define("FOOD_STORAGE_POP_GROWTH") == 0
    assert _define("FOOD_SURPLUS_POP_GROWTH") == 0


def test_store_lever_moves_province_food_staples_and_surplus_sales() -> None:
    config = _config()
    low, full = stored_food.low_payload(config), stored_food.full_payload(config)
    assert config.pivot_months == 12
    # Province Food is worth more below the pivot and less above, by the same slope; some output is left at the cap
    assert low[FOOD] > 0 and full[FOOD] == -low[FOOD]
    assert -1 < full[FOOD] < 0
    # Surplus Sales (the Grange's leg) grow above the pivot and are gone at most 6 months below it
    assert full[SALES] > 0 and low[SALES] <= -2
    # staples: no store lever on them (farm v3: the crop farms' ai_construct_weight reads the crop output modifier as
    # land quality, so a store-driven staple bonus would make the AI build farms where the store is full)
    goods = stored_food.staple_goods()
    assert set(goods) == set(provisioning.PROVISIONED_GOOD_BY_BUILDING.values()) and len(goods) == len(set(goods))
    staples = {f"local_{good}_output_modifier" for good in goods}
    assert not staples & set(low) and not staples & set(full)
    # no victuals line (2026-10-03): the harbour Yard takes no store food, the Grange stops by its Surplus Sales
    assert set(low) == {FOOD, SALES} and set(full) == {FOOD, SALES}
    # nothing of the old storage legs is left on Stored Food, and no Scarcity Premium anywhere
    assert not {FOOD, SALES, PURCHASE} & set(stored_food.payload(config))
    assert PURCHASE not in low and PURCHASE not in full


def test_one_step_modifier_per_stored_month_carries_every_effect() -> None:
    """2026-10-03: one province modifier per whole stored month (0..24); a province carries exactly one, with its true
    values. Each line is the exact continuous value at that month, rounded once to five decimals."""
    config = _config()
    text = _read(MOD_ROOT / stored_food.STATIC_MODIFIERS)
    assert stored_food.STEPS == 2 * 12 == _define("GROWTH_FROM_FOOD_MULTIPLIER_MAX") * 12
    pivot = int(config.pivot_months)
    low, full, per_year = dict(config.low), dict(config.full), dict(config.per_year)
    previous: dict[str, float] | None = None
    for step in range(stored_food.STEPS + 1):
        block = _block("\n" + text, f"pp_food_store_{step}")
        assert "game_data = { category = province }" in block
        values = {k: float(v) for k, v in re.findall(r"^\t(local_\w+) = (-?[\d.]+)$", block, flags=re.MULTILINE)}
        assert values == stored_food.step_payload(config, step), step
        assert all(len(v.split(".")[1]) <= 5 for v in re.findall(r"= (-?[\d.]+)$", block, flags=re.MULTILINE))
        # every line within half a fixed-point step of the exact value
        for key in set(per_year) | set(low) | set(full):
            exact = per_year.get(key, 0.0) * step / 12
            exact += low.get(key, 0.0) * max(pivot - step, 0) / 12 + full.get(key, 0.0) * max(step - pivot, 0) / 12
            assert abs(values.get(key, 0.0) - exact) <= 0.000005 + 1e-12, (step, key)
        # the Stored Food lines only grow with the store; Province Food output only falls
        if previous is not None:
            for key in per_year:
                assert values[key] >= previous.get(key, 0.0), (step, key)
            assert values.get(FOOD, 0.0) < previous.get(FOOD, 0.0), step
        previous = values
    # the ends and the pivot are exact: an empty store is the whole Low Stores year, the pivot carries no lever line,
    # the cap is two Stored Food years plus the whole Full Stores year
    assert stored_food.step_payload(config, 0) == stored_food.low_payload(config)
    assert stored_food.step_payload(config, pivot) == PAYLOAD_1_3
    cap = stored_food.step_payload(config, 24)
    assert cap == {**{k: 2 * v for k, v in PAYLOAD_1_3.items()}, **stored_food.full_payload(config)}
    # the scaled carriers of 2026-10-01..03 are gone from the effects
    for name in stored_food.LEGACY_SCALED:
        assert f"\n{name} = {{ game_data = {{ category = province }} }}" in "\n" + text
    parse_file(MOD_ROOT / stored_food.STATIC_MODIFIERS)


def test_no_country_base_value_belongs_to_the_store_lever() -> None:
    # the lever is zero at the pivot: the old constants (-1.0 sales, +15.0 purchase, +19.0 offset) must not come back
    text = _read(MOD_ROOT / "in_game/common/auto_modifiers/pp_country_base_values.txt")
    for good in ("province_food_sales", "province_food_purchase", "offset", "local_food"):
        assert not re.search(rf"^\s*global_{good}_output_modifier\s*=", text, flags=re.MULTILINE), good


def test_old_save_tier_names_stay_defined_without_effects() -> None:
    text = _read(MOD_ROOT / stored_food.STATIC_MODIFIERS)
    names = re.findall(r"^(pp_stored_food_tier_\d+) = \{ game_data = \{ category = province \} \}$", text, flags=re.MULTILINE)
    assert names == [f"pp_stored_food_tier_{t}" for t in range(1, 25)]
    scaled = re.findall(r"^(pp_\w+) = \{ game_data = \{ category = province \} \}$", text, flags=re.MULTILINE)
    assert set(stored_food.LEGACY_SCALED) <= set(scaled)
    loc = _read(MOD_ROOT / stored_food.LOCALIZATION)
    for name in [f"pp_stored_food_tier_{t}" for t in range(1, 25)] + list(stored_food.LEGACY_SCALED):
        assert f"\n  STATIC_MODIFIER_NAME_{name}:" in loc


def test_generated_files_match_the_configuration_and_the_tier_files_are_gone() -> None:
    result = stored_food.apply(PROJECT, MOD_ROOT, write=False)
    assert result.changed == ()
    for path in stored_food.LEGACY_FILES:
        assert not (MOD_ROOT / path).exists()


def test_localization_names_each_step_without_numbers_in_the_description() -> None:
    loc = _read(MOD_ROOT / stored_food.LOCALIZATION)
    assert '  STATIC_MODIFIER_NAME_pp_food_store_0: "Stored Food: almost empty"' in loc
    assert '  STATIC_MODIFIER_NAME_pp_food_store_1: "Stored Food: 1 month"' in loc
    assert '  STATIC_MODIFIER_NAME_pp_food_store_24: "Stored Food: 24 months"' in loc
    for step in range(stored_food.STEPS + 1):
        assert f'\n  STATIC_MODIFIER_DESC_pp_food_store_{step}: "{stored_food.DESCRIPTION}"' in loc
    for text in (stored_food.DESCRIPTION, stored_food.LEGACY_DESCRIPTION):
        assert not re.search(r"\d", text)
        assert "[" not in text and "#" not in text


def test_refresh_picks_the_nearest_step_with_hysteresis() -> None:
    effect = _block("\n" + _read(MOD_ROOT / stored_food.SCRIPTED_EFFECTS), "pp_refresh_stored_food")
    # the location loop runs once per refresh; province_food is divided by the stored local
    assert effect.count("pp_stored_food_province_consumption") == 1
    assert "pp_stored_food_province_months" not in effect
    assert "value = { value = pp_stored_food_province_consumption add = 100 }" in effect
    assert "divide = { value = local_var:pp_stored_food_consumption subtract = 100 }" in effect
    assert "min = 0" in effect and "max = { value = define:NEconomy|GROWTH_FROM_FOOD_MULTIPLIER_MAX multiply = 12 }" in effect
    # the stored months for the AI weights: re-set past the deadband or when the store emptied
    assert "local_var:pp_stored_food_change > 100.05" in effect and "local_var:pp_stored_food_change < 99.95" in effect
    assert "AND = { local_var:pp_stored_food_target < 100.00001 var:pp_stored_food_months > 100.00001 }" in effect
    assert "set_variable = { name = pp_stored_food_months value = local_var:pp_stored_food_target }" in effect
    # the step: nearest whole month (half rounds up), re-picked only half a month + the deadband away from the carried
    # step, so a store on a boundary does not flip back and forth
    assert ("limit = { OR = { local_var:pp_food_store_change > 100.55 local_var:pp_food_store_change < 99.45 } }" in effect)
    assert ("set_local_variable = { name = pp_food_store_new value = { value = local_var:pp_stored_food_target "
            "add = 0.5 floor = yes max = 124 } }") in effect
    change = effect[effect.index("local_var:pp_food_store_change > 100.55"):effect.index("# nobody eats here")]
    adds = re.findall(r"(if|else_if|else) = \{ (?:limit = \{ local_var:pp_food_store_new < ([\d.]+) \} )?"
                      r"add_province_modifier = \{ modifier = pp_food_store_(\d+) \} \}", change)
    assert [int(step) for _, _, step in adds] == list(range(25))
    assert [float(bound) for _, bound, _ in adds[:-1]] == [100.5 + s for s in range(24)]
    assert adds[0][0] == "if" and adds[-1][0] == "else" and adds[-1][1] == ""
    # every step is dropped before the new one is added, and the carried step is stored
    first_add = change.index("add_province_modifier")
    for step in range(25):
        drop = f"if = {{ limit = {{ has_province_modifier = pp_food_store_{step} }} remove_province_modifier = pp_food_store_{step} }}"
        assert change.index(drop) < first_add
    assert "set_variable = { name = pp_food_store_step value = local_var:pp_food_store_new }" in change
    # only where people eat; elsewhere no step at all
    assert "limit = { local_var:pp_stored_food_consumption > 100 }\n\t\tset_local_variable = { name = pp_food_store_change" in effect
    nobody = effect[effect.index("# nobody eats here"):]
    assert "limit = { var:pp_food_store_step > 99.5 }" in nobody and "set_variable = { name = pp_food_store_step value = 99 }" in nobody
    assert nobody.count("remove_province_modifier = pp_food_store_") == 25
    # never refreshed: below every store, so the first refresh applies both
    for variable in ("pp_stored_food_months", "pp_food_store_step"):
        assert f"limit = {{ NOT = {{ has_variable = {variable} }} }}\n\t\tset_variable = {{ name = {variable} value = 50 }}" in effect
    # old saves: the scaled modifiers and the single-modifier version's variable go
    for name in stored_food.LEGACY_SCALED:
        assert f"if = {{ limit = {{ has_province_modifier = {name} }} remove_province_modifier = {name} }}" in effect
    assert "if = { limit = { has_variable = pp_stored_food_size } remove_variable = pp_stored_food_size }" in effect
    assert "size =" not in effect.split("pp_refresh_farm_produce")[0]
    # +100 offsets (a variable at 0 counts as unset) and no `var:x = n` (a scope comparison in game)
    assert not re.search(r"var:\w+ = ", effect)
    parse_file(MOD_ROOT / stored_food.SCRIPTED_EFFECTS)   # well formed


def _step(months: float, carried: int | None) -> int | None:
    """The refresh's step rule in Python: the step after a refresh at ``months`` while ``carried`` is on."""
    if carried is not None and abs(months - carried) <= 0.5 + 0.05:
        return carried
    return min(int(months + 0.5), 24)


def test_step_rule_rounds_to_the_nearest_month_and_holds_on_boundaries() -> None:
    assert [_step(m, None) for m in (0.0, 0.49, 0.5, 11.5, 11.49, 23.6, 24.0)] == [0, 0, 1, 12, 11, 24, 24]
    # a store sitting on a boundary keeps its step until it is clearly past it
    assert _step(12.53, 12) == 12 and _step(12.56, 12) == 13 and _step(11.46, 12) == 12 and _step(11.44, 12) == 11
    # an emptied store always lands on step 0
    assert _step(0.0, 1) == 0 and _step(0.0, 24) == 0


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


def test_display_values_read_the_carried_step() -> None:
    text = "\n" + _read(MOD_ROOT / stored_food.SCRIPT_VALUES)
    years = _block(text, "pp_stored_food_years")
    assert re.search(
        r"province \?= \{\s*if = \{\s*limit = \{ has_variable = pp_food_store_step var:pp_food_store_step > 99.5 \}\s*"
        r"add = var:pp_food_store_step\s*subtract = 100\s*\}\s*\}\s*divide = 12\s*min = 0",
        years,
    )
    growth = _block(text, "pp_province_food_storage_growth")
    assert "value = pp_stored_food_years" in growth and "multiply = 0.006" in growth
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
    # the legacy Surplus Sales check reads the leg where it lives now: Full Stores, per year above the pivot
    assert cli._province_food_sales_stored_food_per_year(PROJECT) == stored_food.full_payload(_config())[SALES]
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
