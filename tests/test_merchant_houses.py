"""Merchant houses (2026-11-24, Jan; AGENTS.md "Merchant Houses"): the Trade Office, Fondaco and Hanseatic Kontor are
few, big, expensive steps, built only in a market centre, a great natural harbour or a megalopolis within the builder's
trade range. Checks the compiled buildings and the game-start rows."""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from eu5gameparser.clausewitz.parser import parse_file, parse_text
from eu5gameparser.clausewitz.serializer import render_value
from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.load_order import LoadOrderConfig

from prosper_or_perish_constructor.worldbuilder import start_simulation as ss

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mod" / "pp"
HOUSES = ss.MERCHANT_HOUSES
HOST_MODIFIERS = ("local_institution_growth_modifier", "local_max_literacy", "local_merchant_capacity_modifier",
                  "local_migration_attraction")
URBAN = ("town", "city", "megalopolis")


def _first(node, key):
    return next(iter(node.values(key)), None) if isinstance(node, CList) else None


@pytest.fixture(scope="module")
def buildings() -> dict[str, CList]:
    out = {}
    for key in HOUSES:
        doc = parse_file(MOD / f"in_game/common/building_types/zz_pp_{key}.txt")
        blocks = [e.value for e in doc.entries if e.key == f"REPLACE:{key}"]
        assert len(blocks) == 1, key
        out[key] = blocks[0]
    return out


def _text(node) -> str:
    return render_value(node) if node is not None else ""


@pytest.mark.parametrize("key", HOUSES)
def test_site_rule_in_allow_not_in_potential(buildings, key) -> None:
    body = buildings[key]
    assert "pp_merchant_house_site" in _text(_first(body, "allow"))
    assert "pp_merchant_house_site" not in _text(_first(body, "location_potential"))
    assert _first(body, "rural_settlement") is False
    assert all(_first(body, rank) is True for rank in URBAN)


@pytest.mark.parametrize("key", HOUSES)
def test_built_by_trade_range_and_relations_in_allow(buildings, key) -> None:
    body = buildings[key]
    allow = _text(_first(body, "allow"))
    assert re.search(r"market\s*=\s*\{\s*in_trade_range_of\s*=\s*scope:actor\s*\}", allow)
    assert "fondaco_rights" not in render_value(body)
    assert "within_naval_range_of" not in allow
    assert _first(body, "need_good_relation") is False
    # the first step needs a host that is not hostile, further steps opinion 100 and the builder's own levels counted
    assert f"building_type = building_type:{key}" in allow and "owner = scope:actor" in allow
    assert "is_at_war_with = scope:actor" in allow and "is_rival_of" in allow
    assert re.search(r"opinion\s*=\s*\{\s*target\s*=\s*scope:actor\s+value\s*>=\s*100", allow)
    assert re.search(r"opinion\s*=\s*\{\s*target\s*=\s*scope:actor\s+value\s*>=\s*0\b", allow)
    for step in (1, 2, 3):
        assert re.search(rf"value\s*>=\s*{step}\s*\}}", allow), step
    assert "has_advance = trade_range_advance_age_3" in allow and "has_advance = chartered_companies" in allow


@pytest.mark.parametrize("key", HOUSES)
def test_steps_strength_price_and_weight(buildings, key) -> None:
    body = buildings[key]
    assert _first(body, "max_levels") == 4
    assert float(_first(body, "increase_per_level_cost")) == pytest.approx(1.0)
    assert _first(body, "price") == f"pp_{key}_price"
    modifier = _first(body, "modifier")
    for line in (*HOST_MODIFIERS, "merchant_capacity_from_building", "merchant_power_from_building"):
        assert float(_first(modifier, line) or 0) > 0, line
    centre = _first(body, "market_center_modifier")
    assert float(_first(centre, "merchant_capacity_from_building")) == pytest.approx(
        0.5 * float(_first(modifier, "merchant_capacity_from_building")))
    weight = _text(_first(body, "ai_construct_weight"))
    assert "scope:builder.monthly_income_total" in weight and "has_merchant = scope:builder" in weight
    assert float(_first(_first(body, "raw_modifier"), "free_building_levels")) == 1
    prices = (MOD / "in_game/common/prices/zz_pp_building_price_stockpile.txt").read_text(encoding="utf-8-sig")
    assert re.search(rf"^TRY_INJECT:pp_{key}_price = \{{ gold = \d+ \}}", prices, re.M)


def test_site_trigger() -> None:
    body = _text(parse_file(MOD / "in_game/common/scripted_triggers/pp_merchant_house_triggers.txt").entries[0].value)
    assert "is_market_center = yes" in body and "location_rank = location_rank:megalopolis" in body
    assert re.search(r"modifier:natural_harbor_suitability\s*>=\s*[\d.]+", body)


def _harbour_threshold() -> float:
    text = (MOD / "in_game/common/scripted_triggers/pp_merchant_house_triggers.txt").read_text(encoding="utf-8-sig")
    return float(re.search(r"modifier:natural_harbor_suitability\s*>=\s*([\d.]+)", text).group(1))


def test_start_houses_stand_on_sites() -> None:
    """Every start-placed house stands at town rank or above in a market centre, a megalopolis or a location whose own
    natural harbour (the map template, without the river share) reaches the site rule's threshold; at most level 2."""
    vanilla = LoadOrderConfig.load(ROOT / "constructor.load_order.toml").vanilla_root
    setup = parse_file(MOD / "main_menu/setup/1337/07_cities_and_buildings.txt")
    ranks = {e.key: str(_first(e.value, "rank")) for block in setup.values("locations") for e in block.entries
             if isinstance(e.value, CList)}
    centres = set()
    from prosper_or_perish_constructor.worldbuilder import start_placement as sp

    for path in sp.setup_files(vanilla, MOD, "03_markets.txt"):
        for manager in parse_file(path).values("market_manager"):
            centres.update(str(v) for v in manager.values("add_market"))
    harbour = {}
    for line in (MOD / "in_game/map_data/location_templates.txt").read_text(encoding="utf-8-sig").splitlines():
        m = re.match(r"\s*(\w+)\s*=\s*\{.*natural_harbor_suitability\s*=\s*(-?[\d.]+)", line)
        if m:
            harbour[m.group(1)] = float(m.group(2))
    threshold = _harbour_threshold()
    rows = [(e.key, str(_first(e.value, "tag")), str(_first(e.value, "location")), int(_first(e.value, "level")))
            for manager in setup.values("building_manager") for e in manager.entries if e.key in HOUSES]
    assert rows, "no start houses"
    bad = [r for r in rows
           if ranks.get(r[2]) not in URBAN
           or not (r[2] in centres or ranks[r[2]] == "megalopolis" or harbour.get(r[2], 0) >= threshold - 1e-9)
           or not 1 <= r[3] <= 2]
    assert bad == []
    for path in (MOD / "main_menu/setup").rglob("*.txt"):
        if path.name != "07_cities_and_buildings.txt":
            assert not re.search(r"\b(trade_office|fondaco|hanseatic_kontor) = \{", path.read_text(encoding="utf-8-sig")), path


def test_start_rows_levels_and_drops() -> None:
    doc = parse_text(
        "building_manager = {"
        " trade_office = { tag = VEN level = 1 location = port }"
        " trade_office = { tag = GEN level = 3 location = port }"
        " trade_office = { tag = VEN level = 1 location = inland }"
        " hanseatic_kontor = { tag = HSA level = 3 location = port }"
        " temple = { tag = AAA level = 2 location = port } }"
    )
    sim = SimpleNamespace(
        locations={"port": {}, "inland": {}},
        base={"port": {"is_market_center": True}, "inland": {"is_market_center": False}},
        counts={"port": {"trade_office": 4, "hanseatic_kontor": 3}, "inland": {"trade_office": 1}},
        merchant_house_site=lambda tag, key: tag == "port",
    )
    out, report = ss.merchant_house_rows(sim, doc, {"level": 1, "great_level": 2, "great_houses": ["VEN:port"]})
    rows = {(e.key, str(_first(e.value, "tag")), str(_first(e.value, "location"))): _first(e.value, "level")
            for m in out.values("building_manager") for e in m.entries}
    assert rows == {("trade_office", "VEN", "port"): 2, ("trade_office", "GEN", "port"): 1,
                    ("hanseatic_kontor", "HSA", "port"): 1, ("temple", "AAA", "port"): 2}
    assert sim.counts == {"port": {"trade_office": 3, "hanseatic_kontor": 1}, "inland": {"trade_office": 0}}
    assert sorted((r["location"], r["after"]) for r in report) == [("inland", 0), ("port", 1), ("port", 1), ("port", 2)]
