"""Unit tests for the game-start crop allocation (no game files needed)."""

from __future__ import annotations

import csv
import tomllib
from pathlib import Path

import polars as pl
import pytest

from prosper_or_perish_constructor.farming_village_unlocks import RgoUnlockGate
from prosper_or_perish_constructor.worldbuilder import crop_allocation as ca
from prosper_or_perish_constructor.worldbuilder.contract import Contract

ROOT = Path(__file__).resolve().parents[1]
CFG = ca.CropConfig()
ALL = frozenset(CFG.goods)
GATES = (
    RgoUnlockGate(good="rice", subcontinents=("east_asia",), regions=("iberia_region",)),
    RgoUnlockGate(good="maize", subcontinents=("north_america", "south_america"), regions=()),
    RgoUnlockGate(good="potato", subcontinents=(), regions=("andes_region",)),
    RgoUnlockGate(good="olives", subcontinents=("north_africa",), regions=("iberia_region",)),
)


def _contract(tmp_path: Path) -> Contract:
    """Two locations: 'plain' (continental grasslands, the reference) and 'paddy' (tropical marsh)."""
    goods = ["legumes", "maize", "millet", "olives", "potato", "rice", "wheat"]
    rows = pl.DataFrame({
        "attribute": ["reference", "climate", "vegetation"],
        "value": ["intercept", "tropical", "marsh"],
        "capacity_people": [20000.0, 1000.0, 0.0],
        **{f"output_{g}": [0.0, 0.0, 0.0] for g in goods},
    }).with_columns(
        pl.Series("output_wheat", [0.1, -0.5, -0.3]),
        pl.Series("output_rice", [-0.4, 0.3, 0.5]),
        pl.Series("output_potato", [0.0, -2.0, 0.0]),
    )
    attrs = pl.DataFrame({
        "location_tag": ["plain", "paddy"],
        "climate": ["continental", "tropical"],
        "vegetation": ["grasslands", "marsh"],
    })
    meta = {"attributes": {"features": ["climate", "vegetation"], "reference_classes": {"climate": "continental", "vegetation": "grasslands"}}}
    empty = pl.DataFrame()
    return Contract(root=tmp_path, meta=meta, attribute_rows=rows, building_types=empty, location_buildings=empty,
                    location_targets=empty, location_attributes=attrs, goods_floor=empty)


def _frame() -> pl.DataFrame:
    return pl.DataFrame({
        "location_tag": ["plain", "paddy"],
        "raw_material": ["wheat", "rice"],
        "vegetation": ["grasslands", "ha1300_veg_marsh"],
        "region": ["france_region", "east_china_region"],
        "macro_region": ["western_europe", "east_asia"],
    })


def test_allocate_is_deterministic_and_totals_levels():
    weights = {"wheat": 1.0, "millet": 0.95, "legumes": 0.9, "rice": 0.85, "olives": 0.8, "livestock": 0.2}
    for levels in range(0, 13):
        first = ca.allocate(levels, weights, ALL, "wheat", CFG)
        assert first == ca.allocate(levels, dict(reversed(list(weights.items()))), ALL, "wheat", CFG)
        assert sum(first.values()) == levels
        assert all(n > 0 for n in first.values())


def test_remainder_goes_to_the_rgo_good_first():
    # millet 1.0 + 0.5 bonus vs wheat 1.4: 1 level -> both floor to 0, the remainder goes to the RGO good
    assert ca.allocate(1, {"wheat": 1.4, "millet": 1.0}, ALL, "millet", CFG) == {"millet": 1}
    # without an RGO candidate the heaviest good takes the first remaining level
    assert ca.allocate(1, {"wheat": 1.0, "millet": 1.2}, ALL, "iron", CFG) == {"millet": 1}
    # equal weights, no RGO: the tie falls to the fixed good order (wheat before millet)
    assert ca.allocate(1, {"millet": 1.0, "wheat": 1.0}, ALL, None, CFG) == {"wheat": 1}
    assert ca.allocate(3, {"wheat": 1.0, "millet": 1.0}, ALL, None, CFG) == {"wheat": 2, "millet": 1}


def test_floor_drops_weak_crops_but_never_the_rgo_good():
    assert ca.allocate(6, {"wheat": 1.0, "olives": 0.3}, ALL, None, CFG) == {"wheat": 6}
    # the RGO good survives the floor even when it is weak
    out = ca.allocate(6, {"wheat": 2.0, "olives": 0.1}, ALL, "olives", CFG)
    assert out["olives"] >= 1 and sum(out.values()) == 6


def test_grain_rule_moves_one_level_from_three_levels_on():
    weights = {"olives": 1.0, "wheat": 0.3, "millet": 0.4}
    assert ca.allocate(2, weights, ALL, None, CFG) == {"olives": 2}  # under grain_min_levels_from: no staple forced
    assert ca.allocate(3, weights, ALL, None, CFG) == {"millet": 1, "olives": 2}   # millet is the heaviest staple
    # the donor is the largest allocation, livestock included: round(0.7 x 3) = 2 livestock, 1 olives
    assert ca.allocate(3, {"olives": 1.0, "wheat": 0.3, "livestock": 0.7}, ALL, None, CFG) == {"wheat": 1, "olives": 1, "livestock": 1}
    # no staple available with a weight: nothing is moved
    assert ca.allocate(4, {"olives": 1.0, "livestock": 0.5}, ALL, None, CFG) == {"olives": 2, "livestock": 2}


def test_livestock_takes_its_share_before_the_crops_and_is_never_floored():
    assert ca.allocate(10, {"wheat": 1.0, "livestock": 0.1}, ALL, None, CFG) == {"wheat": 9, "livestock": 1}
    assert ca.allocate(6, {"wheat": 1.0, "millet": 0.9, "livestock": 0.5}, ALL, None, CFG) == {"wheat": 2, "millet": 1, "livestock": 3}
    # half up, not banker's rounding: 0.25 x 2 = 0.5 -> 1
    assert ca.allocate(2, {"wheat": 1.0, "livestock": 0.25}, ALL, None, CFG) == {"wheat": 1, "livestock": 1}
    # a livestock RGO adds rgo_bonus to g, capped at livestock_share_max: min(0.7, 0.3 + 0.5) x 6 = 4.2 -> 4
    assert ca.allocate(6, {"wheat": 1.0, "livestock": 0.3}, ALL, "livestock", CFG) == {"wheat": 2, "livestock": 4}
    # no crop available: livestock takes every level; livestock unavailable: it gets none
    assert ca.allocate(5, {"rice": 1.0, "livestock": 0.2}, frozenset({"livestock"}), None, CFG) == {"livestock": 5}
    assert ca.allocate(5, {"wheat": 1.0, "livestock": 0.2}, frozenset({"wheat"}), None, CFG) == {"wheat": 5}


def test_candidate_filter_counts_as_unavailable():
    weights = {"wheat": 1.0, "olives": 1.2, "livestock": 0.1}
    assert ca.allocate(6, weights, ALL, "olives", CFG)["olives"] >= 4
    no_olives = lambda good: good != "olives"  # noqa: E731
    assert ca.allocate(6, weights, ALL, "olives", CFG, candidate_filter=no_olives) == {"wheat": 5, "livestock": 1}
    no_cattle = lambda good: good != "livestock"  # noqa: E731
    assert ca.allocate(6, weights, ALL, None, CFG, candidate_filter=no_cattle) == {"wheat": 2, "olives": 4}
    assert ca.allocate(6, {"olives": 1.0, "livestock": 0.2}, ALL, None, CFG, candidate_filter=lambda g: False) == {}


def test_no_candidates_gives_empty_plan():
    assert ca.allocate(6, {"wheat": 0.0, "rice": 1.0}, frozenset({"wheat"}), "rice", CFG) == {}
    assert ca.allocate(6, {}, ALL - {"livestock"}, None, CFG) == {}
    assert ca.allocate(6, {}, ALL, None, CFG) == {"livestock": 6}   # no crop at all: livestock takes every level
    assert ca.allocate(0, {"wheat": 1.0}, ALL, None, CFG) == {}


def test_unavailable_rgo_gets_no_bonus_or_levels():
    out = ca.allocate(4, {"wheat": 1.0, "rice": 5.0}, frozenset({"wheat"}), "rice", CFG)
    assert out == {"wheat": 4}


def test_gated_crops_only_in_their_native_regions():
    ungated = {"wheat", "millet", "legumes", "livestock"}
    assert ca.availability(GATES, "western_europe", "france_region", CFG) == frozenset(ungated)
    assert ca.availability(GATES, "western_europe", "iberia_region", CFG) == frozenset(ungated | {"rice", "olives"})
    assert ca.availability(GATES, "east_asia", "east_china_region", CFG) == frozenset(ungated | {"rice"})
    assert ca.availability(GATES, "south_america", "andes_region", CFG) == frozenset(ungated | {"maize", "potato"})
    # a gated good without a gate is nowhere available
    assert ca.availability(GATES[:1], "north_america", "mesoamerica_region", CFG) == frozenset(ungated)


def test_livestock_share_bounds_and_bonus():
    assert ca.livestock_share(None, "wheat", "woods", CFG) == pytest.approx(0.2)
    assert ca.livestock_share(0.01, "wheat", "woods", CFG) == pytest.approx(0.1)
    assert ca.livestock_share(0.95, "wheat", "woods", CFG) == pytest.approx(0.7)
    assert ca.livestock_share(0.3, "wool", "woods", CFG) == pytest.approx(0.5)
    assert ca.livestock_share(0.3, "wheat", "ha1300_veg_sparse", CFG) == pytest.approx(0.5)
    assert ca.livestock_share(0.6, "horses", "grasslands", CFG) == pytest.approx(0.7)


def test_crop_weights_sum_the_class_rows(tmp_path):
    weights = ca.crop_weights(_contract(tmp_path), _frame(), CFG, grazing_shares={"plain": 0.05, "paddy": 0.5})
    assert set(weights) == {"plain", "paddy"} and set(weights["plain"]) == set(CFG.goods)
    plain, paddy = weights["plain"], weights["paddy"]
    assert plain["wheat"] == pytest.approx(1.1) and plain["rice"] == pytest.approx(0.6) and plain["millet"] == pytest.approx(1.0)
    # tropical marsh: wheat 1 + 0.1 - 0.5 - 0.3, rice 1 - 0.4 + 0.3 + 0.5, potato clipped at 0
    assert paddy["wheat"] == pytest.approx(0.3) and paddy["rice"] == pytest.approx(1.4) and paddy["potato"] == 0.0
    # livestock carries the clipped grazing share itself: plain 0.05 + 0.2 grasslands bonus, paddy 0.5 (no bonus)
    assert plain["livestock"] == pytest.approx(0.25) and paddy["livestock"] == pytest.approx(0.5)
    # unknown grazing -> default 0.2 (+ 0.2 on grasslands)
    assert ca.crop_weights(_contract(tmp_path), _frame(), CFG, grazing_shares={})["plain"]["livestock"] == pytest.approx(0.4)


def test_plan_all_maps_goods_to_buildings_and_report(tmp_path):
    contract = _contract(tmp_path)
    plan = ca.plan_all(contract, _frame(), GATES, CFG, {"plain": 6, "paddy": 4, "nowhere": 3}, grazing_shares={})
    assert set(plan) == {"plain", "paddy"}
    assert all(b in CFG.buildings.values() for split in plan.values() for b in split)
    assert sum(plan["plain"].values()) == 6 and sum(plan["paddy"].values()) == 4
    assert "rice_farm" not in plan["plain"]               # rice is gated outside east Asia / Iberia
    assert plan["paddy"]["rice_farm"] >= 3                # RGO and best crop in the paddy
    assert plan == ca.plan_all(contract, _frame(), GATES, CFG, {"paddy": 4, "plain": 6, "nowhere": 3}, grazing_shares={})
    # plain: livestock round(0.4 x 6) = 2, the crops share 4 (wheat RGO first)
    assert plan["plain"] == {"wheat_farm": 2, "millet_farm": 1, "legume_farm": 1, "cattle_farm": 2}
    # the filter is per location: no cattle in the paddy
    filtered = ca.plan_all(contract, _frame(), GATES, CFG, {"plain": 6, "paddy": 4}, grazing_shares={},
                           candidate_filter=lambda tag, good: not (tag == "paddy" and good == "livestock"))
    assert filtered["paddy"] == {"rice_farm": 4} and filtered["plain"] == plan["plain"]

    avail = ca.available_by_location(_frame(), GATES, CFG)
    weights = ca.crop_weights(contract, _frame(), CFG, grazing_shares={})
    path = tmp_path / "report" / "crops.csv"
    assert ca.write_report(plan, weights, path, cfg=CFG, available=avail) == 2 * len(CFG.goods)
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    assert tuple(rows[0]) == ca.REPORT_COLUMNS
    rice = next(r for r in rows if r["location_tag"] == "paddy" and r["good"] == "rice")
    assert rice["building"] == "rice_farm" and rice["available"] == "true" and int(rice["levels"]) == plan["paddy"]["rice_farm"]


def test_load_crop_config_reads_constructor_toml():
    raw = tomllib.loads((ROOT / "constructor.toml").read_text(encoding="utf-8"))
    cfg = ca.load_crop_config(raw, ROOT)
    assert cfg.floor_share == 0.6 and cfg.rgo_bonus == 0.5 and cfg.grain_min_levels_from == 3
    assert (cfg.livestock_share_default, cfg.livestock_share_min, cfg.livestock_share_max) == (0.2, 0.1, 0.7)
    assert cfg.gated_goods == ("rice", "maize", "potato", "olives")
    assert cfg.grains == ("wheat", "millet", "rice", "maize", "legumes", "potato")
    assert cfg.buildings == ca.DEFAULT_BUILDINGS
    assert cfg.livestock_source == (ROOT / "../EU5WorldBuilder/artifacts/locations/locations.csv").resolve()
    # missing section -> defaults
    assert ca.load_crop_config({}) == ca.CropConfig()


def test_grazing_shares_read_by_column_name(tmp_path):
    path = tmp_path / "locations.csv"
    path.write_text("location_tag,source_starting_crop_ha,other,grazing_area_ha\nalpha,300,x,100\nbeta,0,y,0\n", encoding="utf-8")
    assert ca.load_grazing_shares(path) == {"alpha": pytest.approx(0.25)}
