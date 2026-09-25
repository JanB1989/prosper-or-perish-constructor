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


def test_the_victualling_yard_packs_real_victuals_with_packing_methods() -> None:
    text = (BLUEPRINTS / "victualling_yard.yml").read_text(encoding="utf-8-sig")
    assert re.search(r"pp_victualling_yard_pack_provisions = \{[^}]*produced = victuals", text, re.S)
    for method in ("pottery_jars", "coopered_barrels", "tin_cans"):
        assert re.search(rf"pp_victualling_yard_{method} = \{{[^}}]*produced = victuals", text, re.S), method
    assert "unlock_production_method = pp_victualling_yard_tin_cans" in text
    assert "local_monthly_food = -60.0" in text


def test_the_logistics_caps_are_generated_under_the_new_names() -> None:
    text = (MOD_ROOT / "in_game/common/script_values/pp_victuals_logistics.txt").read_text(encoding="utf-8-sig")
    assert "tavern_max_level = {" in text and "victualling_yard_max_level = {" in text
    assert "victuals_market" not in text
    yard = text[text.index("victualling_yard_max_level = {"):]
    assert "raw_material = goods:" not in yard and "vegetation = farmland" not in yard   # it packs the store, not crops


def test_yard_pools_prefer_well_connected_surplus() -> None:
    sim = Simulation.__new__(Simulation)
    sim.food_model = FoodModelConfig()
    sim.numbers = {Simulation.YARD: {"local_monthly_food": -60.0}}
    sim.groups = {("A", "river"): ["r"], ("A", "inland"): ["i"]}
    sim.counts = defaultdict(Counter)
    caps = {"r": 6, "i": 1}
    sim.cap = lambda tag, key: caps[tag]
    budgets = {g: {"demand": 1000.0, "supply": 1400.0, "market_food": 0.0, "capacity_months": 30.0, "yard_levels": 0}
               for g in sim.groups}
    budgets[("A", "inland")]["supply"] = 1500.0          # more surplus, but no river, coast or market
    order = [g for g, _ in sim._yard_pools(list(sim.groups), budgets, 1.1)]
    assert order == [("A", "river"), ("A", "inland")]
    # a pool whose spare food fills 30 % of a level gets one (the engine staffs it partly)
    budgets = {("A", "river"): {"demand": 1000.0, "supply": 1300.0, "market_food": 0.0, "capacity_months": 30.0, "yard_levels": 0}}
    sim.groups = {("A", "river"): ["r"]}
    assert sim._yard_pools(list(sim.groups), budgets, 1.25) == [(("A", "river"), 1)]   # 50 food spare > 0.3 x 60
