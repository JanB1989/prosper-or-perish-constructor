"""Food building niches (2026-09-25): Cookshop / Public Kitchen feed the locals, the Tavern serves bought-in victuals,
the Victualling Yard packs full province stores into victuals. No negative goods inputs, no export pulse."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

from prosper_or_perish_constructor import staple_foods
from prosper_or_perish_constructor.worldbuilder.start_food_model_v2 import FoodModelConfig
from prosper_or_perish_constructor.worldbuilder.start_simulation import Simulation

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
BLUEPRINTS = ROOT / "blueprints" / "accepted" / "buildings"


def _mod_text_files():
    for path in MOD_ROOT.rglob("*"):
        if path.is_file() and path.suffix in {".txt", ".yml", ".gui"}:
            yield path


def test_the_export_pulse_and_its_tally_good_are_gone() -> None:
    offenders = [
        str(path.relative_to(MOD_ROOT))
        for path in _mod_text_files()
        if re.search(r"export_tally|pp_deliver_victuals_exports|victuals_export_delivery", path.read_text(encoding="utf-8-sig", errors="replace"))
    ]
    assert offenders == []


def test_old_building_keys_are_gone_from_the_mod() -> None:
    pattern = re.compile(r"\b(cookery|victuals_market|victuals_market_import)\b|pp_cookery_|pp_victuals_market_")
    offenders = [
        str(path.relative_to(MOD_ROOT))
        for path in _mod_text_files()
        if pattern.search(path.read_text(encoding="utf-8-sig", errors="replace"))
    ]
    assert offenders == []


def test_the_tavern_keeps_food_from_spoiling_like_the_cookshop() -> None:
    # 2026-10-04 (Jan): victuals do not rot, so a serving Tavern cuts store decay as a Cookshop does (staffing-scaled)
    text = (BLUEPRINTS / "tavern.yml").read_text(encoding="utf-8-sig")
    modifier = text.split("    modifier = {", 1)[1].split("}", 1)[0]
    assert "local_food_preservation_efficiency_modifier = 0.04" in modifier


def test_no_blueprint_sells_victuals_as_a_negative_input() -> None:
    enabled = [p for p in BLUEPRINTS.glob("*.yml") if p.stem != "dummy_victuals_producer"]   # disabled experiment
    offenders = [p.name for p in enabled if re.search(r"^\s*victuals = -", p.read_text(encoding="utf-8-sig"), re.M)]
    assert offenders == []


def test_the_cookshop_line_only_feeds_the_province() -> None:
    # Farm reward (2026-10-03, Jan): thin offset recipes at any store, the food is the flat modifier food alone
    for key in ("cookshop", "public_kitchen"):
        text = (BLUEPRINTS / f"{key}.yml").read_text(encoding="utf-8-sig")
        assert "produced = victuals" not in text, key
        assert f"pp_{key}_pottery_jars" not in text and f"pp_{key}_tin_cans" not in text, key   # packing moved away
        assert "produced = local_food" not in text and "daily_fare" not in text, key              # off the store lever
        assert "local_monthly_food = " in text, key                                                # the food
        assert "local_food_preservation_efficiency_modifier = " in text, key
        assert "local_peasants_food_consumption = -" in text, key
        assert "pp_location_stored_months" not in text, key                                        # AI weight: no store terms
        for name, body in re.findall(rf"(pp_{key}_\w+) = \{{([^}}]*)\}}", text, re.S):
            assert "produced = offset" in body, name
            out = float(re.search(r"output = ([\d.]+)", body).group(1))
            cost = sum(float(v) for g, v in re.findall(r"(\w+) = ([\d.]+)", body) if g == "manual_labor")
            assert out > cost, name                                                                 # never below its labour


def test_the_public_kitchen_needs_a_town_or_the_province_capital() -> None:
    text = (BLUEPRINTS / "public_kitchen.yml").read_text(encoding="utf-8-sig")
    gate = text[text.index("allow = {"):]
    gate = gate[: gate.index("build_time")]
    assert "is_province_capital = yes" in gate
    assert "NOT = { location_rank = location_rank:rural_settlement }" in gate
    assert "obsolete = cookshop" in text


def _method(text, key):
    match = re.search(rf"{key} = \{{([^}}]*)\}}", text, re.S)
    assert match, key
    return {k: float(v) if re.fullmatch(r"-?[\d.]+", v) else v for k, v in re.findall(r"(\w+) = (\S+)", match.group(1))}


def test_the_harbour_yard_ships_grain_and_takes_no_store_food() -> None:
    """The harbour Victualling Yard (2026-09-26; scaled x0.4 on 2026-09-30; no food part since 2026-10-03): burghers,
    a staple shipment slot and the Market gate; no store food, no Provisions slot; food-neutral against the Tavern; no
    packing slot (the grain arrives packed); no food capacity (the Granary's job)."""
    text = (BLUEPRINTS / "victualling_yard.yml").read_text(encoding="utf-8-sig")
    for gone in ("river_barges", "merchantmen", "armed_convoy"):
        assert f"pp_victualling_yard_{gone}" not in text
    assert "victualling_yard_armed_convoy_advance" not in text and "local_monthly_food" not in text
    shipments = [_method(text, f"pp_victualling_yard_{m}_shipment") for m in ("grain", "rice", "millet")]
    assert [next(g for g in ("wheat", "rice", "millet") if g in m) for m in shipments] == ["wheat", "rice", "millet"]
    assert all(m["produced"] == "victuals" and m["output"] == 0.932 for m in shipments)
    # 2.33 staples (12 food each in the farms' Provisioning) for 0.932 victuals, 30 food each at a Tavern; every
    # further level ships 3 % more (2026-10-04, Jan; was -5 %)
    grain = shipments[0]["wheat"]
    assert abs(grain * 12.0 / 0.932 - 30.0) < 0.05
    assert "local_victuals_output_modifier = 0.03" in text and "local_victuals_output_modifier = -" not in text
    assert "employment_size = 0.2" in text and "pop_type = burghers" in text
    assert "local_food_capacity" not in text and "local_sailors = 0.002" in text
    assert "increase_per_level_cost = 1.0" in text and "{gold = 50}" in text
    assert "free_building_levels" not in text   # supported levels come only from attributes and rank (2026-09-30)
    assert "tin_cans" not in text and "pottery_jars" not in text
    grange = (BLUEPRINTS / "grange.yml").read_text(encoding="utf-8-sig")
    assert "unlock_production_method = pp_grange_tin_cans" in grange   # the advance moved with the packing slot


def test_the_logistics_caps_are_generated_under_the_new_names() -> None:
    text = (MOD_ROOT / "in_game/common/script_values/pp_victuals_logistics.txt").read_text(encoding="utf-8-sig")
    assert "tavern_max_level = {" in text and "victualling_yard_max_level = {" in text
    assert "victuals_market" not in text
    yard = text[text.index("victualling_yard_max_level = {"):]
    assert "raw_material = goods:" not in yard and "vegetation = farmland" not in yard   # it packs the store, not crops
    # harbour capacity x8 (2026-10-04); the Grand Staple Port's building-levels modifier (+3, on the town right) adds
    # after the upper limit, harbour and inland alike
    assert "modifier:harbor_suitability multiply = 8" in yard
    key = "local_victualling_yard_building_levels"
    staple = f"if = {{ limit = {{ modifier:{key} > 0 }} add = {{ desc = PP_VM_CAP_STAPLE_PORT value = modifier:{key} }} }}"
    rights = (MOD_ROOT / "in_game/common/town_rights/pp_town_rights.txt").read_text(encoding="utf-8-sig")
    assert re.search(rf"TRY_INJECT:royal_staple_rights = \{{\s*location_modifier = \{{\s*{key} = 3\s*\}}", rights)
    types = (MOD_ROOT / "main_menu/common/modifier_type_definitions/pp_building_cap_modifiers.txt").read_text(encoding="utf-8-sig")
    assert f"{key} = {{" in types
    assert yard.count(staple) == 2
    for limit in (10, 4):
        assert f"max = {{ desc = PP_VM_CAP_MAXIMUM value = {limit} }} {staple}" in yard


def _packer_sim(caps):
    sim = Simulation.__new__(Simulation)
    sim.food_model = FoodModelConfig()
    sim.numbers = {Simulation.YARD: {"local_monthly_food": -20.0}, Simulation.GRANGE: {"local_monthly_food": -60.0}}
    sim.counts = defaultdict(Counter)
    sim.cap = lambda tag, key: caps.get((tag, key), 0)
    sim.order = lambda tags, key: [t for t in tags if caps.get((t, key), 0) > sim.counts[t][key]]

    def add(tag, key, want):
        n = max(0, min(want, caps.get((tag, key), 0) - sim.counts[tag][key]))
        sim.counts[tag][key] += n
        return n

    sim.add = add
    return sim


def test_yard_pools_prefer_harbour_sites_then_well_connected_surplus() -> None:
    caps = {("h", Simulation.YARD): 1, ("r", Simulation.GRANGE): 6, ("i", Simulation.GRANGE): 1}
    sim = _packer_sim(caps)
    sim.groups = {("A", "harbour"): ["h"], ("A", "river"): ["r"], ("A", "inland"): ["i"]}
    budgets = {g: {"demand": 1000.0, "supply": 1400.0, "market_food": 0.0, "capacity_months": 30.0, "yard_levels": 0}
               for g in sim.groups}
    budgets[("A", "inland")]["supply"] = 1500.0          # more surplus, but a smaller cap
    order = [g for g, *_ in sim._yard_pools(list(sim.groups), budgets, 1.1)]
    assert order == [("A", "harbour"), ("A", "river"), ("A", "inland")]


def test_a_harbour_yard_needs_only_spare_food_a_grange_the_surplus_share() -> None:
    caps = {("h", Simulation.YARD): 2, ("h", Simulation.GRANGE): 0, ("c", Simulation.GRANGE): 3}
    sim = _packer_sim(caps)
    sim.groups = {("A", "port"): ["h"], ("A", "farm"): ["c"]}
    # both pools feed themselves by only +15 %: below the Grange's 25 % surplus share, above the target
    budgets = {g: {"demand": 1000.0, "supply": 1150.0, "market_food": 0.0, "capacity_months": 30.0, "yard_levels": 0}
               for g in sim.groups}
    placed = sim._place_yards(list(sim.groups), budgets, 1.1, victuals=6.0)
    assert sim.counts["h"][Simulation.YARD] == 2 and sim.counts["c"][Simulation.GRANGE] == 0
    assert placed == 2


STAPLE_FOODS = set(staple_foods.staple_foods())   # the one list (2026-10-04): staple crops, animals and fruits


def test_every_staple_food_maker_raises_the_cookshop_cap() -> None:
    # 2026-10-03 (Jan): the Cookshop cap counts every staple food maker, not only the crop farms and orchards; the
    # fisheries, flocks, hunting forests and palm groves carry local_pp_staple_levels (farms keep local_pp_farm_levels,
    # which their own spread term reads too). Sheep count although they make wool (Jan: a staple).
    missing, marked = [], set()
    for path in sorted((MOD_ROOT / "in_game/common/building_types").glob("*.txt")):
        text = re.sub(r"#[^\n]*", "", path.read_text(encoding="utf-8-sig"))
        pos = 0
        top = re.compile(r"(?:REPLACE:|INJECT:|TRY_INJECT:|REPLACE_OR_CREATE:)?(\w+)\s*=\s*\{")
        while (m := top.search(text, pos)):   # top-level blocks only: the files do not indent building bodies
            depth, i = 1, m.end()
            while depth and i < len(text):
                depth += (text[i] == "{") - (text[i] == "}")
                i += 1
            pos = i
            body = text[m.end():i]
            if re.search(r"always\s*=\s*no", body) and "max_levels = 0" in body:
                continue   # retired (farming_village)
            makes = set(re.findall(r"produced\s*=\s*(\w+)", body)) & STAPLE_FOODS
            counted = "local_pp_farm_levels = 1" in body or "local_pp_staple_levels = 1" in body
            if counted:
                marked.add(m.group(1))
            if makes and not counted and path.name != "rural_buildings.txt":
                missing.append(f"{m.group(1)} ({', '.join(sorted(makes))})")
    assert missing == []
    assert {"fishing_village", "ocean_fishery", "sheep_farms", "forest_village", "eng_royal_forest",
            "maghreb_palm_irrigation", "wheat_farm", "fruit_orchard"} <= marked
    # the cap reads both markers; the farms' spread term only their own
    values = (MOD_ROOT / "in_game/common/script_values/pp_food_building_values.txt").read_text(encoding="utf-8-sig")
    block = values[values.index("pp_province_farm_levels = {"):]
    block = block[:block.index("\n}\n")]
    assert "add = modifier:local_pp_farm_levels" in block and "add = modifier:local_pp_staple_levels" in block
    wheat = (MOD_ROOT / "in_game/common/building_types/zz_pp_wheat_farm_tier0.txt").read_text(encoding="utf-8-sig")
    assert "modifier:local_pp_farm_levels max" in wheat and "local_pp_staple_levels" not in wheat
