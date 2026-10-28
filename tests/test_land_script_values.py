"""What the farm caps and the population bars compute, evaluated offline (script_eval.py) and anchored on numbers read
in game (2026-10-28, Jan: "for some reason they slip through your cracks"; the bar tests only checked the text).

Sanlorenzo (Florence), 2 May 1554 in Jan's observer game, read with a console probe: flat capacity 59.168, 49,940
people, no subsistence peasants, 21 Cattle Farm and 13 Horse Breeders levels, 4 Field Management and 1 Land Clearance
levels; the game showed Cattle Farm 21/25 and Horse Breeders 13/17, the Field Management cap at 13.822 and the Land
Clearance cap at 2.411.
"""

from __future__ import annotations

import copy
import math
import tomllib
from pathlib import Path

import pytest

from prosper_or_perish_constructor import arable_land_bar as alb
from prosper_or_perish_constructor.rural_capacity import LAND_FARM_BUILDINGS
from prosper_or_perish_constructor.script_eval import ScriptEval

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
EVAL = ScriptEval(MOD_ROOT)

FLAT = 59.168
POPULATION = 49.94052
LAND_LEFT = FLAT - POPULATION      # no subsistence peasants: everyone brings their own capacity


def sanlorenzo(*, can_build: set[str] | None = None, **buildings: dict) -> dict:
    """The location as the probe read it; ``buildings`` replaces or adds buildings (level, queued)."""
    ctx = {
        "game": {"population": POPULATION, "development": 27.42777, "climate": "oceanic", "topography": "hills",
                 "vegetation": "forest", "unemployed_peasants": 0.00001},
        "modifiers": {"local_population_capacity": FLAT, "pp_subsistence_land_size": 0.0,
                      "pp_levels_cattle_farm": 21, "pp_levels_horse_breeders": 13, "pp_wb_levels_field_management": 4},
        "location_modifiers": set(),
        "buildings": {"cattle_farm": {"level": 21, "queued": 0}, "horse_breeders": {"level": 13, "queued": 0},
                      "field_management": {"level": 4, "queued": 0}, "land_clearance": {"level": 1, "queued": 0},
                      "lumber_mill": {"level": 2, "queued": 0}},
        "can_build": set(can_build or set()),
        "owner": {"modifiers": {}, "can_build": set(can_build or set())},
    }
    for key, state in buildings.items():
        ctx["buildings"][key] = {"level": 0, "queued": 0, **state}
    return ctx


def farm_max(building: str, ctx: dict) -> float:
    return EVAL.value(f"farm_capacity_max_{building}", ctx)


def _land_per_level() -> dict[str, float]:
    section = tomllib.loads((ROOT / "constructor.toml").read_text(encoding="utf-8"))["worldbuilder"]["farm_land"]
    land = {b: float(section[cls]["land"]) for cls, members in section["classes"].items() for b in members}
    return {b: land.get(b, float(section["arable"]["land"])) for b in LAND_FARM_BUILDINGS}


# --- farm caps ----------------------------------------------------------------------------------------------------

def test_sanlorenzo_farm_caps_are_the_ones_the_game_showed():
    ctx = sanlorenzo()
    assert farm_max("cattle_farm", ctx) == 25
    assert farm_max("horse_breeders", ctx) == 17
    # an arable farm (5 land per level) fits one level into the 9.2 land left
    assert farm_max("wheat_farm", ctx) == 1


def test_other_farms_under_construction_take_their_land_first():
    """Two farms used to see the same free land: Cattle Farm 21/25 and Horse Breeders 13/17 on 9.2 land left, 8 levels
    for land of 4 (2026-10-28, Jan). A farm's levels under construction now take their land from every other farm."""
    ctx = sanlorenzo(horse_breeders={"level": 13, "queued": 2})
    assert farm_max("cattle_farm", ctx) == 23                    # 9.2 - 2 x 2 under construction leaves 2 levels
    assert EVAL.value("pp_farm_queued_levels_cattle_farm", ctx) == -2   # its own tooltip row
    # the engine counts a building's own levels under construction against its own max: no second deduction
    assert farm_max("horse_breeders", ctx) == 17
    # every farm level under construction counts, with its own land per level
    ctx = sanlorenzo(horse_breeders={"level": 13, "queued": 2}, wheat_farm={"level": 0, "queued": 1})
    assert farm_max("cattle_farm", ctx) == 21                    # 9.2 - 4 - 5: nothing left for new levels
    assert farm_max("wheat_farm", ctx) == 1                       # 9.2 - 4 holds its one level under construction
    ctx = sanlorenzo(horse_breeders={"level": 13, "queued": 3}, wheat_farm={"level": 0, "queued": 1})
    assert farm_max("wheat_farm", ctx) == 0                       # 9.2 - 6 < 5: the horses came first
    ctx = sanlorenzo(horse_breeders={"level": 13, "queued": 5})
    assert farm_max("cattle_farm", ctx) == 21


def test_the_own_upgrade_line_under_construction_takes_no_land_twice():
    """An upgrade turns the line's levels into the next tier at the same land per level; the engine checks the line's own
    levels under construction against its max."""
    ctx = sanlorenzo(cattle_farmstead={"level": 0, "queued": 1})
    assert farm_max("cattle_farm", ctx) == 25
    assert farm_max("cattle_farmstead", ctx) == 25             # its max counts the Cattle Farm levels it replaces
    assert farm_max("horse_breeders", ctx) == 16               # but another line's farmstead takes the horses' land


def test_constructions_never_lower_a_cap_below_the_standing_levels():
    """On land that is fully taken a construction changes nothing (the cap cull removes levels above the max), and on
    overused land the cap is what it always was: the cull's business, not the queue's."""
    full = sanlorenzo(horse_breeders={"level": 13, "queued": 3})
    full["modifiers"]["local_population_capacity"] = POPULATION + 1.0     # 1 land left: no free level
    assert farm_max("cattle_farm", full) == 21
    over = sanlorenzo(horse_breeders={"level": 13, "queued": 3})
    over["modifiers"]["local_population_capacity"] = POPULATION - 3.0     # farms hold 3 more than there is
    assert farm_max("cattle_farm", over) == 21 + math.floor(-3 / 2)
    assert EVAL.value("pp_farm_queued_levels_cattle_farm", over) == 0


def test_free_land_reads_the_subsistence_land_as_the_engine_applied_it():
    """pp_subsistence_land is refreshed once a year; a farm that hires subsistence peasants in between lowers today's
    count at once, and the cap used to take their land a second time until the refresh (2026-10-28)."""
    ctx = sanlorenzo()
    # last refresh: 3 (thousand) subsistence peasants; a farm hired them since, today none are left
    ctx["modifiers"]["pp_subsistence_land_size"] = 3.0
    ctx["modifiers"]["local_population_capacity"] = LAND_LEFT + POPULATION - 3.0
    assert farm_max("cattle_farm", ctx) == 25
    # a location without the modifier yet (just conquered, before its owner's yearly refresh): the land is the land
    ctx = sanlorenzo()
    ctx["game"]["unemployed_peasants"] = 5.0
    assert farm_max("cattle_farm", ctx) == 25
    # and the bar's green is the same land
    assert EVAL.value("pp_land_bar_left_flat", ctx) == pytest.approx(LAND_LEFT)


def test_every_land_farm_cap_is_its_levels_plus_the_free_land_in_its_levels():
    land = _land_per_level()
    for building in LAND_FARM_BUILDINGS:
        ctx = sanlorenzo(**{building: {"level": 3, "queued": 0}})
        ctx["modifiers"][f"pp_levels_{building}"] = 3
        # the Sanlorenzo farms stand too; this farm's 3 levels take land as well
        ctx["modifiers"]["local_population_capacity"] = FLAT - 3 * land[building]
        free = math.floor((LAND_LEFT - 3 * land[building]) / land[building] + 1e-9)
        own = 3 + (21 if building in ("cattle_farmstead", "cattle_rotations", "cattle_model_farm") else 0) \
            + (13 if building == "stud_farm" else 0)
        assert farm_max(building, ctx) == max(0, free + own), building


# --- improvement caps and the room on the bar -------------------------------------------------------------------

def test_sanlorenzo_improvement_caps_are_the_ones_the_game_showed():
    ctx = sanlorenzo()
    assert EVAL.value("pp_wb_cap_field_management_shared", ctx) == pytest.approx(13.822, abs=1e-3)
    assert EVAL.value("pp_wb_cap_land_clearance_terms", ctx) == pytest.approx(2.411, abs=1e-3)


def test_sanlorenzo_bar_shows_the_land_the_improvements_could_still_add():
    """Field Management cap 13 levels (floored) with 4 Marled Fields (5 each) standing, Land Clearance cap 2 with 1."""
    marled = sanlorenzo(can_build={"field_management", "land_clearance"})
    assert EVAL.value("pp_land_bar_room", marled) == pytest.approx(13 * 5 - 4 * 5 + 2 * 5 - 1 * 5)
    # Improved Fields researched (Marled Fields obsolete): the 4 standing levels upgrade, every level gives 10
    improved = sanlorenzo(can_build={"field_management_improved", "land_clearance"})
    assert EVAL.value("pp_land_bar_room", improved) == pytest.approx(13 * 10 - 4 * 5 + 5)
    # the location can build it but its owner has not researched it: no room from that tier
    unresearched = sanlorenzo(can_build={"field_management_improved", "land_clearance"})
    unresearched["owner"]["can_build"] = {"land_clearance"}
    assert EVAL.value("pp_land_bar_room", unresearched) == pytest.approx(5)
    # nothing buildable, or no owner: no room
    assert EVAL.value("pp_land_bar_room", sanlorenzo()) == 0
    ownerless = sanlorenzo(can_build={"field_management"})
    ownerless["owner"] = None
    assert EVAL.value("pp_land_bar_room", ownerless) == 0


def test_room_is_zero_when_the_caps_are_full_and_never_negative():
    full = sanlorenzo(can_build={"field_management", "land_clearance"},
                      field_management={"level": 13}, land_clearance={"level": 2})
    assert EVAL.value("pp_land_bar_room", full) == 0
    over = sanlorenzo(can_build={"field_management", "land_clearance"},
                      field_management={"level": 15}, land_clearance={"level": 4})
    assert EVAL.value("pp_land_bar_room", over) == 0


def test_alexandria_upgrades_count_as_room():
    """Alexandria 1837 (the other session's case): 7 Marled Fields under a cap of 6, Improved Fields researched."""
    ctx = sanlorenzo(can_build={"field_management_improved"}, field_management={"level": 7})
    ctx["modifiers"]["pp_wb_levels_field_management"] = 7
    ctx["game"]["climate"] = "arid"                                         # -6: cap 6.82 -> 6 levels
    assert EVAL.value("pp_wb_cap_field_management_shared", ctx) == pytest.approx(6.8228, abs=1e-3)
    assert EVAL.value("pp_land_bar_room_field_management_shared", ctx) == pytest.approx(6 * 10 - 7 * 5)
    # without the upgrade researched the cap is full (7 standing levels over a cap of 6): no room
    ctx["can_build"] = ctx["owner"]["can_build"] = {"field_management"}
    assert EVAL.value("pp_land_bar_room_field_management_shared", ctx) == 0


def _full_max_room(unit: alb.CapUnit, levels: dict[str, int], buildable: set[str], cap: float) -> float:
    """The room as the first version computed it: the best over every buildable member, minus the land now."""
    now = sum(levels.get(b.key, 0) * b.land for b in unit.members)
    best = 0.0
    for b in unit.members:
        if b.key not in buildable:
            continue
        kept = [m for m in unit.members if m is not b and m.key not in alb.replaced(b, unit.members)]
        held = max(0.0, min(cap, unit.limit or cap) // 1 - sum(levels.get(m.key, 0) for m in kept)) * b.land
        best = max(best, held + sum(levels.get(m.key, 0) * m.land for m in kept))
    return max(0.0, best - now)


def test_room_from_one_candidate_per_group_is_the_best_of_every_member():
    """The bars compute one candidate per upgrade line and one for the regional alternatives (cost per frame); over
    random states that must give the best room any buildable member gives."""
    import random

    rng = random.Random(1554)
    units = alb.model(MOD_ROOT, None).units
    for _ in range(400):
        unit = rng.choice(units)
        levels = {b.key: rng.choice((0, 0, 1, 3, 7, 12)) for b in unit.members}
        buildable = {b.key for b in unit.members if rng.random() < 0.5}
        ctx = sanlorenzo(can_build=buildable, **{k: {"level": v} for k, v in levels.items()})
        ctx["game"]["development"] = rng.uniform(0, 300)
        short = unit.equation.removeprefix("pp_wb_cap_")
        cap = EVAL.value(unit.equation, ctx)
        expected = _full_max_room(unit, levels, buildable, cap)
        assert EVAL.value(f"pp_land_bar_room_{short}", ctx) == pytest.approx(expected), (short, levels, buildable, cap)


def test_capacity_bar_is_the_engine_capacity_and_its_parts_fill_one_scale():
    ctx = sanlorenzo(can_build={"field_management", "land_clearance"})
    ctx["modifiers"]["local_population_capacity_modifier"] = 0.1
    multiplier = 1.1
    v = lambda name: EVAL.value(name, ctx)  # noqa: E731
    assert v("pp_land_bar_multiplier") == pytest.approx(multiplier)
    assert v("pp_land_bar_capacity") == pytest.approx(FLAT * multiplier)          # what the engine compares with
    assert v("pp_land_bar_left") == pytest.approx(LAND_LEFT * multiplier)
    assert v("pp_land_bar_farms") == pytest.approx(68 * multiplier)               # 21 x 2 + 13 x 2
    assert v("pp_land_bar_improvements") == pytest.approx(25 * multiplier)        # 4 x 5 + 1 x 5
    assert v("pp_land_bar_natural") == pytest.approx((LAND_LEFT + 68 - 25) * multiplier)
    assert v("pp_land_bar_room") == pytest.approx(50 * multiplier)
    # one scale: townsfolk <= capacity <= capacity + farms <= + room = 1 (the land is longer than the population)
    shares = [v(f"pp_land_bar_f_{p}") for p in ("townsfolk_room", "capacity", "held", "land")]
    assert shares == sorted(shares) and shares[-1] == pytest.approx(1.0)
    assert v("pp_land_bar_f_held") - v("pp_land_bar_f_capacity") == pytest.approx(68 * multiplier / v("pp_land_bar_scale"))
    assert v("pp_land_bar_f_land") - v("pp_land_bar_f_held") == pytest.approx(50 * multiplier / v("pp_land_bar_scale"))


def test_farms_beyond_the_land_hold_only_the_land_there_is():
    ctx = sanlorenzo(can_build={"field_management"})
    ctx["modifiers"]["local_population_capacity"] = POPULATION - 3.0
    assert EVAL.value("pp_land_bar_left_shown", ctx) == 0
    assert EVAL.value("pp_land_bar_farms_shown", ctx) == pytest.approx(68 - 3)
    assert EVAL.value("pp_land_bar_capacity", ctx) == pytest.approx(POPULATION)


def test_window_draws_the_room_after_the_farms_with_its_legend_entry():
    """The built location window carries the room part and its legend entry (the 0.10 bar had neither: a sync from
    0.10 put it back live over the improvement-room bar on 2026-10-28, which this catches)."""
    text = (MOD_ROOT / "in_game/gui/location_window.gui").read_text(encoding="utf-8-sig")
    start = text.rindex("vbox = {", 0, text.index('name = "pp_arable_land_bar"'))
    panel = text[start:alb._block_end(text, text.index("{", start)) + 1]
    held, land = "ScriptValue('pp_land_bar_f_held')", "ScriptValue('pp_land_bar_f_land')"
    assert f"Subtract_float(FixedPointToFloat(LocationView.GetLocation.MakeScope.{land}), " \
           f"FixedPointToFloat(LocationView.GetLocation.MakeScope.{held}))" in panel
    # the legend entry and the tooltip row (the tooltip is laid over both rows of the panel)
    assert panel.count('text = "PP_LAND_BAR_ROOM"') == alb.gui_block().count('text = "PP_LAND_BAR_ROOM"') >= 3
