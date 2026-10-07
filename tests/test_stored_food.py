"""Stored Food and the store lever (EU5 1.4 carriers of the stored-food effects; docs/historical_growth_calibration.md 6.2)."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest
from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.syntax import CList

from prosper_or_perish_constructor import cli, provisioning, staple_foods, stored_food
from prosper_or_perish_constructor.worldbuilder import migration

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
ON_ACTION = MOD_ROOT / "in_game/common/on_action/pp_stored_food.txt"
GAME_START = MOD_ROOT / "in_game/common/on_action/pp_game_start.txt"
STORAGE_VALUES = MOD_ROOT / "in_game/common/script_values/pp_province_food_storage.txt"
DEFINES = MOD_ROOT / "loading_screen/common/defines/pp_defines_adjustments.txt"

# Stored Food: the EU5 1.3 positive_province_food_growth values per stored year (the engine's storage term
# NPop.FOOD_STORAGE_POP_GROWTH is 0 since growth moved onto the modifier). The storage legs it once carried
# (Surplus Sales +8.0 per year) are gone: the store lever (Low Stores / Full Stores) replaced them. Growth has its own
# month table (growth_by_month, 2026-10-06).
PAYLOAD_1_3 = {
    "local_devastation_recovery": 0.003,
    "local_migration_attraction": 0.045,
    "local_monthly_prosperity": 0.0025,
}
GROWTH = "local_population_growth"
# growth by stored month (2026-10-06, Jan): +0.05 %/yr per month to 18 months (the 2026-10-03 law, 0.006 per stored
# year), then +0.04, +0.04, +0.03 x 4 to a round 1.10 % at the 24-month cap
GROWTH_BY_STEP = [round(0.0005 * s, 5) for s in range(19)] + [0.0094, 0.0098, 0.0101, 0.0104, 0.0107, 0.011]
FOOD = "local_local_food_output_modifier"
SALES = "local_province_food_sales_output_modifier"


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
    # the steps carry the growth table exactly; it never falls and tapers above 18 months
    config = _config()
    assert stored_food.growth_by_step(config) == GROWTH_BY_STEP
    assert GROWTH not in dict(config.per_year)
    increments = [round(b - a, 5) for a, b in zip(GROWTH_BY_STEP, GROWTH_BY_STEP[1:])]
    assert increments[:18] == [0.0005] * 18 and all(0 < i < 0.0005 for i in increments[18:])
    # the engine's own storage term would add the growth a second time
    assert _define("FOOD_STORAGE_POP_GROWTH") == 0
    assert _define("FOOD_SURPLUS_POP_GROWTH") == 0


def _curve_exact(config: stored_food.StoredFoodConfig, months: float) -> dict[str, float]:
    """The store curve at ``months``, recomputed here from the knots (float), for checking the generated steps."""
    knots = list(config.food_curve)

    def share(m: float) -> float:
        for (m0, s0), (m1, s1) in zip(knots, knots[1:]):
            if m <= m1:
                return s0 + (s1 - s0) * (m - m0) / (m1 - m0)
        return knots[-1][1]

    food = share(months) / share(config.pivot_months) - 1
    lines = {FOOD: food}
    lines.update({f"local_{good}_output_modifier": config.factor(good) * food for good in config.staple_goods})
    return lines


def test_store_lever_moves_province_food_staples_and_surplus_sales() -> None:
    config = _config()
    low, full = stored_food.low_payload(config), stored_food.full_payload(config)
    assert config.pivot_months == 12
    # Surplus Sales (the Grange's leg) grow above the pivot and are gone at most 6 months below it; they are the only
    # linear lever left: Province Food and the staples follow the store curve (2026-10-03)
    assert full[SALES] > 0 and low[SALES] <= -2
    # defensiveness: -24 % at an empty store, +24 % at 24 months, 2 % per month around the pivot (2026-10-05, Jan)
    assert set(low) == {SALES, "local_defensive"} and set(full) == {SALES, "local_defensive"}
    assert low["local_defensive"] == -0.24 and full["local_defensive"] == 0.24
    # the store curve: Jan's shares of an empty store's Province Food output (100 / 80 / 65 / 50 / 40 % at 0 / 6 / 12 /
    # 18 / 24 months), so the output modifier runs +53.8 % .. 0 .. -38.5 %; some output is left at the cap
    assert config.food_curve == ((0.0, 1.0), (6.0, 0.8), (12.0, 0.65), (18.0, 0.5), (24.0, 0.4))
    assert stored_food.province_food_line(config, 0) == pytest.approx(1 / 0.65 - 1)
    assert stored_food.province_food_line(config, 24) == pytest.approx(0.4 / 0.65 - 1)
    # staple foods (the farm trade-off, Jan 2026-10-03; every staple food since 2026-10-04): one line per staple food,
    # opposite to Province Food; the crop farm goods share 0.40 of it, the buy-back goods have their own factor
    assert config.staple_factor == -0.40
    assert config.staple_goods == staple_foods.staple_foods() and len(config.staple_goods) == 13
    farm_goods = {crop["good"] for crop in tomllib.loads((ROOT / "config/crop_farms.toml").read_text())["crops"]}
    assert farm_goods < set(config.staple_goods) and "victuals" not in config.staple_goods
    assert {good: config.factor(good) for good in farm_goods} == dict.fromkeys(farm_goods, -0.40)
    assert dict(config.staple_factor_by_good) == {"fish": -0.20, "fruit": -0.21, "wild_game": -0.14, "wool": -0.23, "camels": -0.16}
    for months in range(25):
        assert stored_food.staple_line(config, months) == pytest.approx(-0.40 * stored_food.province_food_line(config, months))
        for good in config.staple_goods:
            assert stored_food.staple_line(config, months, good) == pytest.approx(
                config.factor(good) * stored_food.province_food_line(config, months))
    # the old staple_output switch stays available for the provisioned goods, but nothing uses it any more
    goods = stored_food.staple_goods()
    assert set(goods) == set(provisioning.PROVISIONED_GOOD_BY_BUILDING.values()) and len(goods) == len(set(goods))
    # nothing of the old storage legs is left on Stored Food
    assert not {FOOD, SALES} & set(stored_food.payload(config))


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
        curve = _curve_exact(config, step)
        for key in set(per_year) | set(low) | set(full) | set(curve) | {GROWTH}:
            exact = per_year.get(key, 0.0) * step / 12 + (GROWTH_BY_STEP[step] if key == GROWTH else 0.0)
            exact += low.get(key, 0.0) * max(pivot - step, 0) / 12 + full.get(key, 0.0) * max(step - pivot, 0) / 12
            exact += curve.get(key, 0.0)
            assert abs(values.get(key, 0.0) - exact) <= 0.000005 + 1e-12, (step, key)
        # every crop farm good carries the same crop line, opposite to Province Food (the others their own factor's)
        farm = sorted(g for g in config.staple_goods if config.factor(g) == config.staple_factor)
        staples = {values.get(f"local_{good}_output_modifier", 0.0) for good in farm}
        assert len(staples) == 1, step
        for good in config.staple_goods:
            assert (values.get(f"local_{good}_output_modifier", 0.0) > 0) == (step > pivot), (step, good)
        # the Stored Food lines only grow with the store; Province Food output only falls, the staples only rise
        if previous is not None:
            for key in [*per_year, GROWTH]:
                assert values[key] >= previous.get(key, 0.0), (step, key)
            assert values.get(FOOD, 0.0) < previous.get(FOOD, 0.0), step
            assert staples.pop() > previous.get(f"local_{farm[0]}_output_modifier", 0.0), step
        previous = values
    # the ends and the pivot: an empty store is the whole Low Stores year plus the curve at 0, the pivot carries no lever
    # or curve line, the cap is two Stored Food years plus the whole Full Stores year plus the curve at 24
    rounded = lambda lines: {k: round(v, 5) for k, v in lines.items()}   # noqa: E731
    assert stored_food.step_payload(config, 0) == {**stored_food.low_payload(config), **rounded(_curve_exact(config, 0))}
    assert stored_food.step_payload(config, pivot) == {**PAYLOAD_1_3, GROWTH: 0.006}
    cap = stored_food.step_payload(config, 24)
    assert cap == {**{k: 2 * v for k, v in PAYLOAD_1_3.items()}, GROWTH: 0.011, **stored_food.full_payload(config),
                   **rounded(_curve_exact(config, 24))}
    parse_file(MOD_ROOT / stored_food.STATIC_MODIFIERS)


def test_no_country_base_value_belongs_to_the_store_lever() -> None:
    # the lever is zero at the pivot: the old constants (-1.0 sales, +19.0 offset) must not come back
    text = _read(MOD_ROOT / "in_game/common/auto_modifiers/pp_country_base_values.txt")
    for good in ("province_food_sales", "offset", "local_food"):
        assert not re.search(rf"^\s*global_{good}_output_modifier\s*=", text, flags=re.MULTILINE), good


def test_no_old_save_carriers_remain() -> None:
    # 2026-10-06 (Jan): the mod is not save compatible across versions, so the earlier carriers (whole-month tiers,
    # the scaled Stored Food / Low Stores / Full Stores and their variables) are neither defined nor cleaned up
    modifiers = _read(MOD_ROOT / stored_food.STATIC_MODIFIERS)
    names = re.findall(r"^(\w+) = \{", modifiers, flags=re.MULTILINE)
    assert names == [stored_food.step_name(step) for step in range(stored_food.STEPS + 1)]
    for path in (stored_food.SCRIPTED_EFFECTS, stored_food.LOCALIZATION, stored_food.SCRIPT_VALUES):
        text = _read(MOD_ROOT / path)
        for name in ("pp_stored_food_tier", "pp_low_stores", "pp_full_stores", "pp_stored_food_size"):
            assert name not in text, (path, name)
        assert not re.search(r"\bpp_stored_food\b", text), path


def test_generated_files_match_the_configuration() -> None:
    result = stored_food.apply(PROJECT, MOD_ROOT, write=False)
    assert result.changed == ()


def test_every_step_modifier_has_the_stored_food_icon() -> None:
    # 2026-10-05 (Jan): the province modifier row drew the steps with the engine's generic icon; the engine reads a
    # static modifier's icon from icons/modifiers/<key>.dds, so each step carries the Stored Food chip's icon
    icons = {(MOD_ROOT / stored_food.step_icon(step)).read_bytes() for step in range(stored_food.STEPS + 1)}
    assert len(icons) == 1 and next(iter(icons))[:4] == b"DDS "
    assert stored_food.STEP_ICON_SOURCE.as_posix().endswith("flat_icons/trade_market/food_stockpile.dds")
    chip = (ROOT / "src/prosper_or_perish_constructor/location_status.py").read_text(encoding="utf-8")
    assert "flat_icons/trade_market/food_stockpile.dds" in chip


def test_localization_names_each_step_without_numbers_in_the_description() -> None:
    loc = _read(MOD_ROOT / stored_food.LOCALIZATION)
    assert '  STATIC_MODIFIER_NAME_pp_food_store_0: "Stored Food: almost empty"' in loc
    assert '  STATIC_MODIFIER_NAME_pp_food_store_1: "Stored Food: 1 month"' in loc
    assert '  STATIC_MODIFIER_NAME_pp_food_store_24: "Stored Food: 24 months"' in loc
    for step in range(stored_food.STEPS + 1):
        assert f'\n  STATIC_MODIFIER_DESC_pp_food_store_{step}: "{stored_food.DESCRIPTION}"' in loc
    assert not re.search(r"\d", stored_food.DESCRIPTION)
    assert "[" not in stored_food.DESCRIPTION and "#" not in stored_food.DESCRIPTION


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
    # the carried step's modifier goes before the new one is added, and the carried step is stored
    assert change.index("remove_province_modifier") < change.index("add_province_modifier")
    assert "set_variable = { name = pp_food_store_step value = local_var:pp_food_store_new }" in change
    swap = _find_block(_effect_tree(), "pp_food_store_new")
    for carried in range(25):
        for new in (0, carried, 24 - carried):
            values = {"var:pp_food_store_step": 100 + carried, "local_var:pp_food_store_new": 100 + new}
            assert _walk(swap, values) == [("remove_province_modifier", f"pp_food_store_{carried}"),
                                           ("add_province_modifier", f"pp_food_store_{new}")], values
    # never refreshed (50) or no step (99): nothing to remove
    for unset in (50, 99):
        values = {"var:pp_food_store_step": unset, "local_var:pp_food_store_new": 107}
        assert _walk(swap, values) == [("add_province_modifier", "pp_food_store_7")]
    # halving: at most five comparisons deep for 25 steps (removal adds the "carries a step" guard)
    assert _depth(swap, "local_var:pp_food_store_new") == 5
    assert _depth(swap, "var:pp_food_store_step") == 1 + 5
    # only where people eat; elsewhere no step at all
    assert "limit = { local_var:pp_stored_food_consumption > 100 }\n\t\tset_local_variable = { name = pp_food_store_change" in effect
    nobody = effect[effect.index("# nobody eats here"):]
    assert "limit = { var:pp_food_store_step > 99.5 }" in nobody and "set_variable = { name = pp_food_store_step value = 99 }" in nobody
    assert nobody.count("remove_province_modifier = pp_food_store_") == 25   # one leaf per step, the carried one runs
    # never refreshed: below every store, so the first refresh applies both
    for variable in ("pp_stored_food_months", "pp_food_store_step"):
        assert f"limit = {{ NOT = {{ has_variable = {variable} }} }}\n\t\tset_variable = {{ name = {variable} value = 50 }}" in effect
    assert "has_province_modifier" not in effect   # no old-save cleanup, no check per step
    assert "size =" not in effect
    assert "pp_farm_produce" not in effect   # Farm Produce removed 2026-10-03 (the farm-based Cookshop cap is the reward)
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


def _effect_tree() -> CList:
    return parse_file(MOD_ROOT / stored_food.SCRIPTED_EFFECTS).values("pp_refresh_stored_food")[0]


def _find_block(block: CList, local: str) -> CList | None:
    """The block that sets the local ``local`` (the step swap) and then acts on it."""
    for entry in block.entries:
        if entry.key == "set_local_variable" and isinstance(entry.value, CList) and entry.value.first("name") == local:
            return block
        if isinstance(entry.value, CList):
            found = _find_block(entry.value, local)
            if found is not None:
                return found
    return None


def _limit_holds(limit: CList, values: dict[str, float]) -> bool:
    """A limit of plain `<key> < n` / `<key> > n` comparisons on the walked variables (anything else: not taken)."""
    for entry in limit.entries:
        if entry.key not in values or entry.op not in ("<", ">"):
            return False
        if not (values[entry.key] < float(entry.value) if entry.op == "<" else values[entry.key] > float(entry.value)):
            return False
    return True


def _walk(block: CList, values: dict[str, float]) -> list[tuple[str, str]]:
    """Runs the if / else trees of ``block`` on ``values``; the modifier effects reached, in order."""
    hits: list[tuple[str, str]] = []
    taken = True
    for entry in block.entries:
        if entry.key == "remove_province_modifier":
            hits.append((entry.key, str(entry.value)))
        elif entry.key == "add_province_modifier":
            hits.append((entry.key, str(entry.value.first("modifier"))))
        elif entry.key == "if":
            taken = _limit_holds(entry.value.first("limit"), values)
            if taken:
                hits += _walk(entry.value, values)
        elif entry.key == "else":
            if not taken:
                hits += _walk(entry.value, values)
            taken = True
    return hits


def _depth(block: CList, key: str) -> int:
    """The longest chain of nested comparisons on ``key`` in ``block``."""
    best = 0
    for entry in block.entries:
        if entry.key in ("if", "else") and isinstance(entry.value, CList):
            limit = entry.value.first("limit")
            own = int(isinstance(limit, CList) and any(item.key == key for item in limit.entries))
            best = max(best, own + _depth(entry.value, key))
    return best


def test_display_values_read_the_carried_step() -> None:
    text = "\n" + _read(MOD_ROOT / stored_food.SCRIPT_VALUES)
    years = _block(text, "pp_stored_food_years")
    assert re.search(
        r"province \?= \{\s*if = \{\s*limit = \{ has_variable = pp_food_store_step var:pp_food_store_step > 99.5 \}\s*"
        r"add = var:pp_food_store_step\s*subtract = 100\s*\}\s*\}\s*divide = 12\s*min = 0",
        years,
    )
    growth = _block(text, "pp_province_food_storage_growth")
    # one branch per step, the step's growth as written (growth_by_month)
    assert "else_if = { limit = { var:pp_food_store_step < 118.5 } add = 0.009 }" in growth
    assert "else_if = { limit = { var:pp_food_store_step < 119.5 } add = 0.0094 }" in growth
    assert "else = { add = 0.011 }" in growth and growth.count("add = ") == stored_food.STEPS + 1
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
