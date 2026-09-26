"""Food building niches (2026-09-25): Cookshop / Public Kitchen feed the locals, the Tavern serves bought-in victuals,
the Victualling Yard packs full province stores into victuals. No negative goods inputs, no export pulse."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

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


def test_no_blueprint_sells_victuals_as_a_negative_input() -> None:
    enabled = [p for p in BLUEPRINTS.glob("*.yml") if p.stem != "dummy_victuals_producer"]   # disabled experiment
    offenders = [p.name for p in enabled if re.search(r"^\s*victuals = -", p.read_text(encoding="utf-8-sig"), re.M)]
    assert offenders == []


def test_the_cookshop_line_only_feeds_the_province() -> None:
    for key in ("cookshop", "public_kitchen"):
        text = (BLUEPRINTS / f"{key}.yml").read_text(encoding="utf-8-sig")
        assert "produced = victuals" not in text, key
        assert f"pp_{key}_pottery_jars" not in text and f"pp_{key}_tin_cans" not in text, key   # packing moved away
        assert re.search(rf"pp_{key}_beer = \{{[^}}]*produced = local_food", text, re.S), key       # drinks feed too
        assert "local_monthly_food = " in text, key                                                # the flat base


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


def test_the_harbour_yard_ships_grain_and_packs_little_of_the_store() -> None:
    """The harbour Victualling Yard (2026-09-26): burghers, 20 food per level, three Provisions methods (labour or
    goods) and a grain shipment slot; food-neutral against the Tavern; no packing slot (the grain arrives packed)."""
    text = (BLUEPRINTS / "victualling_yard.yml").read_text(encoding="utf-8-sig")
    provisions = [_method(text, f"pp_victualling_yard_{m}") for m in ("river_barges", "merchantmen", "armed_convoy")]
    shipments = [_method(text, f"pp_victualling_yard_{m}_shipment") for m in ("grain", "rice", "millet")]
    # shipping cost methods: the better ships lose less cargo, and the labour share falls from method to method
    assert all(m["produced"] == "victuals" for m in provisions)
    outputs = [m["output"] for m in provisions]
    assert outputs == sorted(outputs) and outputs[0] < outputs[-1]
    labour = [m["manual_labor_cost"] for m in provisions]
    assert labour == sorted(labour, reverse=True)
    assert "cannons" in provisions[2] and "requires = cannon_maker_advance" in text
    # the Yard never makes food: with the -5 % victuals per level, the best method and a grain shipment at one level
    # give no more victuals than 90 food buys back at a Tavern (30 food each)
    assert "local_victuals_output_modifier = -0.05" in text
    assert (max(outputs) + 2.33) * 0.95 <= 3.0 + 1e-9
    assert "employment_size = 0.2" in text
    assert [next(g for g in ("wheat", "rice", "millet") if g in m) for m in shipments] == ["wheat", "rice", "millet"]
    assert all(m["produced"] == "victuals" and m["output"] == 2.33 for m in shipments)
    assert "local_monthly_food = -20.0" in text and "pop_type = burghers" in text
    assert "increase_per_level_cost = 1.0" in text and "{gold = 50 sailors = 0.25}" in text
    assert "free_building_levels = -5" in text
    # 20 food + 5.83 grain (12 food each in the farms' Provisioning) for 3 victuals = 30 food per victual (the Tavern's)
    grain = shipments[0]["wheat"]
    assert abs((20.0 + grain * 12.0) / (0.67 + 2.33) - 30.0) < 0.05
    assert "tin_cans" not in text and "pottery_jars" not in text
    grange = (BLUEPRINTS / "grange.yml").read_text(encoding="utf-8-sig")
    assert "unlock_production_method = pp_grange_tin_cans" in grange   # the advance moved with the packing slot


def test_the_logistics_caps_are_generated_under_the_new_names() -> None:
    text = (MOD_ROOT / "in_game/common/script_values/pp_victuals_logistics.txt").read_text(encoding="utf-8-sig")
    assert "tavern_max_level = {" in text and "victualling_yard_max_level = {" in text
    assert "victuals_market" not in text
    yard = text[text.index("victualling_yard_max_level = {"):]
    assert "raw_material = goods:" not in yard and "vegetation = farmland" not in yard   # it packs the store, not crops


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
