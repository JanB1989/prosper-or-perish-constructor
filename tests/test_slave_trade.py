"""The slave trade (2026-11-27, Jan): a traded unit of slaves goods moves people only when the selling market holds
slaves at its slave market or slave centre sites. Old World slave markets make a quarter of vanilla's goods (margin
kept), the West African slave centres twice vanilla's goods and enslave more, and the slave plantations ask a third
of their old slaves goods with the input cost kept. AGENTS.md "Slave Trade"."""

from __future__ import annotations

from pathlib import Path

from eu5_building_pipeline.template import load_template
from eu5gameparser.clausewitz.parser import parse_file, parse_text
from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.load_order import LoadOrderConfig, load_merged_directory

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINTS = ROOT / "blueprints" / "accepted" / "buildings"
PRICES = ROOT / "mod" / "pp" / "in_game" / "common" / "goods" / "zz_pp_goods_stockpile_prices.txt"
DEFINES = ROOT / "mod" / "pp" / "loading_screen" / "common" / "defines"


def _vanilla_buildings() -> dict[str, CList]:
    profile = LoadOrderConfig.load(ROOT / "constructor.load_order.toml").profile("vanilla")
    return {entry.key: entry.value for entry in load_merged_directory(profile, "building_types").entries}


def _mod_body(key: str) -> CList:
    template = load_template(BLUEPRINTS / f"{key}.yml")
    body = parse_text(f"{template.key} = {{\n{template.building_body}\n}}\n", path=BLUEPRINTS / f"{key}.yml").entries[0].value
    assert isinstance(body, CList)
    return body


def _methods(body: CList) -> dict[str, dict[str, float]]:
    found: dict[str, dict[str, float]] = {}
    for block in body.values("unique_production_methods"):
        assert isinstance(block, CList)
        for entry in block.entries:
            if isinstance(entry.value, CList):
                found[entry.key] = {
                    e.key: float(e.value) for e in entry.value.entries if isinstance(e.value, (int, float))
                }
    return found


def _modifier(body: CList, key: str) -> float:
    return sum(float(e.value) for block in body.values("modifier") for e in block.entries if e.key == key)


def _prices() -> dict[str, float]:
    prices = {"manual_labor": 1.0}
    for entry in parse_file(PRICES).entries:
        if isinstance(entry.value, CList):
            for e in entry.value.entries:
                if e.key == "default_market_price":
                    prices[entry.key.split(":")[-1]] = float(e.value)
    return prices


def _cost(method: dict[str, float], prices: dict[str, float]) -> float:
    skip = {"output", "debug_max_profit"}
    return sum(amount * prices[good] for good, amount in method.items() if good not in skip)


def test_slave_market_makes_a_quarter_of_vanilla_at_the_same_margin() -> None:
    vanilla = _vanilla_buildings()["slave_market"]
    vanilla_method = _methods(vanilla)["slave_market_maintenance"]
    assert vanilla_method["output"] == 2.0
    assert _modifier(vanilla, "building_enslavement_power") == 0.1

    body = _mod_body("slave_market")
    method = _methods(body)["pp_slave_market_slave_market_maintenance"]
    assert method["output"] == 0.5
    assert _modifier(body, "building_enslavement_power") == 0.1  # vanilla, kept
    # the margin of the 2026-10-05 recipe (output 2.0, input cost 8.57 at default prices) stays
    prices = _prices()
    margin = method["output"] * prices["slaves_goods"] / _cost(method, prices)
    assert abs(margin - 2.0 * 4.65 / (0.64 * 4.65 + 0.16 * 5.0375 + 0.38 * 5.115 + 0.54 * 3.41 + 1.4)) < 0.01


def test_slave_center_makes_twice_vanilla_and_enslaves_more() -> None:
    vanilla = _vanilla_buildings()["slave_center"]
    assert _methods(vanilla)["slave_center_maintenance"]["output"] == 1.0
    assert _modifier(vanilla, "building_enslavement_power") == 0.2

    body = _mod_body("slave_center")
    method = _methods(body)["pp_slave_center_slave_center_maintenance"]
    assert method["output"] == 2.0
    assert _modifier(body, "building_enslavement_power") == 0.3
    assert body.values("max_levels") == [1]  # one centre per site, as in vanilla
    # it pays where West African prices sit (about half the default price)
    prices = _prices()
    assert 0.5 * method["output"] * prices["slaves_goods"] > _cost(method, prices)


def test_slave_plantations_ask_a_third_of_the_slaves_goods_at_the_old_input_cost() -> None:
    old_cost = {  # the worked method's input cost at default prices before 2026-11-27 (slaves_goods 0.3)
        "sugar_plantation": ("pp_sugar_plantation_boiling_house", 2.721),
        "cotton_plantation": ("pp_cotton_plantation_gin_house", 2.737),
        "tobacco_plantation": ("pp_tobacco_plantation_curing_barns", 2.779),
    }
    prices = _prices()
    for building, (method_key, cost) in old_cost.items():
        method = _methods(_mod_body(building))[method_key]
        assert method["slaves_goods"] == 0.1, building
        assert method["output"] == 0.667, building
        assert abs(_cost(method, prices) - cost) < 0.01, (building, _cost(method, prices))


def test_trade_slave_factor_stays_vanilla() -> None:
    paths = list(DEFINES.rglob("*.txt"))
    assert paths
    for path in paths:
        assert "TRADE_SLAVE_FACTOR" not in path.read_text(encoding="utf-8-sig"), path
