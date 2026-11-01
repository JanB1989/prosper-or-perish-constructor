"""A rural producer next to a town: the AI does not build a rural-capable producer (rural_settlement = yes) at a rural
location whose province has a town of the same owner while the country evaluating it also has a town-only producer of ANY
good that building can make (researched if an advance unlocks it, country_potential passes). Every method counts, active or
not, main good or side good, and no weight, price or shortage opens it (docs/ai_building_rulebook.md 2.5b). Iron mines got 2
of 1,464 levels at such sites in a whole run because one ochre method made dyes, so a side method on a rural building is
never a small thing.

The check here is wider than any one country: a pair counts whatever advance the town-only producer needs, because a country
can research it later. The pairs that stay are listed by hand in [rural_town_goods.allowed] (constructor.toml). A new pair
fails until someone decides it; a listed pair that no longer holds fails too, so the list stays exact. Reads the built mod."""

from __future__ import annotations

import tomllib
from collections import defaultdict
from pathlib import Path

import polars as pl
import pytest
from eu5gameparser.domain.eu5 import load_eu5_data
from eu5gameparser.load_order import load_merged_directory, load_profile

ROOT = Path(__file__).resolve().parents[1]
LOAD_ORDER = ROOT / "constructor.load_order.toml"
# Side methods removed 2026-11-01: these tiers must stay free, so they may never go on the list either.
MINE_TIERS = ("iron_mine", "iron_mine_improved", "iron_mine_deep", "cinnabar_pit", "quicksilver_retort")


def shared_pairs(rural_goods: dict[str, set[str]], town_goods: dict[str, set[str]]) -> dict[str, set[str]]:
    """Rural-capable building -> the goods it makes that a town-only building also makes."""
    town_made = {good for goods in town_goods.values() for good in goods}
    return {name: goods & town_made for name, goods in rural_goods.items() if goods & town_made}


@pytest.fixture(scope="module")
def makers() -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Goods per building from the built mod, split by rural_settlement: (rural-capable, town-only). Producers only."""
    data = load_eu5_data(profile="constructor", load_order_path=LOAD_ORDER).building_data
    blocks = {entry.key: entry.value for entry in load_merged_directory(load_profile("constructor", LOAD_ORDER), "building_types").entries}
    methods = data.production_methods.filter(pl.col("produced").is_not_null())
    global_goods = {row["name"]: row["produced"] for row in methods.filter(pl.col("building").is_null()).iter_rows(named=True)}
    goods: dict[str, set[str]] = defaultdict(set)
    for row in methods.filter(pl.col("building").is_not_null()).iter_rows(named=True):
        goods[row["building"]].add(row["produced"])
    for row in data.buildings.select("name", "possible_production_methods").iter_rows(named=True):
        goods[row["name"]].update(global_goods[m] for m in row["possible_production_methods"] or [] if m in global_goods)
    rural = {name: made for name, made in goods.items() if made and blocks[name].first("rural_settlement") is True}
    town = {name: made for name, made in goods.items() if made and name not in rural}
    assert rural and town
    return rural, town


@pytest.fixture(scope="module")
def allowed() -> dict[str, set[str]]:
    config = tomllib.loads((ROOT / "constructor.toml").read_text(encoding="utf-8"))
    return {name: set(goods) for name, goods in config["rural_town_goods"]["allowed"].items()}


def test_pair_rule_reads_any_good_of_a_rural_building() -> None:
    rural = {"mine": {"iron", "dyes"}, "farm": {"wheat"}}
    town = {"dye_works": {"dyes"}, "mill": {"flour"}}
    assert shared_pairs(rural, town) == {"mine": {"dyes"}}


def test_no_rural_producer_shares_a_good_with_a_town_only_producer_unless_listed(makers, allowed) -> None:
    rural, town = makers
    new = {name: sorted(goods - allowed.get(name, set())) for name, goods in shared_pairs(rural, town).items() if goods - allowed.get(name, set())}
    made_by = {good: sorted(name for name, goods in town.items() if good in goods) for found in new.values() for good in found}
    assert not new, (
        f"The AI would not build these at rural locations with a town in the province: {new}. Town-only producers of those "
        f"goods: {made_by}. Remove the method, or decide it and list the pair in [rural_town_goods.allowed] (constructor.toml)."
    )


def test_every_listed_pair_still_holds(makers, allowed) -> None:
    rural, town = makers
    shared = shared_pairs(rural, town)
    stale = {name: sorted(goods - shared.get(name, set())) for name, goods in allowed.items() if goods - shared.get(name, set())}
    assert not stale, f"No longer shared, remove from [rural_town_goods.allowed]: {stale}"


def test_mine_tiers_share_no_good_with_town_only_producers(makers, allowed) -> None:
    rural, town = makers
    shared = shared_pairs(rural, town)
    assert all(tier in rural for tier in MINE_TIERS)
    assert not {tier: shared[tier] for tier in MINE_TIERS if tier in shared}
    assert not set(MINE_TIERS) & set(allowed)
