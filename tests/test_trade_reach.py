"""Trade reach (2026-11-24, Jan): nations built for trade get better at it over time; a nation that is not trade focused
cannot jump in with gold. The mellow variant.

The flat trade range of the researched advances counts by pp_trade_reach (0.5..1) from points per country: burghers
(10 per percent above 1.5 %, at most 45), seafaring (40 x the maritime reach), capital economy (up to 30), plutocracy,
naval and free subjects (up to 15 each), people in towns and cities (0.5 per percent, at most 15) and trade buildings at
home (15 at 4 levels per 100,000 people); full at 150 points, at least half always, landless countries the floor. The
auto modifier pp_limited_trade_reach takes the rest off. The raw reach (no floor) sets the merchant house cap
1 + 7 x raw. These tests pin the rule's numbers, keep the advance list in step with the game's advances and check that
every building type the points read exists.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest
from eu5gameparser.clausewitz.parser import parse_text
from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.load_order import load_merged_directory, load_profile

ROOT = Path(__file__).resolve().parents[1]
LOAD_ORDER = ROOT / "constructor.load_order.toml"
MOD_ROOT = ROOT / "mod" / "pp"
COMMON = MOD_ROOT / "in_game" / "common"
VALUES = COMMON / "script_values" / "pp_trade_reach_values.txt"
MARITIME = COMMON / "script_values" / "pp_maritime_reach_values.txt"
AUTO = COMMON / "auto_modifiers" / "pp_trade_reach.txt"
EFFECTS = COMMON / "scripted_effects" / "pp_trade_reach_effects.txt"
ON_ACTION = COMMON / "on_action" / "pp_subsistence_land.txt"
LOC = MOD_ROOT / "main_menu" / "localization" / "english" / "pp_modifiers_l_english.yml"
DEFINES = MOD_ROOT / "loading_screen" / "common" / "defines" / "pp_defines_adjustments.txt"
SV = {"capital_economy_vs_traditional_economy", "aristocracy_vs_plutocracy", "land_vs_naval", "serfdom_vs_free_subjects"}


def _objects(path: Path) -> dict[str, CList]:
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), f"{path.name} needs a UTF-8 BOM"
    return {e.key: e.value for e in parse_text(raw.decode("utf-8-sig")).entries if isinstance(e.value, CList)}


VALS = {**_objects(MARITIME), **_objects(VALUES)}


def _evaluate(block: CList, scope: dict, result: float = 0.0) -> float:
    """The script value syntax these files use, applied in order to one running value. ``scope`` holds trigger
    results and atoms by their text (``total_population``, ``societal_value:land_vs_naval``, ...)."""

    def operand(value) -> float:
        if isinstance(value, CList):
            return _evaluate(value, scope)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        name = str(value).removeprefix("this.")
        if name in scope:
            return float(scope[name])
        if name in VALS:
            return _evaluate(VALS[name], scope)
        raise AssertionError(f"unknown operand {value}")

    for entry in block.entries:
        key, value = entry.key, entry.value
        if key == "desc":
            continue
        if key == "value":
            result = operand(value)
        elif key == "add":
            result += operand(value)
        elif key == "subtract":
            result -= operand(value)
        elif key == "multiply":
            result *= operand(value)
        elif key == "divide":
            result /= operand(value)
        elif key == "min":
            result = max(result, operand(value))
        elif key == "max":
            result = min(result, operand(value))
        elif key == "ceiling":
            result = math.ceil(result - 1e-9)
        elif key == "if":
            if all(_holds(e, scope) for e in value.first("limit").entries):
                result = _evaluate(CList([e for e in value.entries if e.key != "limit"]), scope, result)
        else:
            raise AssertionError(f"unexpected script value operation {key}")
    return result


def _holds(entry, scope: dict) -> bool:
    if entry.key == "has_advance":
        return entry.value in scope.get("advances", ())
    if entry.key == "has_societal_value":
        return True
    if entry.key == "has_variable":
        return f"var:{entry.value}" in scope
    value = ("yes" if entry.value else "no") if isinstance(entry.value, bool) else entry.value
    actual = scope.get(entry.key)
    if actual is None:
        actual = _evaluate(VALS[entry.key], scope)
    if entry.op == "=":
        return actual == value
    return actual > float(value) if entry.op == ">" else actual < float(value)


def country(*, pop=1000.0, burghers=0.0, maritime=0.0, sv=None, urban=0.0, levels=0.0, locations=10, advances=(), trade_body=False):
    """A country scope: population in thousands, burgher share 0..1, maritime reach 0..1, societal values -100..100."""
    scope = {"total_population": pop, "percentage_pop_type_in_country:burghers": burghers, "pp_maritime_reach": maritime,
             "num_locations": locations, "var:pp_trade_reach_urban_share": urban, "pp_trade_reach_trade_levels": levels,
             "advances": set(advances), "pp_landless_trade_body": "yes" if trade_body else "no"}
    # default: every slider gives nothing (plutocracy counts over the whole slider, so it starts at full aristocracy)
    for key in SV:
        scope[f"societal_value:{key}"] = (sv or {}).get(key, -100.0 if key == "aristocracy_vs_plutocracy" else 0.0)
    return scope


def points(**kw) -> dict[str, float]:
    s = country(**kw)
    names = ["burghers", "seafaring", "capital_economy", "plutocracy", "naval", "free_subjects", "towns", "trade_buildings"]
    return {n: _evaluate(VALS[f"pp_trade_reach_pts_{n}"], s) for n in names}


def test_points_per_input_follow_the_configured_rule() -> None:
    assert points()["burghers"] == 0                                   # no burghers, no points
    assert points(burghers=0.015)["burghers"] == pytest.approx(0)      # 1.5 %: the threshold
    assert points(burghers=0.035)["burghers"] == pytest.approx(20)     # 10 per percent above it
    assert points(burghers=0.20)["burghers"] == 45                     # at most 45
    assert points(maritime=0.5)["seafaring"] == 20 and points(maritime=1)["seafaring"] == 40
    cap = "capital_economy_vs_traditional_economy"
    assert points(sv={cap: -100})["capital_economy"] == 30             # the capital-economy pole
    assert points(sv={cap: -50})["capital_economy"] == 15
    assert points(sv={cap: 60})["capital_economy"] == 0                # the traditional half gives nothing
    pluto = "aristocracy_vs_plutocracy"
    assert points(sv={pluto: -100})["plutocracy"] == 0 and points(sv={pluto: 100})["plutocracy"] == 15
    assert points(sv={pluto: 0})["plutocracy"] == pytest.approx(7.5)   # linear over the whole slider
    for key, name in (("land_vs_naval", "naval"), ("serfdom_vs_free_subjects", "free_subjects")):
        assert points(sv={key: 100})[name] == 15 and points(sv={key: 40})[name] == pytest.approx(6)
        assert points(sv={key: -100})[name] == 0
    assert points(urban=0.2)["towns"] == pytest.approx(10) and points(urban=0.5)["towns"] == 15
    # 4 levels per 100,000 people = 15 points: 1,000 thousand people, 40 levels
    assert points(pop=1000, levels=40)["trade_buildings"] == pytest.approx(15)
    assert points(pop=1000, levels=20)["trade_buildings"] == pytest.approx(7.5)
    assert points(pop=1000, levels=400)["trade_buildings"] == 15


def _reach(name: str, **kw) -> float:
    return _evaluate(VALS[name], country(**kw))


def test_full_reach_at_150_points_and_the_floor_holds() -> None:
    full = dict(burghers=0.06, maritime=1, sv={"capital_economy_vs_traditional_economy": -100,
                                                "aristocracy_vs_plutocracy": 100, "land_vs_naval": 100,
                                                "serfdom_vs_free_subjects": 100}, urban=0.3, levels=40)
    assert _reach("pp_trade_reach_points", **full) == pytest.approx(190)   # every input at its top
    assert _reach("pp_trade_reach_raw", **full) == 1
    half = dict(burghers=0.06, maritime=0.75)                            # 45 + 30 = 75 points
    assert _reach("pp_trade_reach_raw", **half) == pytest.approx(0.5)
    assert _reach("pp_trade_reach", **half) == pytest.approx(0.5)
    some = dict(burghers=0.06, maritime=1, urban=0.3)                    # 45 + 40 + 15 = 100 points
    assert _reach("pp_trade_reach", **some) == pytest.approx(100 / 150)
    assert _reach("pp_trade_reach_raw") == 0 and _reach("pp_trade_reach") == 0.5   # nothing: the floor
    # a landless bank gets the floor, whatever its societal values
    landless = dict(full, locations=0)
    assert _reach("pp_trade_reach_points", **landless) == 0 and _reach("pp_trade_reach", **landless) == 0.5
    # a landless merchant federation or trading company (the Hansa): 100 points for being one, plus its societal values
    body = dict(locations=0, trade_body=True)
    assert _reach("pp_trade_reach_points", **body) == pytest.approx(100)
    assert _reach("pp_trade_reach", **body) == pytest.approx(100 / 150)
    assert _reach("pp_trade_reach_points", **dict(landless, trade_body=True)) == pytest.approx(175)
    # with land the trade body rule adds nothing
    assert _reach("pp_trade_reach_points", **dict(full, trade_body=True)) == pytest.approx(190)


def test_shortfall_takes_the_unreached_part_of_the_advances_range() -> None:
    adv = ("merchants_and_trade", "trade_range_advance_age_2", "trade_range_advance_age_3")
    assert _reach("pp_advance_trade_range", advances=adv) == 750
    assert _reach("pp_trade_reach_shortfall", advances=adv) == pytest.approx(375)        # the floor: half off
    assert _reach("pp_trade_reach_shortfall", advances=adv, burghers=0.06, maritime=1, urban=0.3, levels=40,
                  sv={"capital_economy_vs_traditional_economy": -100, "land_vs_naval": 40}) == pytest.approx(0)


def test_merchant_house_cap_is_one_plus_seven_raw_reach() -> None:
    assert _reach("pp_merchant_house_cap") == 1 and _reach("pp_merchant_house_cap_shown") == 1
    assert _reach("pp_merchant_house_cap", burghers=0.06, maritime=0.75) == pytest.approx(4.5)
    assert _reach("pp_merchant_house_cap_shown", burghers=0.06, maritime=0.75) == 5
    assert _reach("pp_merchant_house_cap_shown", burghers=0.06, maritime=1, urban=0.3, levels=40,
                  sv={"capital_economy_vs_traditional_economy": -100, "land_vs_naval": 40}) == 8
    held = VALS["pp_merchant_houses_held"]
    body = held.first("every_owned_foreign_building")
    types = {str(e.value) for e in body.first("limit").first("OR").entries}
    assert types == {"building_type:trade_office", "building_type:fondaco", "building_type:hanseatic_kontor"}


def test_advance_range_lists_every_advance_with_trade_range() -> None:
    listed: dict[str, float] = {}
    for entry in VALS["pp_advance_trade_range"].entries:
        if entry.key == "if":
            listed[str(entry.value.first("limit").first("has_advance"))] = float(entry.value.first("add"))
    found: dict[str, float] = {}
    for entry in load_merged_directory(load_profile("constructor", LOAD_ORDER), "advances", scope="in_game").entries:
        if isinstance(entry.value, CList):
            total = sum(float(v) for v in entry.value.values("trade_range")
                        if isinstance(v, (int, float)) and not isinstance(v, bool))
            if total:
                found[entry.key] = total
    assert listed == found, "pp_advance_trade_range must list every advance with a trade_range line, same value"


def test_trade_building_types_exist() -> None:
    names = re.findall(r"total_effective_building_levels:(\w+)", VALUES.read_text(encoding="utf-8-sig"))
    assert len(names) == len(set(names)) >= 10
    loaded = {e.key.split(":")[-1] for e in load_merged_directory(load_profile("constructor", LOAD_ORDER),
                                                                    "building_types", scope="in_game").entries}
    assert set(names) <= loaded, set(names) - loaded
    assert not {"trade_office", "fondaco", "hanseatic_kontor", "banking_office"} & set(names)


def test_the_auto_modifier_takes_off_the_shortfall_only() -> None:
    auto = _objects(AUTO)
    assert set(auto) == {"pp_limited_trade_reach"}
    body = auto["pp_limited_trade_reach"]
    lines = {(e.key, e.op, str(e.value)) for e in body.first("potential_trigger").entries}
    assert lines == {("pp_advance_trade_range", ">", "0"), ("pp_trade_reach", "<", "1")}
    assert body.first("scales_with") == "pp_trade_reach_shortfall"
    modifiers = [e for e in body.entries if e.key not in ("potential_trigger", "scales_with")]
    assert [(e.key, e.value) for e in modifiers] == [("trade_range", -1)]


def test_town_share_is_stored_by_the_yearly_pulse_and_at_game_start() -> None:
    effects = _objects(EFFECTS)
    assert "name = pp_trade_reach_urban_share value = pp_trade_reach_urban_share_now" in re.sub(
        r"\s+", " ", EFFECTS.read_text(encoding="utf-8-sig"))
    assert set(effects) == {"pp_refresh_trade_reach"}
    on_action = ON_ACTION.read_text(encoding="utf-8-sig")
    assert on_action.count("pp_refresh_trade_reach = yes") == 2      # yearly country pulse and game start
    now = VALS["pp_trade_reach_urban_share_now"]
    text = re.sub(r"\s+", " ", re.sub(r"#.*", "", VALUES.read_text(encoding="utf-8-sig")))
    assert "every_owned_location = { limit = { NOT = { location_rank = location_rank:rural_settlement } } add = population }" in text
    assert now.first("if") is not None
    # nothing else walks the country's locations
    assert text.count("every_owned_location") == 1


def test_points_rows_have_text_and_the_modifier_a_plain_description() -> None:
    text = LOC.read_text(encoding="utf-8-sig")
    for desc in re.findall(r'desc = "(\w+)"', VALUES.read_text(encoding="utf-8-sig")):
        assert re.search(rf'^{desc}: "(.+)"$', text, re.MULTILINE), desc
    name = re.search(r'^AUTO_MODIFIER_NAME_pp_limited_trade_reach: "(.+)"$', text, re.MULTILINE)
    desc = re.search(r'^AUTO_MODIFIER_DESC_pp_limited_trade_reach: "(.+)"$', text, re.MULTILINE)
    assert name and desc
    assert not re.search(r"\d", re.sub(r"\[[^\]]*\]", "", desc.group(1))), "no values in player text"
    assert "[trade_range|e]" in desc.group(1)


def test_distance_divisor() -> None:
    text = DEFINES.read_text(encoding="utf-8-sig")
    assert re.search(r"^\s*MERCHANT_DISTANCE_COST_DIVISOR = 300\b", text, re.MULTILINE)
