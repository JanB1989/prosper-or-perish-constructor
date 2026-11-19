"""Maritime reach (2026-11-19, Jan): the colonial range the advances add counts only as far as a country's seafaring.

Every country keeps the base colonial range. The range its advances add is scaled by pp_maritime_reach (0..1), from the
points of its open-sea ports: 1 per port, 3 in a town or city, +2 per shipbuilding slot there (at most 2 slots). None
at 6 points or less, full from 24. The auto modifier pp_limited_maritime_reach takes the rest off. It replaced the AI
charter cap cut of 2026-10-09, which also kept every native nation from colonising its own backyard. The numbers come
from a fit against nine observer runs (AGENTS.md "Colonial Range"); these tests pin the rule's shape so a change of
the files cannot move it unnoticed, and keep the advance list in step with the game's advances.
"""

from __future__ import annotations

import re
from pathlib import Path

from eu5gameparser.clausewitz.parser import parse_text
from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.load_order import load_merged_directory, load_profile

ROOT = Path(__file__).resolve().parents[1]
LOAD_ORDER = ROOT / "constructor.load_order.toml"
MOD_ROOT = ROOT / "mod" / "pp"
COMMON = MOD_ROOT / "in_game" / "common"
VALUES = COMMON / "script_values" / "pp_maritime_reach_values.txt"
TRIGGERS = COMMON / "scripted_triggers" / "pp_maritime_reach_triggers.txt"
AUTO = COMMON / "auto_modifiers" / "pp_maritime_reach.txt"
LOC = MOD_ROOT / "main_menu" / "localization" / "english" / "pp_modifiers_l_english.yml"
DEFINITIONS = MOD_ROOT / "in_game" / "map_data" / "definitions.txt"
OPEN_SEA = {"ocean", "deep_ocean", "coastal_ocean", "narrows", "inland_sea"}
ENCLOSED_SEAS = {"black_sea_area", "caspian_sea_area"}


def _objects(path: Path) -> dict[str, CList]:
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), f"{path.name} needs a UTF-8 BOM"
    return {e.key: e.value for e in parse_text(raw.decode("utf-8-sig")).entries if isinstance(e.value, CList)}


def _evaluate(block: CList, values: dict[str, CList], scope: dict, result: float = 0.0) -> float:
    """The subset of script value syntax these files use, operations applied in order to one running value (inside
    ``if`` and an iterator too). ``scope``: trigger results and modifier values by name; a country lists its ports under
    ``ports``, its advances under ``advances``."""

    def operand(value) -> float:
        if isinstance(value, CList):
            return _evaluate(value, values, scope)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        if value in values:
            return _evaluate(values[value], values, scope)
        return float(scope[value])

    for entry in block.entries:
        key, value = entry.key, entry.value
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
        elif key == "if":
            if all(_holds(e, scope) for e in value.first("limit").entries):
                result = _evaluate(CList([e for e in value.entries if e.key != "limit"]), values, scope, result)
        elif key == "every_port_in_country":
            body = CList([e for e in value.entries if e.key != "limit"])
            for port in scope["ports"]:
                if all(_holds(e, port) for e in value.first("limit").entries):
                    result = _evaluate(body, values, port, result)
        else:
            raise AssertionError(f"unexpected script value operation {key}")
    return result


def _holds(entry, scope: dict) -> bool:
    if entry.key == "NOT":
        return not all(_holds(e, scope) for e in entry.value.entries)
    if entry.key == "has_advance":
        return entry.value in scope["advances"]
    value = ("yes" if entry.value else "no") if isinstance(entry.value, bool) else entry.value
    return bool(scope[f"{entry.key} {entry.op} {value}"])


def _port(*, town: bool, ships: int) -> dict:
    return {"pp_open_sea_port = yes": True, "location_rank = location_rank:rural_settlement": not town,
            "modifier:max_ships_built_at_same_time": ships}


def test_open_sea_port_points_and_reach_follow_the_fitted_rule() -> None:
    values = _objects(VALUES)

    def points(**port) -> float:
        return _evaluate(values["pp_open_sea_port_points"], values, _port(**port))

    assert points(town=False, ships=0) == 1
    assert points(town=True, ships=0) == 3
    assert points(town=True, ships=1) == 5              # dock
    assert points(town=True, ships=2) == 7              # dry dock
    assert points(town=True, ships=12) == 7             # naval base: at most two slots count

    def reach(ports: list[dict]) -> float:
        return _evaluate(values["pp_maritime_reach"], values, {"ports": ports})

    rural, town = _port(town=False, ships=0), _port(town=True, ships=0)
    river = dict(rural, **{"pp_open_sea_port = yes": False})
    assert reach([]) == 0                                # inland: Basel, Bohemia, Kleve
    assert reach([river] * 12) == 0                      # river and enclosed-sea ports do not count
    assert reach([_port(town=True, ships=2)]) < 0.1      # a Hanse city with a dry dock
    assert 0.4 < reach([rural] * 8 + [town] * 2) < 0.5    # Frisia's coast in the runs: rural ports, two towns, no yards
    # Holland in the runs: about five rural and five town ports, full once it has a few shipyards
    assert reach([rural] * 5 + [town] * 5) < 0.9
    assert reach([rural] * 5 + [town] * 3 + [_port(town=True, ships=4)] * 2) == 1
    assert reach([town] * 8) == 1                        # any larger coast: Portugal, Castile, England, France


def test_shortfall_takes_the_unreached_part_of_the_advances_range() -> None:
    values = _objects(VALUES)
    advances = {"merchants_and_trade", "new_world_advance", "open_sea_exploration"}
    assert _evaluate(values["pp_advance_colonial_range"], values, {"advances": advances}) == 2350
    for share, expected in ((0.0, 2350), (0.5, 1175), (1.0, 0)):
        fixed = {**values, "pp_maritime_reach": parse_text(f"x = {{ value = {share} }}").entries[0].value}
        got = _evaluate(values["pp_maritime_reach_shortfall"], fixed, {"advances": advances})
        assert abs(got - expected) < 1e-9, share


def test_advance_range_lists_every_advance_with_colonial_range() -> None:
    values = _objects(VALUES)
    listed: dict[str, float] = {}
    for entry in values["pp_advance_colonial_range"].entries:
        if entry.key == "if":
            advance = entry.value.first("limit").first("has_advance")
            listed[str(advance)] = float(entry.value.first("add"))
    found: dict[str, float] = {}
    for entry in load_merged_directory(load_profile("constructor", LOAD_ORDER), "advances", scope="in_game").entries:
        if isinstance(entry.value, CList):
            total = sum(float(v) for v in entry.value.values("colonial_range")
                        if isinstance(v, (int, float)) and not isinstance(v, bool))
            if total:
                found[entry.key] = total
    assert listed == found, "pp_advance_colonial_range must list every advance with a colonial_range line, same value"


def test_the_auto_modifier_takes_off_the_shortfall_only() -> None:
    auto = _objects(AUTO)
    assert set(auto) == {"pp_limited_maritime_reach"}
    body = auto["pp_limited_maritime_reach"]
    potential = body.first("potential_trigger")
    lines = {(e.key, e.op, str(e.value)) for e in potential.entries}
    assert lines == {("pp_advance_colonial_range", ">", "0"), ("pp_maritime_reach", "<", "1")}
    assert body.first("scales_with") == "pp_maritime_reach_shortfall"
    modifiers = [e for e in body.entries if e.key not in ("potential_trigger", "scales_with")]
    assert [(e.key, e.value) for e in modifiers] == [("colonial_range", -1)]


def test_open_sea_port_trigger_excludes_rivers_lakes_and_enclosed_seas() -> None:
    trigger = _objects(TRIGGERS)["pp_open_sea_port"]
    assert trigger.first("is_port") is True
    water = trigger.first("any_neighbor_location")
    assert water.first("is_land") is False
    assert {str(e.value) for e in water.first("OR").entries if e.key == "topography"} == OPEN_SEA
    excluded = {str(n.first("area")).removeprefix("area:") for n in water.values("NOT")}
    assert excluded == ENCLOSED_SEAS
    areas = set(re.findall(r"(\w+_area) = \{", DEFINITIONS.read_text(encoding="utf-8-sig")))
    assert ENCLOSED_SEAS <= areas


def test_no_auto_modifier_cuts_the_ai_charter_cap() -> None:
    # The 2026-10-09 gate cut ai_amount_of_parallel_charters for every AI below 150 locations or 8 open-sea ports at
    # home, so the natives never colonised their backyard (Discord report 2026-11). Range now does the work.
    for path in (COMMON / "auto_modifiers").glob("*.txt"):
        text = re.sub(r"#.*", "", path.read_text(encoding="utf-8-sig"))
        assert not re.search(r"ai_amount_of_parallel_charters\s*=\s*-", text), path.name
    assert "pp_colonial_charter_gate" not in LOC.read_text(encoding="utf-8-sig")


def test_the_modifier_has_a_name_and_a_plain_description() -> None:
    text = LOC.read_text(encoding="utf-8-sig")
    name = re.search(r'^AUTO_MODIFIER_NAME_pp_limited_maritime_reach: "(.+)"$', text, re.MULTILINE)
    desc = re.search(r'^AUTO_MODIFIER_DESC_pp_limited_maritime_reach: "(.+)"$', text, re.MULTILINE)
    assert name and desc
    assert not re.search(r"\d", re.sub(r"\[[^\]]*\]", "", desc.group(1))), "no values in player text"
    assert "[colonial_range|e]" in desc.group(1)
