"""Location-gated production methods (``location_allow``, 2026-11-22, Jan; location_methods.py).

The game checks a method's ``location_allow`` only when a building is created, valued, switched or picked by hand, and the
AI's method switch picks one favourite per slot whatever the gate: a gated method in a shared slot froze every building
outside its gate (in game 2026-11-22). So every gated method of the mod's blueprints

- has a slot of its own: an ungated method without goods or output first, the gated method second, nothing else;
- is not the building's gate (the Market leg, the last slot) and not alone in a slot;
- comes back, with the same gate, in every building that replaces its building (``obsolete``);
- has a name and a description (where it works) in the compiled English text, and every slot of its building has a name;
- follows the add-on rule: 8-16 % of the building's output value, output / input at least 1.2 with labour at 1.8;

and no file of the compiled mod sets a production method (``set_production_method`` ignores the gate).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from eu5gameparser.domain.buildings import load_building_data

from prosper_or_perish_constructor import location_methods as lm
from prosper_or_perish_constructor import production_gate as pg
from prosper_or_perish_constructor import yaml_io

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
MOD_ROOT = ROOT / "mod" / "pp"
LOC_KEY = re.compile(r"(?m)^\s*([A-Za-z0-9_.\-]+):\d*\s*\"")
SLOT_KEY = re.compile(r"(?m)^\s*([A-Za-z0-9_]+_slot_\d+):\d*\s*\"")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _blueprints() -> dict[str, tuple[Path, dict]]:
    """Building key -> (path, data) of every enabled building blueprint with a body."""
    found = {}
    for path in pg.enabled_blueprints(ROOT):
        if not path.is_file():
            continue
        data = yaml_io.safe_load(_read(path)) or {}
        building = data.get("building") or {}
        if building.get("key") and building.get("body"):
            found[str(building["key"])] = (path, data)
    return found


@pytest.fixture(scope="module")
def gated() -> dict[str, tuple[Path, dict, list[pg.Slot]]]:
    """Building -> (blueprint, data, slots) for every blueprint with a location-gated method."""
    out = {}
    for key, (path, data) in _blueprints().items():
        slots, _ = pg.body_slots(data["building"]["body"], path)
        if any(m.gated for slot in slots for m in slot.methods):
            out[key] = (path, data, slots)
    return out


def test_the_check_sees_the_gated_methods(gated) -> None:
    """A parser or helper change that loses the gates must not leave the checks below passing on nothing."""
    expected = {"charcoal_maker", "improved_charcoal_maker", "salt_collector", "rural_clothmaker", "rural_glassmaker",
                "lumber_mill", "water_sawmill", "lumber_mill_improved"}
    assert expected <= set(gated)
    gates = lm.gates_in_text(gated["charcoal_maker"][1]["building"]["body"])
    assert gates == {"pp_charcoal_maker_peat_cutting": "has_location_modifier = pp_wb_soil_peat"}


def test_a_gated_method_has_a_slot_of_its_own_behind_an_empty_method(gated) -> None:
    problems = []
    for key, (path, data, slots) in sorted(gated.items()):
        for index, slot in enumerate(slots):
            if not any(m.gated for m in slot.methods):
                continue
            where = f"{path.name} slot {index} ({', '.join(slot.names())})"
            first, rest = slot.methods[0], slot.methods[1:]
            if first.gated or first.has_output or any(a > 0 for a in first.inputs.values()):
                problems.append(f"{where}: the first method must be an ungated method without goods or output")
            if len(slot.methods) != 2 or not all(m.gated for m in rest):
                problems.append(f"{where}: the slot holds exactly the empty method and one gated method")
            if index == len(slots) - 1 or any(pg.is_leg(m.name) for m in slot.methods):
                problems.append(f"{where}: a gated method never sits in the gate slot (the Market leg)")
            if data.get(pg.FLAG) in slot.names():
                problems.append(f"{where}: a gated method never gates")
    assert not problems, "\n".join(problems)


@pytest.fixture(scope="module")
def game_buildings() -> dict[str, dict]:
    data = load_building_data(profile="constructor", load_order_path=ROOT / "constructor.load_order.toml")
    return {row["name"]: row for row in data.buildings.to_dicts()}


def test_every_upgrade_carries_the_gate(gated, game_buildings) -> None:
    """A building that replaces one with a gated method (once researched the old one cannot be built) carries a method
    with the same gate, so the site keeps what its land gives (tests/test_upgrade_not_worse.py compares them)."""
    gates = lm.game_gates(lm.building_type_files(ROOT, PROJECT))

    def building_gates(name: str) -> set[str]:
        row = game_buildings.get(name) or {}
        return {gates[m] for slot in row.get("unique_production_method_groups") or [] for m in slot if m in gates}

    problems = []
    for old in sorted(gated):
        wanted = building_gates(old)
        assert wanted, f"{old}: the compiled mod lost its gated methods"
        for new, row in sorted(game_buildings.items()):
            if old in (row.get("obsolete_buildings") or []):
                missing = wanted - building_gates(new)
                problems += [f"{old} -> {new}: no method gated on {gate!r}" for gate in sorted(missing)]
    assert not problems, "\n".join(problems)


def test_gated_methods_and_their_slots_have_names(gated) -> None:
    keys: set[str] = set()
    for path in (MOD_ROOT / "main_menu/localization").rglob("*_l_english.yml"):
        keys |= set(LOC_KEY.findall(_read(path)))
    from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

    for path in (vanilla_root(ROOT, PROJECT) / "game/main_menu/localization/english").rglob("*.yml"):
        keys |= set(SLOT_KEY.findall(_read(path)))
    problems = []
    for key, (path, _, slots) in sorted(gated.items()):
        for index in range(len(slots)):
            if f"{key}_slot_{index}" not in keys:
                problems.append(f"{path.name}: no name for slot {index} ({key}_slot_{index})")
        for method in (m for slot in slots for m in slot.methods):
            for loc in (method.name, f"{method.name}_desc") if method.gated else (method.name,):
                if loc not in keys:
                    problems.append(f"{path.name}: no text {loc}")
    assert not problems, "\n".join(problems)


ADD_ON_SIZE = (0.08, 0.16)  # share of the building's output value per level the gated method adds
ADD_ON_LABOUR_PRICE = 1.8  # manual_labor as the game sees it in a running game
ADD_ON_MIN_RETURN = 1.2  # the gated method's own output / input at that labour price
MARKET_GATE = re.compile(r"\bmarket\s*\??=")  # a gate on the market's goods can change: not a location add-on


def test_a_gated_method_follows_the_add_on_rule(gated) -> None:
    """Add-on rule (AGENTS.md "Location-Gated Methods"), base prices (production_gate.load_prices): the gated method
    adds 8-16 % of the building's output value per level, the other slots on their most profitable ungated method (the
    Market leg included), and its own output / input is at least 1.2 with manual_labor at 1.8, so the building with it
    beats the empty choice at the labour price the game sees. Gates on the market (the lumber mills' Forest Elephants)
    are left out: they follow a price, not the land."""
    prices = pg.load_prices(ROOT, PROJECT)
    dear_labour = {**prices, "manual_labor": ADD_ON_LABOUR_PRICE}
    problems, checked = [], 0
    for key, (path, _, slots) in sorted(gated.items()):
        ungated = [[m for m in slot.methods if not m.gated] for slot in slots]
        best = [max(methods, key=lambda m: m.value(prices) - m.cost(prices)) for methods in ungated if methods]
        building_value = sum(m.value(prices) for m in best)
        for method in (m for slot in slots for m in slot.methods if m.gated and m.has_output):
            if MARKET_GATE.search(method.location_allow or ""):
                continue
            checked += 1
            size = method.value(prices) / building_value if building_value > 0 else float("inf")
            back = method.value(dear_labour) / max(method.cost(dear_labour), 1e-9)
            if not ADD_ON_SIZE[0] - 1e-9 <= size <= ADD_ON_SIZE[1] + 1e-9:
                problems.append(f"{path.name}: {method.name} adds {size:.1%} of the building's output value")
            if back < ADD_ON_MIN_RETURN - 1e-9:
                problems.append(f"{path.name}: {method.name} returns {back:.3f} x its input at labour {ADD_ON_LABOUR_PRICE}")
    assert checked >= 5, "the add-on rule checked fewer gated methods than the mod has"
    assert not problems, "\n".join(problems)


def test_no_script_sets_a_production_method() -> None:
    """set_production_method ignores location_allow and the building stays on the method (in game 2026-11-22); a script
    that needs it must test the gate itself, so none may call it unseen."""
    found = [
        str(path.relative_to(MOD_ROOT))
        for path in MOD_ROOT.rglob("*.txt")
        if "set_production_method" in re.sub(r"#[^\n]*", "", _read(path))
    ]
    assert not found, "set_production_method in: " + ", ".join(found)


@pytest.mark.parametrize(
    ("gate", "facts", "expected"),
    [
        ("has_location_modifier = pp_wb_soil_peat", {"modifiers": {"pp_wb_soil_peat"}}, True),
        ("has_location_modifier = pp_wb_soil_peat", {"modifiers": {"pp_wb_soil_loam"}}, False),
        ("OR = { climate = arid climate = mediterranean }", {"climate": "mediterranean"}, True),
        ("has_river = yes OR = { topography = hills topography = ha1300_topo_valleys }",
         {"has_river": True, "topography": "valleys"}, True),
        ("has_river = yes OR = { topography = hills topography = ha1300_topo_valleys }",
         {"has_river": False, "topography": "valleys"}, False),
        ("OR = { vegetation = forest vegetation = ha1300_veg_mixed_forest }", {"vegetation": "coniferous_forest"}, False),
        ("market ?= { is_produced_in_market = goods:elephants }", {"market_goods": {"elephants"}}, True),
        ("market ?= { is_produced_in_market = goods:elephants }", {"market_goods": {"lumber"}}, False),
    ],
)
def test_the_offline_gate_reads_like_the_game(gate: str, facts: dict, expected: bool) -> None:
    assert lm.holds(gate, facts) is expected


def test_the_gate_pass_never_makes_a_gated_slot_a_base_slot_or_a_gate() -> None:
    body = (
        "unique_production_methods = { x_base = { manual_labor = 0.08 produced = salt output = 0.08 } }\n"
        "unique_production_methods = { x_none = { category = building_maintenance }\n"
        "    x_sun = { location_allow = { climate = arid } manual_labor = 0.048 produced = salt output = 0.048 } }\n"
    )
    slots, _ = pg.body_slots(body)
    config = pg.GateConfig()
    prices = {"salt": 5.0, "manual_labor": 1.0}
    assert pg.slot_class(slots[0], config) == 0 and pg.slot_class(slots[1], config) == 1
    assert slots[1].methods[1].location_allow == "climate = arid" and not slots[1].methods[0].gated
    assert pg.suggest_gate([slots[1]], config, prices) is None and pg.main_good([slots[1]], config, prices) is None
    assert pg.gate_problems(slots, "x_sun", False)
    # tier prices are the same everywhere, the Old Ways pass carries recipes of the line: neither reads a gated method
    from prosper_or_perish_constructor import legacy_methods, tier_lines

    assert tier_lines._profit_per_level(body, prices) == pytest.approx(0.08 * 5.0 - 0.08)
    assert [m.gated for m in legacy_methods.parse_body(body)[1]] == [False, True]


def test_the_calculators_count_a_gated_method_only_inside_its_gate() -> None:
    """The Construction Plan's business estimate wraps the method in its gate and its market limit leaves it out; the
    start market stock averages a gated slot over the methods allowed in the location."""
    from prosper_or_perish_constructor import construction_plan as cp
    from prosper_or_perish_constructor import start_market_stock as sms

    peat = "has_location_modifier = pp_wb_soil_peat"
    gated = cp.Recipe("coal", 0.155, (("manual_labor", 0.062),), peat)
    plain = cp.Recipe("coal", 0.62, (("lumber", 0.37),))
    text = cp._business_method("pp_cplan_bm_x_1_1", gated, set())
    inside = text.split(f"limit = {{ {peat} }}", 1)
    assert len(inside) == 2 and "goods:coal" in inside[1] and "goods:manual_labor" in inside[1]
    assert "limit" not in cp._business_method("pp_cplan_bm_x_2_1", plain, set())
    assert cp.main_output([[plain], [cp.Recipe(None, 0.0, ()), gated]], "coal") == 0.62

    empty = {"name": "x_none", "input_goods": [], "input_amounts": [], "produced": None, "output": None}
    cutting = {"name": "x_peat", "input_goods": ["manual_labor"], "input_amounts": [0.062], "produced": "coal", "output": 0.155}
    slot = [(empty, None), (cutting, peat)]
    assert sms._gated_flows([slot], {"modifiers": {"pp_wb_soil_loam"}}) == ({}, {})
    inputs, outputs = sms._gated_flows([slot], {"modifiers": {"pp_wb_soil_peat"}})
    assert inputs == {"manual_labor": 0.031} and outputs == {"coal": 0.0775}


def test_an_unknown_condition_is_not_allowed() -> None:
    with pytest.raises(lm.Unreadable):
        lm.holds("owner = { has_advance = x }", {})
    assert lm.allowed("owner = { has_advance = x }", {}) is False
    assert lm.allowed("market ?= { is_produced_in_market = goods:elephants }", {"market_goods": None}) is False
    assert lm.allowed(None, {}) is True
