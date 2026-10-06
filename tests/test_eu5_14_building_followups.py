"""Decisions on buildings EU5 1.4 added or changed (2026-10-01), pinned against the merged game data and blueprints."""

from __future__ import annotations

from functools import cache
from pathlib import Path
import re

from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.load_order import MergedEntry, load_merged_directory, load_profile
from prosper_or_perish_constructor import yaml_io


ROOT = Path(__file__).resolve().parents[1]
LOAD_ORDER = ROOT / "constructor.load_order.toml"
BLUEPRINTS = ROOT / "blueprints" / "accepted" / "buildings"


@cache
def _merged(collection: str, profile: str = "constructor") -> dict[str, MergedEntry]:
    return {
        entry.key: entry
        for entry in load_merged_directory(load_profile(profile, LOAD_ORDER), collection, scope="in_game").entries
    }


def _keys(value: object) -> set[str]:
    """Every key anywhere inside a block."""
    if not isinstance(value, CList):
        return set()
    out: set[str] = set()
    for entry in value.entries:
        out.add(entry.key)
        out |= _keys(entry.value)
    return out


def _blueprint(tag: str) -> dict:
    return yaml_io.safe_load((BLUEPRINTS / f"{tag}.yml").read_text(encoding="utf-8"))


def test_village_granary_is_never_built() -> None:
    # The mod's Granary already serves rural settlements (food capacity and preservation); the 1.4 village granary
    # stays off.
    granary = _merged("building_types")["village_granary"].value
    potentials = granary.values("location_potential")
    assert len(potentials) == 1
    assert [(entry.key, str(entry.value)) for entry in potentials[0].entries] in (
        [("always", "False")],
        [("always", "no")],
    )


def test_itinerant_court_seat_pays_jewelry_not_gold() -> None:
    # Like the palaces in pp_gold_to_jewelry_buildings.txt: gold maintenance -> jewelry, construction on the jewelry
    # demand. Vanilla's shared capital_administration_maintenance (with gold) stays untouched for other buildings.
    seat = _merged("building_types")["itinerant_court_seat"].value
    assert seat.values("possible_production_methods") == []
    slots = seat.values("unique_production_methods")
    assert len(slots) == 1
    methods = {entry.key: entry.value for entry in slots[0].entries}
    assert list(methods) == ["pp_itinerant_court_seat_maintenance"]
    keys = _keys(methods["pp_itinerant_court_seat_maintenance"])
    assert "jewelry" in keys and "goods_gold" not in keys
    demand = str(seat.values("construction_demand")[-1])
    assert demand == "pp_early_capital_jewelry_construction"
    assert "goods_gold" not in _keys(_merged("goods_demand")[demand].value)
    vanilla_method = _merged("production_methods")["capital_administration_maintenance"].value
    assert "goods_gold" in _keys(vanilla_method)


def test_textile_mill_keeps_its_own_output() -> None:
    # The mod balances the textile mill by profit per building (output 3 cotton / 2.5, then the manufacturing tiers of
    # 2026-10-06: tier 4 x2.0 throughput, margin +0.12); EU5 1.4's output 4 is not merged.
    body = _blueprint("textile_mill")["building"]["body"]
    outputs = sorted(float(value) for value in re.findall(r"(?m)^\s*output = ([0-9.]+)\s*$", body))
    assert outputs[-1] == 6.697


def test_maghreb_palm_irrigation_is_a_market_producer() -> None:
    # One-level cultural oasis building (like the Omani falaj, estate_land): not a farm on the land capacity; its dates
    # go to market and the Market leg is its gate. Since 2026-10-04 (Jan: every staple food maker follows the store
    # curve) it provisions like one level of a village (reference size), no flat food.
    raw = _blueprint("maghreb_palm_irrigation")
    assert raw["footprint"] == "estate_land"
    methods = [method for slot in raw["building"]["production_method_slots"] for method in slot["methods"]]
    assert [method for method in methods if "provision" in method] == ["pp_maghreb_palm_irrigation_provision"]
    assert not [method for method in methods if "sell_surplus" in method]
    assert raw["gate_method"] == "pp_maghreb_palm_irrigation_market_sales" == methods[-1]
    assert "local_monthly_food" not in raw["building"]["body"]
