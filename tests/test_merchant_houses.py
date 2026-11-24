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


def _flat(node) -> str:
    """The rendered block on one line, single spaces."""
    return re.sub(r"\s+", " ", _text(node))


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
    # the engine refuses a foreign building without the flag (error.log, 2026-11-24)
    assert _first(body, "need_good_relation") is True
    # the first step needs a host that is not hostile, further steps opinion 100 and the builder's own levels counted
    assert f"building_type = building_type:{key}" in allow and "owner = scope:actor" in allow
    assert "is_at_war_with = scope:actor" in allow and "is_rival_of" in allow
    assert re.search(r"opinion\s*=\s*\{\s*target\s*=\s*scope:actor\s+value\s*>=\s*100", allow)
    assert re.search(r"opinion\s*=\s*\{\s*target\s*=\s*scope:actor\s+value\s*>=\s*0\b", allow)
    for step in (1, 2, 3):
        assert re.search(rf"value\s*>=\s*{step}\s*\}}", allow), step
    assert "has_advance = trade_range_advance_age_3" in allow and "has_advance = chartered_companies" in allow


def _actor_block(body) -> CList:
    blocks = [e.value for e in _first(body, "allow").entries if e.key == "scope:actor"]
    assert len(blocks) == 1
    return blocks[0]


@pytest.mark.parametrize("key", HOUSES)
def test_new_house_one_per_market_and_reach_cap(buildings, key) -> None:
    """2026-11-24 (Jan): a new house (no level of ours here yet) needs no other house of ours in the market and fewer
    houses than the trade reach allows; further steps of a standing house stay open. All builder conditions sit in
    the scope:actor block, which the start check reads as held."""
    actor = _actor_block(buildings[key])
    new = [e.value for e in actor.entries if e.key == "trigger_if"
           and re.search(rf"NOT = \{{ location_building_level = \{{ building_type = building_type:{key} owner = scope:actor "
                         r"value >= 1 \} \}", _flat(e.value.first("limit")))]
    assert len(new) == 1
    text = _flat(new[0])
    assert "text = pp_merchant_house_one_per_market_tt" in text and "text = pp_merchant_house_cap_tt" in text
    assert re.search(r"any_owned_foreign_building_location = \{\s*market = root\.market\s*pp_merchant_house_of_actor = yes",
                     text)
    assert "pp_merchant_houses_held < pp_merchant_house_cap" in text
    trigger = parse_file(MOD / "in_game/common/scripted_triggers/pp_merchant_house_triggers.txt")
    of_actor = _flat(next(e.value for e in trigger.entries if e.key == "pp_merchant_house_of_actor"))
    for house in HOUSES:
        assert f"building_type = building_type:{house} owner = scope:actor value >= 1" in of_actor


@pytest.mark.parametrize("key", HOUSES)
def test_no_landless_banks_except_the_hansa(buildings, key) -> None:
    """Vanilla's building countries (the Florentine banks, the Japanese clans' houses) never build a Trade Office or
    Fondaco; the Kontor's only builder, the Hanseatic merchant federation, is itself a building country (its reform
    requires it), so the Kontor has no such line. In allow, so no standing house is removed."""
    actor = _flat(_actor_block(buildings[key]))
    body = buildings[key]
    assert "country_type = building" not in _text(_first(body, "location_potential"))
    if key == "hanseatic_kontor":
        assert "NOT = { country_type = building }" not in actor
        assert "allows_hanseatic_federation_buildings" in _text(_first(body, "country_potential"))
    else:
        assert re.search(r"custom_tooltip = \{\s*text = pp_merchant_house_builder_tt\s*NOT = \{ country_type = building \}",
                         actor)


def test_house_tooltips_have_text() -> None:
    text = (MOD / "main_menu/localization/english/pp_merchant_houses_l_english.yml").read_text(encoding="utf-8-sig")
    for key in ("pp_merchant_house_builder_tt", "pp_merchant_house_one_per_market_tt", "pp_merchant_house_cap_tt"):
        m = re.search(rf'^ {key}: "(.+)"$', text, re.M)
        assert m, key
        assert not re.search(r"\d", re.sub(r"\[[^\]]*\]", "", m.group(1))), key


@pytest.mark.parametrize("key", HOUSES)
def test_steps_strength_price_and_weight(buildings, key) -> None:
    body = buildings[key]
    assert _first(body, "max_levels") == 4
    # 2026-11-24 (Jan): 1,600 gold for step 1, each further step adds 200 % of it: 1,600 / 4,800 / 8,000 / 11,200
    assert float(_first(body, "increase_per_level_cost")) == pytest.approx(2.0)
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
    assert re.search(rf"^TRY_INJECT:pp_{key}_price = \{{ gold = 1600 \}}", prices, re.M)


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


def _sim(**counts):
    return SimpleNamespace(locations={"port": {}, "inland": {}, "bay": {}}, counts={k: dict(v) for k, v in counts.items()},
                           merchant_house_site=lambda tag, key: tag != "inland")


def test_start_rows_replace_vanilla_with_the_configured_list() -> None:
    doc = parse_text(
        "building_manager = {"
        " trade_office = { tag = VEN level = 1 location = port }"
        " trade_office = { tag = GEN level = 3 location = port }"
        " trade_office = { tag = VEN level = 1 location = inland }"
        " hanseatic_kontor = { tag = HSA level = 3 location = port }"
        " temple = { tag = AAA level = 2 location = port } }"
    )
    sim = _sim(port={"trade_office": 4, "hanseatic_kontor": 3}, inland={"trade_office": 1}, bay={})
    raw = {"houses": ["VEN:trade_office:port:2", "HSA:hanseatic_kontor:port:1", "GEN:fondaco:bay:1"]}
    out, report = ss.merchant_house_rows(sim, doc, raw)
    rows = {(e.key, str(_first(e.value, "tag")), str(_first(e.value, "location"))): _first(e.value, "level")
            for m in out.values("building_manager") for e in m.entries}
    assert rows == {("trade_office", "VEN", "port"): 2, ("hanseatic_kontor", "HSA", "port"): 1,
                    ("fondaco", "GEN", "bay"): 1, ("temple", "AAA", "port"): 2}
    assert sim.counts["port"] == {"trade_office": 2, "fondaco": 0, "hanseatic_kontor": 1}
    assert sim.counts["inland"] == {"trade_office": 0, "fondaco": 0, "hanseatic_kontor": 0}
    assert sim.counts["bay"]["fondaco"] == 1
    got = sorted((r["owner"], r["building"], r["location"], r["before"], r["after"]) for r in report)
    assert got == [("GEN", "fondaco", "bay", 0, 1), ("GEN", "trade_office", "port", 3, 0),
                   ("HSA", "hanseatic_kontor", "port", 3, 1), ("VEN", "trade_office", "inland", 1, 0),
                   ("VEN", "trade_office", "port", 1, 2)]


def test_start_rows_refuse_a_house_off_its_site() -> None:
    doc = parse_text("building_manager = { temple = { tag = AAA level = 2 location = port } }")
    with pytest.raises(ValueError, match="off their sites"):
        ss.merchant_house_rows(_sim(port={}, inland={}, bay={}), doc, {"houses": ["VEN:trade_office:inland:1"]})
    with pytest.raises(ValueError, match="bad entry"):
        ss.merchant_house_rows(_sim(port={}, inland={}, bay={}), doc, {"houses": ["VEN:temple:port:1"]})


def _country_types() -> dict[str, str]:
    vanilla = LoadOrderConfig.load(ROOT / "constructor.load_order.toml").vanilla_root
    path = MOD / "main_menu/setup/1337/10_countries.txt"
    if not path.exists():
        path = vanilla / "game/main_menu/setup/1337/10_countries.txt"
    out = {}
    countries = _first(next(iter(parse_file(path).values("countries"))), "countries")  # countries = { countries = { TAG } }
    for e in countries.entries:
        if isinstance(e.value, CList) and re.fullmatch(r"[A-Z0-9_]{3}", e.key):
            out[e.key] = str(_first(e.value, "type") or "")
    return out


def test_configured_start_houses_follow_the_rules() -> None:
    """The start list (constructor.toml [worldbuilder.start.merchant_houses]): one house per owner and market (the
    1337 markets of config/start_markets.txt), no landless bank or trading house as builder except the listed ones, step
    1 or 2, and step 2 only in a market centre or megalopolis."""
    import tomllib

    raw = tomllib.loads((ROOT / "constructor.toml").read_text(encoding="utf-8"))["worldbuilder"]["start"]["merchant_houses"]
    houses = ss.parse_merchant_houses(raw)
    assert houses
    market = dict(line.split() for line in (ROOT / "config/start_markets.txt").read_text(encoding="utf-8").splitlines()
                  if line.strip() and not line.startswith("#"))
    seen = {}
    for key, tag, loc, step in houses:
        assert loc in market, loc
        assert (tag, market[loc]) not in seen, f"{tag}: {loc} and {seen.get((tag, market[loc]))} share the market"
        seen[tag, market[loc]] = loc
        assert step in (1, 2), (tag, loc)
        if step == 2:
            assert market[loc] == loc or loc == "constantinople", (tag, loc)
    types = _country_types()
    landless = set(raw.get("landless_builders", ()))
    assert landless <= {t for t, kind in types.items() if kind == "building"}
    for _key, tag, _loc, _step in houses:
        assert tag in types, tag
        assert types[tag] != "building" or tag in landless, tag
