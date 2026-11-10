"""Construction Plan, the Towns and Buildings tab: public buildings, town and city upgrades, urban rights
(src/prosper_or_perish_constructor/construction_plan_country.py, mod/pp/.../pp_construction_plan_country*)."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import pytest

from prosper_or_perish_constructor import building_footprint
from prosper_or_perish_constructor import construction_plan as cp
from prosper_or_perish_constructor import construction_plan_country as cc
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
MOD = ROOT / "mod" / "pp"
COMMON = MOD / "in_game/common"
SCRIPT_FILES = (cc.EFFECTS, cc.TRIGGERS, cc.VALUES, cc.SCRIPTED_GUIS)
SCRIPT_FOLDERS = ("scripted_effects", "scripted_triggers", "script_values", "scripted_guis")
PP_RIGHTS = 35  # 17 goods with a charter and its rights, and the iron right
SWITCHED_OFF = 18  # vanilla's bundled specialization rights and charters, switched off by the mod


def _vanilla() -> Path:
    return vanilla_root(ROOT, PROJECT)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _code(path: Path) -> str:
    return re.sub(r"#[^\n]*", "", _read(path))


def _block(text: str, name: str) -> str:
    match = re.search(rf"^{re.escape(name)} = \{{\n(.*?)^\}}", text, re.MULTILINE | re.DOTALL)
    assert match, name
    return match.group(1)


def _tokens(text: str) -> str:
    return " ".join(text.split())


@lru_cache(maxsize=1)
def _built() -> tuple[cc.Result, dict[Path, str]]:
    return cc.build(ROOT, PROJECT, MOD, _vanilla())


def _result() -> cc.Result:
    return _built()[0]


@lru_cache(maxsize=1)
def _config() -> cc.Config:
    return cc.load_config(PROJECT)


def _defined(folder: str) -> set[str]:
    names: set[str] = set()
    for path in (COMMON / folder).glob("*.txt"):
        names.update(re.findall(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{", _read(path), re.MULTILINE))
    return names


# ---- the generated files ---------------------------------------------------------------------------------------------


def test_generated_files_are_up_to_date() -> None:
    result, files = _built()
    for path, text in files.items():
        assert (MOD / path).is_file(), f"{path}: run ppc finalize"
        assert (MOD / path).read_text(encoding="utf-8") == text, f"{path}: run ppc finalize"
    assert result.missing == [] and result.duplicate_lines == [] and result.missing_icons == []
    assert result.unknown_order == []


def test_tracked_paths_fit_windows() -> None:
    for path in [*SCRIPT_FILES, cc.GUI, cc.LOC]:
        relative = (Path("mod/pp") / path).as_posix()
        assert len(relative) <= 109 and re.fullmatch(r"[A-Za-z0-9._/\-]+", relative), relative


def test_braces_balance_in_every_generated_file() -> None:
    for path in [*SCRIPT_FILES, cc.GUI]:
        text = re.sub(r"#[^\n]*", "", re.sub(r'"[^"\n]*"', '""', _read(MOD / path)))  # a "#format" is no comment
        assert text.count("{") == text.count("}"), path


def test_group_is_registered_in_the_build() -> None:
    cli = (ROOT / "src/prosper_or_perish_constructor/cli.py").read_text(encoding="utf-8")
    assert cli.index("construction_plan.apply(") < cli.index("construction_plan_country.apply(")
    assert cp.GROUP_WHY.get("country", cc.WHY) == cc.WHY


# ---- public buildings ------------------------------------------------------------------------------------------------


def test_every_configured_building_exists_and_has_an_icon() -> None:
    config, result = _config(), _result()
    assert [building.key for building in result.buildings] == list(config.public_buildings)
    known = cp.defined_buildings(MOD, _vanilla())
    gui = _read(MOD / cc.GUI)
    for building in result.buildings:
        assert set(building.tiers) <= known, building.key
        icon = f"{building.key}.dds"
        places = [root / icons / cc.BUILDING_ICONS / icon for root in (MOD, _vanilla() / "game") for icons in cc.ICON_ROOTS]
        assert any(place.is_file() for place in places), f"{building.key}: no icon, its tile would draw nothing"
        assert f'texture = "gfx/interface/icons/buildings/{icon}"' in gui, building.key


def test_a_missing_icon_takes_the_tile_out(tmp_path: Path) -> None:
    assert cc.icon_texture(cc.BUILDING_ICONS, "university", MOD, _vanilla()) == "gfx/interface/icons/buildings/university.dds"
    assert cc.icon_texture(cc.BUILDING_ICONS, "no_such_building", MOD, _vanilla()) is None
    assert cc.icon_texture(cc.BUILDING_ICONS, "university", tmp_path, tmp_path) is None


def test_no_dlc_only_key_in_the_script() -> None:
    """A key only a DLC folder defines must not appear in the mod's script (AGENTS.md, DLC Content)."""
    result = _result()
    assert not set(result.switched_off) & set(result.dlc_rights)
    dlc_buildings = building_footprint.dlc_only_buildings(_vanilla())
    for building in result.buildings:
        assert not set(building.tiers) & dlc_buildings, building.key
    code = "".join(_code(MOD / path) for path in SCRIPT_FILES) + _read(MOD / cc.GUI) + _read(MOD / cc.LOC)
    for key in result.dlc_rights:
        assert not re.search(rf"\b{key}\b", code), key


def test_other_rule_groups_buildings_are_not_public_buildings() -> None:
    config, plan = _config(), cp.load_config(PROJECT)
    theirs = {*plan.kitchens, *plan.taverns, *plan.granaries, *plan.granges, *plan.yards, *plan.logistics_order,
              "market_village"}
    from prosper_or_perish_constructor import arable_land_bar

    theirs |= {b.key for b in arable_land_bar.model(MOD, _vanilla() / "game").improvements}
    tiers = {tier for building in _result().buildings for tier in building.tiers}
    assert not tiers & theirs, sorted(tiers & theirs)
    assert len(set(config.public_buildings)) == len(config.public_buildings)


def test_a_line_is_one_tile() -> None:
    lines = {building.key: building.tiers for building in _result().buildings}
    assert lines["dock"] == ("naval_base", "grand_shipyard", "shipyard", "dry_dock", "dock")
    assert lines["early_council_hall"] == ("modern_council_hall", "council_hall", "early_council_hall")
    assert lines["university"] == ("university",)
    seen = [tier for tiers in lines.values() for tier in tiers]
    assert len(seen) == len(set(seen)), "a building is on two tiles"
    gui = _read(MOD / cc.GUI)
    # a tile stands once in every row its place can fall in (the grid wraps: its place is never past its number)
    for number, (key, tiers) in enumerate(lines.items()):
        assert gui.count(f"MakeScopeFlag('pub_{key}')") == number // _config().tiles_per_row + 1, key
        for tier in tiers[:-1]:
            assert f"MakeScopeFlag('pub_{tier}')" not in gui and f"buildings/{tier}.dds" not in gui, tier
    # the rule: only the highest tier the country can build, highest first; never where a tier of the line stands
    buildings = _block(_code(MOD / cc.EFFECTS), "pp_cplan_country_buildings")
    dock = buildings[buildings.index("has_variable = pp_cplan_pub_dock"):buildings.index("has_variable = pp_cplan_pub_bridge")]
    tried = re.findall(r"(if|else_if) = \{\s*limit = \{ can_build_building = building_type:(\w+) \}\s*"
                       r"pp_cplan_country_public = \{ type = (\w+) line = dock ", dock)
    assert [(word, tier) for word, tier, _ in tried] == [("if", "naval_base"), ("else_if", "grand_shipyard"),
                                                         ("else_if", "shipyard"), ("else_if", "dry_dock"), ("else_if", "dock")]
    assert all(tier == built for _, tier, built in tried)
    stands = _block(_code(MOD / cc.TRIGGERS), "pp_cplan_pub_line_dock")
    assert re.findall(r"has_building_with_at_least_one_level = (\w+)", stands) == list(lines["dock"])
    show = _block(_code(MOD / cc.VALUES), "pp_cplan_pub_show_dock")
    assert re.findall(r"can_build_building = building_type:(\w+)", show) == list(lines["dock"])


def test_lines_from_a_small_database() -> None:
    def entry(body: str, dlc: bool = False) -> cc.Entry:
        return cc.Entry([body], dlc)

    buildings = {
        "hut": entry("max_levels = 1"),
        "house": entry("obsolete = hut"),
        "hall": entry("obsolete = house\n\tobsolete = hut"),
        "palace": entry("obsolete = hall", dlc=True),
        "mill": entry("unique_production_methods = { obsolete = nothing }"),
    }
    lines, missing, duplicates = cc.building_lines(buildings, ("hut", "mill", "house", "tower", "palace"))
    assert lines == {"hut": ("hall", "house", "hut"), "mill": ("mill",)}
    assert missing == ["tower", "palace"]  # not in the game; only in a DLC folder
    assert duplicates == ["house"]
    # the later tier listed first: the earlier one would repeat it
    assert cc.building_lines(buildings, ("house", "hut"))[2] == ["hut"]


def test_public_building_rule() -> None:
    effects = _code(MOD / cc.EFFECTS)
    group = _block(effects, "pp_cplan_group_country")
    # script time (2026-11-10): one rule a look, each in its own months; while the group saves it does not look,
    # it only goes for what it saves for once its purse can pay
    assert _tokens(group) == _tokens(
        "if = { limit = { pp_cplan_country_w > 0 } "
        "if = { limit = { pp_cplan_saving = { why = 107 } } pp_cplan_group_target = { why = 107 do = pp_cplan_country_target } } "
        "else_if = { limit = { OR = { pp_cplan_looks_upgrades = yes pp_cplan_looks_public = yes pp_cplan_looks_ranks = yes } } "
        "pp_cplan_group_start = { why = 107 } "
        "if = { limit = { pp_cplan_looks_upgrades = yes } pp_cplan_country_upgrades = yes } "
        "if = { limit = { pp_cplan_looks_public = yes } pp_cplan_country_buildings = yes } "
        "if = { limit = { pp_cplan_looks_ranks = yes } pp_cplan_country_ranks = yes } } }")
    assert _tokens(_block(effects, "pp_cplan_look_country_all")) == _tokens(
        "pp_cplan_group_start = { why = 107 } pp_cplan_country_upgrades = yes pp_cplan_country_buildings = yes "
        "pp_cplan_country_ranks = yes")
    public = _block(effects, "pp_cplan_country_public")
    limit = public[public.index("limit = {"):public.index("order_by")]
    for check in ("pp_cplan_country_site = yes", "max_control >= scope:pp_cplan_country.pp_cplan_country_control_line",
                  "NOT = { pp_cplan_pub_line_$line$ = yes }", "can_build_building = building_type:$type$"):
        assert check in limit, check
    # the construction goods are asked in the body: where the market lacks them nothing starts and the window counts it
    # (in game 2026-11-10 a ticked Library did nothing where the market had no books, and no reason showed)
    assert "pp_cplan_goods_here_$demand$" not in limit
    body = public[public.index("check_range_bounds = no"):]
    assert _tokens(body).startswith("check_range_bounds = no if = { limit = { pp_cplan_goods_here_$demand$ = yes }")
    assert _tokens(body).endswith("pp_cplan_construct = { type = $type$ why = 107 } } else = { pp_cplan_note_goods = { why = 107 } } }")
    assert "order_by = pp_cplan_country_control_here" in public
    # the reason for the window and a fresh "waiting for gold" count per location, before the construction
    start = public.index("pp_cplan_construct = { type = $type$ why = 107 }")
    for line in ("name = pp_cplan_rv", "name = pp_cplan_rs value = 1", "remove_variable = pp_cplan_noted"):
        assert 0 < public.index(line) < start, line
    site = _block(_code(MOD / cc.TRIGGERS), "pp_cplan_country_site")
    assert _tokens(site) == ("NOT = { integration_level = conquered } NOT = { has_variable = pp_lprof_xc } "
                             "pp_cplan_site_free = yes")
    # the ticked types in the config's order, the country's part of the can-build check once per type
    buildings = _block(effects, "pp_cplan_country_buildings")
    assert re.findall(r"^\tif = \{\n\t\tlimit = \{ has_variable = pp_cplan_pub_(\w+) \}", buildings, re.MULTILINE) \
        == list(_config().public_buildings)
    # the construction goods trigger of every tier exists (construction_plan.py writes one per demand)
    demands = set(re.findall(r"demand = (\w+) \}", buildings))
    assert demands and all(f"pp_cplan_goods_here_{demand}" in _defined("scripted_triggers") for demand in demands)


def test_group_counts_only_while_something_is_ticked() -> None:
    """The monthly pass counts the group's weight only while pp_cplan_country_active is 1: a public building ticked or
    an upgrade switched on (else its part of the gold would be held back for nothing). The rights cost no gold."""
    active = _block(_code(MOD / cc.VALUES), "pp_cplan_country_active")
    assert _tokens(active).startswith("value = 0 if = { limit = { OR = {") and _tokens(active).endswith("} } value = 1 }")
    expected = ["pp_cplan_upgrade", "pp_cplan_rank_town", "pp_cplan_rank_city",
                *(f"pp_cplan_pub_{key}" for key in _config().public_buildings)]
    assert re.findall(r"has_variable = (\w+)", active) == expected
    # the names the monthly pass generates are not defined here
    for path in SCRIPT_FILES:
        defined = set(re.findall(r"^(\w+) = \{", _code(MOD / path), re.MULTILINE))
        assert not {name for name in defined if re.fullmatch(
            r"pp_cplan_(?:country_w|share_country|part_country|d_country_\w+|h_country_\w+)", name)}, path


# ---- building upgrades -----------------------------------------------------------------------------------------------


def _obsolete_pairs() -> list[tuple[str, str]]:
    """(older tier, successor) for every building type of the base game and the mod that names one with obsolete =,
    read by counting braces (the mod's files do not indent), after the load order."""
    by_name: dict[str, Path] = {}
    for root in (_vanilla() / "game", MOD):
        for path in (root / cc.BUILDING_TYPES).glob("*.txt"):
            by_name[path.name] = path
    older: dict[str, list[str]] = {}  # type -> the older tiers it names
    for name in sorted(by_name):
        depth, current = 0, None
        for token in re.finditer(r"\{|\}|([A-Za-z0-9_:]+)\s*=\s*(\{|[A-Za-z0-9_.\-]+)", _code(by_name[name])):
            if token.group(0) == "{":
                depth += 1
            elif token.group(0) == "}":
                depth -= 1
            elif token.group(2) == "{":
                if depth == 0:
                    mode, _, key = token.group(1).rpartition(":")
                    if mode in ("INJECT", "TRY_INJECT"):
                        current = key if key in older else None
                    elif mode == "TRY_REPLACE" and key not in older:
                        current = None
                    else:
                        older[key] = []
                        current = key
                depth += 1
            elif depth == 1 and token.group(1) == "obsolete" and current is not None:
                older[current].append(token.group(2))
    return [(old, key) for key, olds in older.items() for old in olds if old in older and old != key]


def test_successor_map_holds_every_type_with_an_older_tier() -> None:
    pairs = _result().upgrades
    assert len(pairs) == len(set(pairs)) > 100
    assert set(pairs) == set(_obsolete_pairs())
    assert ("dock", "dry_dock") in pairs and ("early_council_hall", "council_hall") in pairs
    assert ("dock", "shipyard") not in pairs  # only the direct successor, as the game's upgrade button
    dlc = building_footprint.dlc_only_buildings(_vanilla())
    assert not {key for pair in pairs for key in pair} & dlc
    # the rule's chain: every pair once, in the map's order (several successors of one older tier: the game's file order)
    chain = _block(_code(MOD / cc.EFFECTS), "pp_cplan_country_upgrade_building")
    tried = re.findall(r"(if|else_if) = \{\n\t+limit = \{ building_type = building_type:(\w+) scope:pp_cplan_country = "
                       r"\{ can_build_building = building_type:(\w+) \} \}\n\t+scope:pp_cplan_up_site = "
                       r"\{ pp_cplan_country_upgrade_to = \{ type = (\w+) demand = (\w+) \} \}", chain)
    assert [(older, successor) for _, older, successor, _, _ in tried] == pairs
    assert [word for word, *_ in tried] == ["if"] + ["else_if"] * (len(pairs) - 1)
    assert all(successor == built for _, _, successor, built, _ in tried)
    goods = _defined("scripted_triggers")
    assert all(f"pp_cplan_goods_here_{demand}" in goods for *_, demand in tried)
    # no location-side can-build check: the game's upgrade does not need it (it is what freezes a line)
    assert "location_and_owner_can_build" not in chain and chain.count("can_build_building") == len(pairs)


def test_upgrade_pairs_from_a_small_database() -> None:
    def entry(body: str, dlc: bool = False) -> cc.Entry:
        return cc.Entry([body], dlc)

    buildings = {
        "hut": entry("max_levels = 1"),
        "house": entry("obsolete = hut"),
        "lodge": entry("obsolete = hut\n\tunique_production_methods = { obsolete = house }"),
        "hall": entry("obsolete = house\n\tobsolete = hut\n\tobsolete = ruin"),
        "palace": entry("obsolete = hall", dlc=True),
        "keep": entry("obsolete = keep"),
    }
    assert cc.upgrade_pairs(buildings) == [("hut", "house"), ("hut", "lodge"), ("house", "hall"), ("hut", "hall")]


def test_upgrade_rule() -> None:
    effects, triggers = _code(MOD / cc.EFFECTS), _code(MOD / cc.TRIGGERS)
    group = _block(effects, "pp_cplan_group_country")
    assert group.index("pp_cplan_country_upgrades = yes") < group.index("pp_cplan_country_buildings = yes") \
        < group.index("pp_cplan_country_ranks = yes")
    rule = _block(effects, "pp_cplan_country_upgrades")
    assert rule.count("has_variable = pp_cplan_upgrade") == 1 and rule.strip().startswith("if = {")
    limit = rule[rule.index("ordered_owned_location"):rule.index("order_by")]
    assert "pp_cplan_country_site = yes" in limit  # not conquered, no pp_lprof_xc, a free construction slot
    assert "any_buildings_in_location = { pp_cplan_country_upgradable = yes }" in limit
    assert "max_control >=" not in rule and "order_by = pp_cplan_country_control_here" in rule  # no line, highest first
    start = rule.index("every_buildings_in_location")
    for line in ("save_scope_as = pp_cplan_up_site", "name = pp_cplan_rv value = { value = max_control multiply = 100 add = 100 }",
                 "name = pp_cplan_rs value = 3", "remove_variable = pp_cplan_noted"):
        assert 0 < rule.index(line) < start, line
    assert "limit = { pp_cplan_country_upgradable = yes }\n\t\t\t\tpp_cplan_country_upgrade_building = yes" in rule
    # a standing, open building the country can upgrade: a closed older tier is left alone
    assert _tokens(_block(triggers, "pp_cplan_country_upgradable")) == \
        "building_level > 0 is_opened = yes building_can_be_upgraded_by = scope:pp_cplan_country"
    # one upgrade a location a month: the first try marks the location, the mark goes after the location
    chain = _block(effects, "pp_cplan_country_upgrade_building")
    assert chain.strip().startswith("if = {\n\t\tlimit = { NOT = { scope:pp_cplan_up_site = { has_variable = pp_cplan_up_try } } }")
    to = _block(effects, "pp_cplan_country_upgrade_to")
    assert _tokens(to) == ("if = { limit = { pp_cplan_goods_here_$demand$ = yes } set_variable = { name = pp_cplan_up_try "
                           "value = yes } pp_cplan_construct = { type = $type$ why = 107 } } "
                           "else = { pp_cplan_note_goods = { why = 107 } }")
    assert rule.index("remove_variable = pp_cplan_up_try") > start
    # the construction is the plan's like any building's (the purse, reserve, ledger, closed successor, free slot)
    scoped = _block(_code(COMMON / "scripted_effects/pp_construction_plan.txt"), "pp_cplan_construct_scoped")
    for check in ("pp_cplan_site_free = yes", "NOT = { pp_cplan_saving = { why = $why$ } }",
                  "pp_cplan_affordable = { why = $why$ }", "is_opened = no"):
        assert check in scoped, check
    assert "can_build_building" not in scoped  # nothing there asks the location's part again
    # one toggle, in the public buildings' header row, and the group counts while it is on
    gui = _read(MOD / cc.GUI)
    assert gui.count("MakeScopeFlag('upgrade')") == 1
    assert gui.index("PP_CPLANC_PUB\"") < gui.index("MakeScopeFlag('upgrade')") < gui.index("MakeScopeFlag('control_line')") \
        < gui.index("MakeScopeFlag('pub_")
    assert "flag:upgrade = { pp_cplan_flip = { var = pp_cplan_upgrade } }" in _code(MOD / cc.SCRIPTED_GUIS)
    assert cc.STEP_UPGRADE == 3


# ---- towns and cities ------------------------------------------------------------------------------------------------


def _vanilla_rank(name: str) -> str:
    """A rank's definition in the base game's file, read the simple way."""
    text = _code(_vanilla() / "game" / cc.LOCATION_RANKS / "00_default.txt")
    return re.search(rf"^{name} = \{{\n(.*?)^\}}", text, re.MULTILINE | re.DOTALL).group(1)


def test_ranks_are_read_from_the_games_files() -> None:
    """The gate is the rank's own: the rank below, the game's population minimum, its construction goods and price."""
    town, city = _result().ranks
    assert (town.key, town.source, city.key, city.source) == ("town", "rural_settlement", "city", "town")
    demands = _code(_vanilla() / "game" / cc.GOODS_DEMAND / "00_goods_demand.txt") \
        if (_vanilla() / "game" / cc.GOODS_DEMAND / "00_goods_demand.txt").is_file() else \
        "".join(_code(path) for path in sorted((_vanilla() / "game" / cc.GOODS_DEMAND).glob("*.txt")))
    for rank in (town, city):
        body = _vanilla_rank(rank.key)
        allow = re.search(r"^\tallow = \{\n(.*?)^\t\}", body, re.MULTILINE | re.DOTALL).group(1)
        assert rank.population == float(re.search(r"population >= ([0-9.]+)", allow).group(1)) > 0, rank.key
        assert "modifier:cannot_upgrade_location = no" in allow, rank.key  # the other condition the rule asks itself
        demand = re.search(r"^\tconstruction_demand = (\w+)", body, re.MULTILINE).group(1)
        goods = re.search(rf"^{demand} = \{{\n(.*?)^\}}", demands, re.MULTILINE | re.DOTALL).group(1)
        assert dict(rank.goods) == {good: float(n) for good, n in re.findall(r"^\t(\w+) = ([0-9.]+)\s*$", goods, re.MULTILINE)}
        assert len(rank.goods) >= 3 and rank.price > 0
    assert "upgrade_from = town" in _vanilla_rank("city")
    assert city.population > town.population and city.price > town.price
    # a mod's inject can raise the minimum: every allow block must pass
    entry = cc.Entry(["allow = {\n\tpopulation >= 5\n\tmodifier:cannot_upgrade_location = no\n}", "allow = { population >= 12.5 }"], False)
    assert cc.rank_minimum_population(entry) == 12.5
    assert cc.rank_minimum_population(cc.Entry(["rank_modifier = { local_population_capacity = 20 }"], False)) == 0


def test_rank_upgrades() -> None:
    effects = _code(MOD / cc.EFFECTS)
    ranks = _block(effects, "pp_cplan_country_ranks")
    town = ranks[:ranks.index("has_variable = pp_cplan_rank_city")]
    city = ranks[ranks.index("has_variable = pp_cplan_rank_city"):]
    assert "has_variable = pp_cplan_rank_town" in town
    found = {rank.key: rank for rank in _result().ranks}
    for part, rank in ((town, found["town"]), (city, found["city"])):
        limit = part[part.index("limit = {\n"):part.index("order_by")]
        checks = ["pp_cplan_country_site = yes", f"location_rank = location_rank:{rank.source}",
                  "modifier:cannot_upgrade_location = no", f"population >= {rank.population:g}"]
        if rank.key == "town":
            checks.append("population >= scope:pp_cplan_country.pp_cplan_country_town_pop")
        assert [line.strip() for line in limit.splitlines()[1:] if line.strip() not in ("", "}")] == checks, rank.key
        assert "order_by = pp_cplan_country_pop_here" in part
        # the construction goods are asked in the body: an upgrade the market lacks them for is counted for the window
        body = _tokens(part[part.index("check_range_bounds = no"):])
        assert (f"if = {{ limit = {{ pp_cplan_country_goods_{rank.key} = yes }} pp_cplan_country_rank_up = {{ rank = "
                f"{rank.key} n = {cc.SAVE_RANK[rank.key]} }} }} else = {{ pp_cplan_note_goods = {{ why = 107 }} }}") in body, rank.key
    # the engine's can_become_rank is not the gate (in game 2026-11-10: false everywhere while the upgrade worked)
    for path in SCRIPT_FILES:
        assert "can_become_rank" not in _code(MOD / path), path
    # the construction goods in the market: the plan's months of the draw of every good of the rank's demand
    months = cp.load_config(PROJECT).construction_goods_months
    triggers, values = _code(MOD / cc.TRIGGERS), _code(MOD / cc.VALUES)
    low, high = cp.price_impact_bounds(MOD, _vanilla())
    for rank in found.values():
        goods = _block(triggers, f"pp_cplan_country_goods_{rank.key}")
        assert re.findall(r'"stockpile_in_market\(goods:(\w+)\)" >= ([0-9.]+)', goods) \
            == [(good, f"{amount * months:g}") for good, amount in rank.goods], rank.key
        assert goods.strip().startswith("market ?= {")
        # its cost here: the game's price x the construction goods' price factor, as the game charges it
        cost = _block(values, f"pp_cplan_country_cost_{rank.key}")
        assert re.findall(r'value = "market\.market_price\(goods:(\w+)\)" divide = "default_price\(goods:(\w+)\)" '
                          rf"min = {low:g} max = {high:g} multiply = ([0-9.]+)", cost) \
            == [(good, good, f"{amount:g}") for good, amount in rank.goods], rank.key
        assert f"divide = {sum(amount for _, amount in rank.goods):g}" in cost
        assert _tokens(cost).startswith("value = 1 if = { limit = { market ?= { always = yes } } value = 0")
        assert _tokens(cost).endswith(f"}} multiply = {rank.price:g}")


def test_rank_upgrade_checks_the_budget_and_books_only_what_was_paid() -> None:
    up = _block(_code(MOD / cc.EFFECTS), "pp_cplan_country_rank_up")
    limit = up[up.index("limit = {"):up.index("construct_location_rank")]
    # the group's purse pays (budgets that save, 2026-11-10): not while it saves for something, and the cost must fit
    # in the purse and in the gold above the reserve, as pp_cplan_affordable asks for a building
    assert "NOT = { pp_cplan_saving = { why = 107 } }" in limit
    assert "pp_cplan_country_cost_$rank$ <= scope:pp_cplan_country.pp_cplan_purse_n_107" in limit
    assert "pp_cplan_country_cost_$rank$ <= scope:pp_cplan_country.pp_cplan_free_gold" in limit
    assert "pp_cplan_affordable" in _defined("scripted_triggers") and "pp_cplan_saving" in _defined("scripted_triggers")
    assert "pp_cplan_purse_n_107" in _defined("script_values")
    order = ["name = pp_cplan_gold_before value = { value = gold add = 1000000 }",
             "construct_location_rank = location_rank:$rank$", "pp_cplan_rank_charge = { rank = $rank$ }",
             "name = pp_cplan_paid value = { value = var:pp_cplan_gold_before subtract = 1000000 subtract = gold }",
             "remove_variable = pp_cplan_gold_before", "limit = { scope:pp_cplan_paid > 0 }",
             "change_variable = { name = pp_cplan_spent add = scope:pp_cplan_paid }"]
    places = [up.index(line) for line in order]
    assert places == sorted(places)
    # the effect refuses silently where the game's own conditions fail: nothing is booked unless gold was paid
    booked = up[up.index("limit = { scope:pp_cplan_paid > 0 }"):up.rindex("else = {")]
    for name in ("pp_cplan_spent", "pp_cplan_started", "pp_cplan_dspent_107", "pp_cplan_dn_107", "pp_cplan_hit",
                 "pp_cplan_log ", "pp_cplan_log_107", "pp_cplan_log_rank", "pp_cplan_log_cost_107",
                 "pp_cplan_log_step_107", "pp_cplan_log_val_107", "PP_CPLAN_TLOG_107"):
        assert up.index(name) > up.index("limit = { scope:pp_cplan_paid > 0 }"), name
    assert "construct_location_rank" not in booked
    paid, waiting = booked, up[up.rindex("else = {"):]
    assert "save_temporary_scope_value_as = { name = pp_cplan_wc value = pp_cplan_country_cost_$rank$ }" in waiting
    for line in ("change_variable = { name = pp_cplan_spent add = scope:pp_cplan_paid }",
                 "change_variable = { name = pp_cplan_started add = 1 }",
                 "change_variable = { name = pp_cplan_dspent_107 add = scope:pp_cplan_paid }",
                 "change_variable = { name = pp_cplan_dn_107 add = 1 }",
                 "set_variable = { name = pp_cplan_hit value = yes }",
                 "pp_cplan_purse_pay = { why = 107 }",  # the purse falls by what was really paid
                 "add_to_variable_list = { name = pp_cplan_log target = scope:pp_cplan_site }",
                 "add_to_variable_list = { name = pp_cplan_log_107 target = scope:pp_cplan_site }",
                 "set_variable = { name = pp_cplan_log_rank value = yes }",
                 "set_variable = { name = pp_cplan_log_cost_107 value = scope:pp_cplan_paid }",
                 "change_variable = { name = pp_cplan_log_cost_107 add = scope:pp_cplan_paid }",
                 "set_variable = { name = pp_cplan_log_step_107 value = 2 }",
                 "set_variable = { name = pp_cplan_log_val_107 value = scope:pp_cplan_rv }"):
        assert line in paid, line
    # the group's own entry of the location (another rule group's stays untouched: each has its own); the reason of a
    # building the group started here in the same pass (a location with two construction slots) stays
    guard = paid[paid.index("limit = { NOT = { has_variable = pp_cplan_log_step_107 } }"):]
    written = guard[:guard.index("\n\t\t\t}\n")]
    assert all(f"name = pp_cplan_log_{name}_107 " in written for name in ("step", "val"))
    assert "pp_cplan_log_why" not in up
    assert "pp_cplan_log_types" not in up  # an upgrade is no building: the window names it by pp_cplan_log_rank
    # test runs: the rule group and the location in debug.log, as pp_cplan_construct_now writes them (ppc plan-report)
    assert _tokens(paid[paid.index("has_variable = pp_cplan_ai_test"):]).startswith(
        "has_variable = pp_cplan_ai_test } } debug_log = PP_CPLAN_TLOG_107 debug_log_scopes = no }")
    assert "PP_CPLAN_TLOG_107:" in _read(MOD / "main_menu/localization/english/pp_construction_plan_l_english.yml")
    for line in ("set_variable = { name = pp_cplan_wait value = yes }",
                 "limit = { NOT = { has_variable = pp_cplan_noted } }",
                 "set_variable = { name = pp_cplan_noted value = yes }",
                 "change_variable = { name = pp_cplan_dwait_107 add = scope:pp_cplan_wc }",
                 "change_variable = { name = pp_cplan_dwn_107 add = 1 }",
                 # the first thing of the pass the group cannot pay for is what it saves for: the location, the
                 # cost and which upgrade (an upgrade has no building type)
                 "limit = { NOT = { has_variable = pp_cplan_save_cost_107 } }",
                 "set_variable = { name = pp_cplan_save_cost_107 value = { value = scope:pp_cplan_wc add = 100 } }",
                 "set_variable = { name = pp_cplan_save_loc_107 value = scope:pp_cplan_site }",
                 "set_variable = { name = pp_cplan_save_rank_107 value = $n$ }"):
        assert line in waiting, line
    assert cc.SAVE_RANK == {"town": 101, "city": 102}


def test_the_charging_decision_sits_in_one_effect_that_charges_nothing_yet() -> None:
    """Vanilla never uses construct_location_rank; an in-game test decides whether the plan must pay the price."""
    effects = _code(MOD / cc.EFFECTS)
    charge = _block(effects, "pp_cplan_rank_charge")
    assert _tokens(charge) == "if = { limit = { always = no } pay_price = price:$rank$_upgrade }"
    assert effects.count("pay_price = price:$rank$_upgrade") == 1 and effects.count("pp_cplan_rank_charge = {") == 2
    # in game 2026-11-10 the effect takes the game's price itself: the comment says so
    comment = _read(MOD / cc.EFFECTS)
    comment = comment[:comment.index("\npp_cplan_rank_charge = {")].rsplit("\n\n", 1)[1]
    assert "charges nothing, and that is right" in comment and "2026-11-10" in comment
    prices = cc.database(MOD, _vanilla(), cc.PRICES)
    assert {"town_upgrade", "city_upgrade"} <= set(prices)


# ---- urban rights ----------------------------------------------------------------------------------------------------


def _right_files() -> list[Path]:
    """The town rights files of the base game and the mod (not the DLC folders), in load order."""
    by_name: dict[str, Path] = {}
    for root in (_vanilla() / "game", MOD):
        for path in (root / cc.TOWN_RIGHTS).glob("*.txt"):
            by_name[path.name] = path
    return [by_name[name] for name in sorted(by_name)]


def _definitions() -> dict[str, list[str]]:
    """Right -> its standing definition and injects, read the simple way: blocks that start in the first column."""
    found: dict[str, list[str]] = {}
    for path in _right_files():
        for mode, key, body in re.findall(r"^(?:([A-Z_]+):)?(\w+) = \{\n(.*?)^\}", _code(path), re.MULTILINE | re.DOTALL):
            if mode in ("INJECT", "TRY_INJECT"):
                if key in found:
                    found[key].append(body)
            elif mode != "TRY_REPLACE" or key in found:
                found[key] = [body]
    return found


def _part(body: str, name: str) -> str | None:
    """A potential or allow block of a definition body (one tab deep), by its indentation."""
    match = re.search(rf"^\t{name} = \{{(.*?)\}}[ \t]*$", body, re.MULTILINE)  # on one line
    if match and "{" not in match.group(1):
        return match.group(1)
    match = re.search(rf"^\t{name} = \{{[ \t]*\n(.*?)^\t\}}", body, re.MULTILINE | re.DOTALL)
    return match.group(1) if match else None


def test_every_right_of_the_database_is_there_once() -> None:
    result = _result()
    definitions = _definitions()
    off = {key for key, bodies in definitions.items()
           if any(_tokens(_part(body, name) or "") == "always = no" for body in bodies for name in ("potential", "allow"))}
    assert len(off) == SWITCHED_OFF and off == set(result.switched_off)
    keys = [right.key for right in result.rights]
    assert len(keys) == len(set(keys))
    assert set(keys) == set(definitions) - off
    pp = [key for key in keys if re.fullmatch(r"pp_\w+_(?:charter|rights)", key)]
    assert len(pp) == PP_RIGHTS and "pp_iron_rights" in pp
    assert sum(key.endswith("_charter") for key in pp) == 17 and sum(key.endswith("_rights") for key in pp) == 18
    # every right has its three triggers, its tile, its toggle and its place in the rule, once each
    triggers, effects = _code(MOD / cc.TRIGGERS), _code(MOD / cc.EFFECTS)
    gui, guis = _read(MOD / cc.GUI), _code(MOD / cc.SCRIPTED_GUIS)
    for key in keys:
        for name in ("potential", "allow", "site"):
            assert len(re.findall(rf"^pp_cplan_right_{name}_{key} = \{{", triggers, re.MULTILINE)) == 1, (name, key)
        number = [right.key for right in cc.tile_order(_result().rights)].index(key)
        assert gui.count(f"MakeScopeFlag('right_{key}')") == number // _config().tiles_per_row + 1, key
        assert guis.count(f"flag:right_{key} = {{ pp_cplan_flip = {{ var = pp_cplan_right_{key} }} }}") == 1, key
        assert effects.count(f"pp_cplan_country_grant = {{ right = {key} }}") == 1, key
    # a switched-off right has no trigger, tile, toggle or place in the rule (other rights' own conditions may name it)
    for key in off:
        assert not re.search(rf"pp_cplan_right_(?:potential_|allow_|site_|show_)?{key}\b|[':]right_{key}\b|right = {key}\b",
                             triggers + effects + gui + guis), key


def test_potential_and_allow_are_carried_as_written() -> None:
    """The triggers hold the database's text: the standing definition's block, then the injected ones. Only the spelling
    of a NOT with several conditions differs (NOR, which is what the engine reads)."""
    triggers = _code(MOD / cc.TRIGGERS)
    definitions = _definitions()
    carried = 0
    for right in _result().rights:
        for name in ("potential", "allow"):
            written = [part for body in definitions[right.key] if (part := _part(body, name)) is not None]
            expected = _tokens(" ".join(written))
            body = _block(triggers, f"pp_cplan_right_{name}_{right.key}")
            assert body.count("{") == body.count("}"), (name, right.key)
            lines = _tokens(body)
            if name == "potential" and right.advances:
                lead = (f"has_advance = {right.advances[0]}" if len(right.advances) == 1
                        else "OR = { " + " ".join(f"has_advance = {a}" for a in right.advances) + " }")
                assert lines.startswith(lead), right.key
                lines = lines[len(lead):].strip()
            if not expected:
                assert lines in ("always = yes", ""), (name, right.key)
                continue
            assert lines.replace("NOR = {", "NOT = {") == expected.replace("NOR = {", "NOT = {"), (name, right.key)
            carried += 1
    assert carried > 100
    # samples straight from the files
    assert "country = root" in _block(triggers, "pp_cplan_right_potential_stapelrecht_town_rights")
    iron = _block(triggers, "pp_cplan_right_allow_pp_iron_rights")
    assert "raw_material = goods:iron" in iron and "scope:target = {" in iron
    assert _tokens(_block(triggers, "pp_cplan_right_allow_fortress_town")) == "always = yes"
    assert "NOR = { is_port = yes pp_is_sea_coast = yes }" in _block(triggers, "pp_cplan_right_allow_novo_brdo_charter")


def test_explicit_nor_changes_only_the_spelling() -> None:
    text = "NOT = { a = yes }\nNOT = { a = yes b = no }\nOR = { NOT = { x > 1 scope:y = { z = yes } } NOT = { has_x = flag:q } }"
    assert cc.explicit_nor(text) == (
        "NOT = { a = yes }\nNOR = { a = yes b = no }\nOR = { NOR = { x > 1 scope:y = { z = yes } } NOT = { has_x = flag:q } }")
    assert cc.trigger_lines(("\n\t\tis_port = yes\n\t\tOR = {\n\t\t\ta = b\n\t\t}\n\t",)) == ["\tis_port = yes", "\tOR = {", "\t\ta = b", "\t}"]


def test_load_order_of_a_small_database(tmp_path: Path) -> None:
    game, mod = tmp_path / "vanilla" / "game", tmp_path / "mod"
    for root, name, text in (
        (game, "00_base.txt", "strong = {\n\tallow = { is_capital = yes }\n}\n"
                               "weak = {\n\tupgrades_to = strong\n\tpotential = {\n\t\ttag = AAA # home\n\t}\n}\n"
                               "old = {\n\tpotential = { tag = BBB }\n}\ngone = {\n\tallow = { tag = CCC }\n}\n"),
        (game / "dlc" / "D001_test", "d001.txt", "extra = {\n\tallow = { tag = DDD }\n}\n"),
        (mod, "pp_changes.txt", "TRY_INJECT:weak = {\n\tallow = {\n\t\tscope:target = { is_port = yes }\n\t}\n"
                                "\tpotential = { NOT = { tag = EEE is_ai = yes } }\n}\n"
                                "REPLACE:old = {\n\tis_specialization = yes\n\tpotential = { tag = FFF }\n}\n"
                                "REPLACE:gone = {\n\tpotential = { always = no }\n\tallow = { always = no }\n}\n"
                                "TRY_INJECT:nothing = {\n\tallow = { tag = GGG }\n}\nTRY_REPLACE:nobody = {\n}\n"),
    ):
        folder = root / "in_game/common/town_rights"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(text, encoding="utf-8")
    advances = mod / "in_game/common/advances"
    advances.mkdir(parents=True)
    (advances / "a.txt").write_text("first = {\n\tunlock_town_rights = strong\n}\nsecond = {\n\tunlock_town_rights = strong\n"
                                    "\tunlock_town_rights = old\n}\n", encoding="utf-8")
    icons = mod / "main_menu/gfx/interface/icons/town_rights"
    icons.mkdir(parents=True)
    for name in ("_default", "old"):
        (icons / f"{name}.dds").write_bytes(b"DDS ")
    rights, off, dlc = cc.read_rights(mod, tmp_path / "vanilla")
    assert (off, dlc) == (["gone"], ["extra"])
    by_key = {right.key: right for right in rights}
    assert list(by_key) == ["strong", "weak", "old"]
    assert by_key["strong"].advances == ("first", "second") and by_key["weak"].upgrades_to == "strong"
    # an injected potential or allow is one more block: both must pass
    assert [_tokens(block) for block in by_key["weak"].potential] == ["tag = AAA", "NOT = { tag = EEE is_ai = yes }"]
    assert [_tokens(block) for block in by_key["weak"].allow] == ["scope:target = { is_port = yes }"]
    assert cc.potential_lines(by_key["weak"]) == ["\ttag = AAA", "\tNOR = { tag = EEE is_ai = yes }"]
    assert cc.potential_lines(by_key["strong"]) == ["\tOR = {", "\t\thas_advance = first", "\t\thas_advance = second", "\t}"]
    # a replace drops what stood before it
    assert [_tokens(block) for block in by_key["old"].potential] == ["tag = FFF"] and by_key["old"].specialization
    assert by_key["old"].icon.endswith("town_rights/old.dds") and by_key["weak"].icon.endswith("town_rights/_default.dds")
    assert by_key["weak"].always_shown is False and not by_key["strong"].always_shown
    ordered, unknown = cc.order_rights(rights, ("weak", "missing"))
    assert [right.key for right in ordered] == ["weak", "old", "strong"] and unknown == ["missing"]
    assert cc.upgrade_sources(rights) == {"strong": ["weak"]}


def test_rights_unlocked_by_an_advance_ask_for_it() -> None:
    """The engine offers a right an advance lists under unlock_town_rights only once one of those advances is
    researched (a right no advance lists is unlocked from the start); the potential trigger asks the same."""
    listed: dict[str, list[str]] = {}
    for root in (_vanilla() / "game", MOD):
        for path in sorted((root / cc.ADVANCES).glob("*.txt")):
            for advance, body in re.findall(r"^(?:[A-Z_]+:)?(\w+) = \{\n(.*?)^\}", _code(path), re.MULTILINE | re.DOTALL):
                for right in re.findall(r"^\tunlock_town_rights = (\w+)", body, re.MULTILINE):
                    listed.setdefault(right, []).append(advance)
    by_key = {right.key: right for right in _result().rights}
    assert by_key["flemish_cloth_industries_right"].advances == ("flemish_cloth_making",)
    assert by_key["royal_market_rights"].advances == ("town_rights_enable",)
    assert by_key["pp_cloth_rights"].advances == ("printing_press_advance",) and by_key["pp_cloth_charter"].advances == ()
    triggers = _code(MOD / cc.TRIGGERS)
    known = _advance_keys()
    for key, right in by_key.items():
        assert set(right.advances) == set(listed.get(key, ())), key
        potential = _block(triggers, f"pp_cplan_right_potential_{key}")
        assert set(re.findall(r"^\t+has_advance = (\w+)", potential.split("\n\t", 1)[0] if not right.advances else potential,
                              re.MULTILINE)) >= set(right.advances), key
        assert set(right.advances) <= known, key
    assert sum(bool(right.advances) for right in by_key.values()) >= 24


def _advance_keys() -> set[str]:
    keys: set[str] = set()
    for root in (_vanilla() / "game", MOD):
        for path in (root / cc.ADVANCES).glob("*.txt"):
            keys.update(re.findall(r"^(?:[A-Z_]+:)?(\w+) = \{", _code(path), re.MULTILINE))
    return keys


def test_rights_rule() -> None:
    effects = _code(MOD / cc.EFFECTS)
    rule = _block(effects, "pp_cplan_country_rights")
    limit = rule[rule.index("limit = {"):rule.index("has_variable = pp_cplan_right_")]
    for check in ("has_variable = pp_cplan_rights_on", "modifier:can_grant_town_rights = yes",
                  "political_influence >= pp_cplan_country_influence_need"):
        assert check in limit, check
    result = _result()
    asked = re.findall(r"has_variable = pp_cplan_right_(\w+)\n\t+pp_cplan_right_potential_(\w+) = yes\n\t+\}\n"
                       r"\t+pp_cplan_country_grant = \{ right = (\w+) \}", rule)
    assert [a for a, _, _ in asked] == [right.key for right in result.rights]
    assert all(a == b == c and a != "mark" for a, b, c in asked)
    grant = _block(effects, "pp_cplan_country_grant")
    for line in ("pp_cplan_country_rights_site = yes", "pp_cplan_right_site_$right$ = yes",
                 "order_by = pp_cplan_country_pop_here", "save_scope_as = target",
                 "political_influence >= pp_cplan_country_influence_need", "can_pay_price = price:grant_town_rights",
                 "pp_cplan_right_allow_$right$ = yes", "grant_town_rights = town_rights_type:$right$",
                 "pay_price = price:grant_town_rights"):
        assert line in grant, line
    # the location is scope:target before the allow is asked; the raw effect skips the price, so the country pays it
    assert grant.index("save_scope_as = target") < grant.index("pp_cplan_right_allow_$right$ = yes") \
        < grant.index("grant_town_rights =") < grant.index("\tpay_price =")
    # at most one grant a location a month
    site = _block(_code(MOD / cc.TRIGGERS), "pp_cplan_country_rights_site")
    assert _tokens(site) == ("NOT = { integration_level = conquered } NOT = { has_variable = pp_lprof_xc } "
                             "NOT = { has_variable = pp_cplan_right_mark } has_max_town_rights = no")
    assert "set_variable = { name = pp_cplan_right_mark value = yes }" in grant
    assert rule.rstrip().endswith("}") and "remove_variable = pp_cplan_right_mark" in rule[rule.rindex("every_owned_location"):]
    # the amount kept and the price, from the tab's line and the game's price database
    need = _block(_code(MOD / cc.VALUES), "pp_cplan_country_influence_need")
    price = cc.price_amount(cc.database(MOD, _vanilla(), cc.PRICES), "grant_town_rights", "political_influence")
    assert _tokens(need) == f"value = pp_cplan_country_keep_influence add = {price:g}" and price > 0


def test_rights_order_and_upgrades() -> None:
    result = _result()
    keys = [right.key for right in result.rights]
    by_key = {right.key: right for right in result.rights}
    assert _config().rights_order == ()
    # the specialization rights first, then the rest, each in the game's order
    special = [right.specialization for right in result.rights]
    assert special == sorted(special, reverse=True) and special.count(True) >= PP_RIGHTS
    # a right stands before the charter that upgrades into it: a location that qualifies for both gets the stronger one
    upgrades = [right for right in result.rights if right.upgrades_to]
    assert len(upgrades) >= 19
    triggers = _code(MOD / cc.TRIGGERS)
    for right in upgrades:
        assert keys.index(right.upgrades_to) < keys.index(right.key), right.key
        # upgrading is not part of the plan: where the charter stands, its stronger right is left to the player, and
        # the charter is not granted on top of the right
        for key, other in ((right.upgrades_to, right.key), (right.key, right.upgrades_to)):
            held = re.findall(r"has_town_rights = town_rights_type:(\w+)", _block(triggers, f"pp_cplan_right_site_{key}"))
            assert key in held and other in held, (key, other)
    for key in keys:
        site = _block(triggers, f"pp_cplan_right_site_{key}")
        assert site.strip().startswith("NOR = {") and f"town_rights_type:{key}\n" in site, key
    assert by_key["pp_cloth_charter"].upgrades_to == "pp_cloth_rights" and by_key["staple_port"].upgrades_to == "royal_staple_rights"


def test_every_right_has_an_icon() -> None:
    result = _result()
    icons = [root / folder / cc.RIGHT_ICONS for root in (MOD, _vanilla() / "game") for folder in cc.ICON_ROOTS]
    gui = _read(MOD / cc.GUI)
    own = 0
    for right in result.rights:
        name = Path(right.icon).name
        assert right.icon == f"gfx/interface/icons/town_rights/{name}", right.key
        assert name in (f"{right.key}.dds", "_default.dds"), right.key
        assert any((folder / name).is_file() for folder in icons), f"{right.key}: its tile would draw nothing"
        assert f'texture = "{right.icon}"' in gui, right.key
        own += name != "_default.dds"
    # the mod's own rights all have their picture; a few vanilla rights use the game's default one, as in the game
    assert all(not right.icon.endswith("_default.dds") for right in result.rights if right.key.startswith("pp_"))
    assert own >= 70


# ---- script hygiene --------------------------------------------------------------------------------------------------


def test_every_argument_is_used_and_passed() -> None:
    """A scripted effect or trigger called with an argument it never uses fails to compile."""
    parameters: dict[str, set[str]] = {}
    for folder in ("scripted_effects", "scripted_triggers"):
        for path in sorted((COMMON / folder).glob("pp_construction_plan*.txt")):
            text = _code(path)
            for name in re.findall(r"^(\w+) = \{", text, re.MULTILINE):
                parameters[name] = set(re.findall(r"\$(\w+)\$", _block(text, name)))
    calls = 0
    for path in SCRIPT_FILES:
        for name, arguments in re.findall(r"\b(pp_cplan_\w+) = \{ ((?:\w+ = [\w$]+ ?)+)\}", _code(MOD / path)):
            if name not in parameters:
                continue
            passed = set(re.findall(r"(\w+) = ", arguments))
            assert passed == parameters[name], f"{path.name}: {name} takes {sorted(parameters[name])}, got {sorted(passed)}"
            calls += 1
    assert calls > 150
    for name in ("pp_cplan_country_public", "pp_cplan_country_rank_up", "pp_cplan_rank_charge", "pp_cplan_country_grant"):
        assert parameters[name], name
    assert parameters["pp_cplan_country_public"] == {"type", "line", "demand"}
    # an effect called with "= yes" takes no argument
    for path in SCRIPT_FILES:
        for name in re.findall(r"\b(pp_cplan_\w+) = yes", _code(MOD / path)):
            assert not parameters.get(name), name


def test_every_script_name_exists() -> None:
    """Everything the generated script calls or reads is defined in the mod: its own names and the monthly pass's
    (pp_construction_plan.txt, construction_plan.py)."""
    defined = set().union(*(_defined(folder) for folder in SCRIPT_FOLDERS))
    variable = r"(?:name|has_variable|remove_variable|var|variable|clear_variable_list) = "
    for path in SCRIPT_FILES:
        code = _code(MOD / path)
        used = set(re.findall(r"(?<![\w:.$])(pp_cplan_[a-z0-9_]+)(?![\w$])", re.sub(variable + r"\w+", "", code)))
        used -= {name for name in used if re.search(rf"(?:var|scope|flag):{name}\b", code) and name not in defined}
        used -= {"pp_cplan_pub_line_", "pp_cplan_goods_here_", "pp_cplan_right_site_", "pp_cplan_right_allow_"}  # + $argument$
        missing = sorted(used - defined)
        assert not missing, f"{path.name}: not defined anywhere: {missing[:8]}"
    for name in ("pp_cplan_group_country", "pp_cplan_country_rights", "pp_cplan_country_declare"):
        assert name in _defined("scripted_effects"), name
    # the names the monthly pass gives this group
    for name in ("pp_cplan_country_w", "pp_cplan_purse_n_107", "pp_cplan_free_gold"):
        assert name in _defined("script_values"), name
    for name in ("pp_cplan_site_free", "pp_cplan_saving", "pp_cplan_affordable"):
        assert name in _defined("scripted_triggers"), name
    for name in ("pp_cplan_group_start", "pp_cplan_construct", "pp_cplan_flip", "pp_cplan_step_var", "pp_cplan_purse_pay",
                 "pp_cplan_note_goods"):
        assert name in _defined("scripted_effects"), name


def test_no_construction_count_and_no_several_condition_not() -> None:
    for path in [*SCRIPT_FILES, cc.GUI]:
        code = _code(MOD / path)
        assert "num_civil_constructions" not in code, path  # pp_cplan_site_free is the one place for it
        for match in re.finditer(r"\bNOT = \{", code):
            depth, index = 1, match.end()
            while depth:
                depth += {"{": 1, "}": -1}.get(code[index], 0)
                index += 1
            body, top, level = code[match.end():index - 1], 0, 0
            for token in re.finditer(r"\{|\}|[A-Za-z_:.\"()0-9?]+\s*(?:[<>=!?]+)", body):
                level += {"{": 1, "}": -1}.get(token.group(0), 0)
                top += token.group(0) not in "{}" and level == 0
            assert top <= 1, f"{path}: NOT with {top} conditions: {body.strip()[:60]}"
    assert "pp_cplan_site_free = yes" in _block(_code(MOD / cc.TRIGGERS), "pp_cplan_country_site")


def test_variables_carry_a_hundred_and_defaults_come_from_the_config() -> None:
    config = _config()
    values = _code(MOD / cc.VALUES)
    for name, variable, default in (("pp_cplan_country_control_pct", cc.VAR_CONTROL, config.control_pct),
                                    ("pp_cplan_country_town_pop", cc.VAR_TOWN_POP, config.town_population),
                                    ("pp_cplan_country_keep_influence", cc.VAR_KEEP, config.keep_influence)):
        assert _tokens(_block(values, name)) == (f"value = {default} if = {{ limit = {{ has_variable = {variable} }} "
                                                 f"value = var:{variable} subtract = 100 }}"), name
    assert (config.control_pct, config.town_population, config.keep_influence) == (50, 30, 50)
    guis = _code(MOD / cc.SCRIPTED_GUIS)
    step = _block(guis, "pp_cplan_country_step")
    assert (f"flag:control_line = {{ pp_cplan_step_var = {{ var = {cc.VAR_CONTROL} current = pp_cplan_country_control_pct "
            f"step = {config.control_step} min = 100 max = 200 }} }}") in step
    assert (f"flag:town_line = {{ pp_cplan_step_var = {{ var = {cc.VAR_TOWN_POP} current = pp_cplan_country_town_pop "
            f"step = {config.town_population_step} min = {config.town_population_min + 100} "
            f"max = {config.town_population_max + 100} }} }}") in step
    assert (f"flag:keep_line = {{ pp_cplan_step_var = {{ var = {cc.VAR_KEEP} current = pp_cplan_country_keep_influence "
            f"step = {config.keep_influence_step} min = 100 max = {config.keep_influence_max + 100} }} }}") in step
    assert (config.control_step, config.town_population_step, config.keep_influence_step) == (10, 5, 5)
    assert (config.town_population_min, config.town_population_max, config.keep_influence_max) == (5, 100, 100)
    # no variable is compared with "=" (that compares scopes), and the ones the script counts in start at 100
    code = "".join(_code(MOD / path) for path in SCRIPT_FILES)
    assert not re.search(r"var:pp_cplan_\w+ = \d", code)
    assert "set_variable = { name = pp_cplan_rights_n value = 100 }" in code


def test_every_button_flag_is_handled_and_declared() -> None:
    gui = _read(MOD / cc.GUI)
    guis = _code(MOD / cc.SCRIPTED_GUIS)
    declared = set(re.findall(r"value = flag:(\w+)", _block(_code(MOD / cc.EFFECTS), "pp_cplan_country_declare")))
    handled = {name: set(re.findall(r"flag:(\w+) = \{", _block(guis, name)))
               for name in ("pp_cplan_country_toggle", "pp_cplan_country_step")}
    calls = re.findall(r"GetScriptedGui\('(\w+)'\)\.Execute\(GuiScope\.SetRoot\(GetPlayer\.MakeScope\)"
                       r"\.AddScope\('pp_key', MakeScopeFlag\('(\w+)'\)\)(?:\.AddScope\('pp_dir', MakeScopeFlag\('(up|down)'\)\))?\.End\)", gui)
    assert len(calls) == gui.count("GetScriptedGui(") and len(calls) > 120
    for name, flag, direction in calls:
        assert flag in handled[name], (name, flag)
        assert flag in declared, flag
        assert bool(direction) == (name == "pp_cplan_country_step"), (name, flag)
    assert {flag for _, flag, _ in calls} == set().union(*handled.values()) == declared
    result = _result()
    assert declared == set(cc.flags(result.buildings, result.rights))


# ---- the tab ---------------------------------------------------------------------------------------------------------


def _widget_tree(text: str) -> list[tuple[str, str | None]]:
    pairs: list[tuple[str, str | None]] = []
    stack: list[str | None] = []
    for match in re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{|\}", re.sub(r'"[^"\n]*"', '""', re.sub(r"#[^\n]*", "", text))):
        if match.group(0) == "}":
            if stack:
                stack.pop()
            continue
        name = match.group(1)
        pairs.append((name, stack[-1] if stack else None))
        stack.append(name)
    return pairs


def test_tab_is_one_type_made_of_known_parts() -> None:
    gui = _read(MOD / cc.GUI)
    assert len(re.findall(r"^\ttype pp_cplan_country_tab = vbox \{", gui, re.MULTILINE)) == 1
    tab = gui[gui.index("type pp_cplan_country_tab = vbox {"):]
    assert "layoutpolicy_horizontal = expanding" in tab[:200] and "layoutpolicy_vertical = expanding" in tab[:200]
    for name, parent in _widget_tree(gui):
        if parent in {"flowcontainer", "container", "dynamicgridbox", "fixedgridbox"}:
            assert name not in {"hbox", "vbox"}, f"{name} directly inside {parent}"
    # only widget kinds the plan window and the profile editor already use; the tab's own three small types
    kinds = {name for name, _ in _widget_tree(gui)} - {"types", "type", "size", "margin", "color", "minimumsize", "maximumsize"}
    # (flowcontainer: the scroll area's list of the rights, as the detail panes' lists)
    assert kinds <= {"vbox", "hbox", "flowcontainer", "button", "widget", "icon", "glow", "expand", "scrollarea", "scrollwidget",
                     "scrollbar_vertical", "blockoverride", "button_checkbox", "pp_cplan_country_label",
                     "pp_cplan_country_title", "pp_cplan_country_step_button", "text_single", "button_regular"}, kinds
    assert "Concatenate" not in gui and "GetFlagName" not in gui and "datamodel" not in gui
    # the window hosts it (the plan window is construction_plan.py's side)
    window = _read(MOD / "in_game/gui/pp_construction_plan.gui")
    if "pp_cplan_country_tab" in window:
        assert window.count("pp_cplan_country_tab = {}") == 1


def test_tiles_are_toggles_in_rows() -> None:
    gui = _read(MOD / cc.GUI)
    result, config = _result(), _config()
    tiles = re.findall(r"\t+button = \{\n(.*?)\n\t+\}\n", gui, re.DOTALL)
    per_row = config.tiles_per_row
    # the grids wrap: row r holds a copy of every tile from its first place on (a tile's place among the tiles that
    # show is never past its own number), each shown while its place, a country variable the layout effect keeps,
    # falls in that row
    copies = lambda count: sum(count - start for start in range(0, count, per_row))
    assert len(result.buildings) + len(result.rights) == 120
    assert len(tiles) == copies(len(result.buildings)) + copies(len(result.rights))
    layout = _block(_code(MOD / cc.EFFECTS), cc.LAYOUT_EFFECT)
    for tile in tiles:
        variable = re.search(r"down = \"\[GetPlayer\.MakeScope\.Var\('(pp_cplan_(?:pub|right)_\w+)'\)\.IsSet\]\"", tile)
        assert variable, tile[:80]
        name = variable.group(1)
        flag = name.removeprefix("pp_cplan_")
        assert f"MakeScopeFlag('{flag}')" in tile, name
        # pressed and the gold glow while ticked, an icon, a tooltip, a size of its own
        assert f"glow = {{ visible = \"[GetPlayer.MakeScope.Var('{name}').IsSet]\" glow_radius" in tile, name
        assert "using = header_button_template" in tile and "using = button_tab_toggle_properties_template" in tile
        assert "size = { 34 34 }" in tile and re.search(r'texture = "gfx/interface/icons/\w+/\w+\.dds"', tile), name
        assert re.search(r'tooltip = "PP_CPLANC_(?:PUB|RIGHT)_[A-Z0-9_]+"', tile), name
        # shown while its place falls in this row: only variables are read, no script value a frame
        place = name.replace("pp_cplan_pub_", "pp_cplan_tp_pub_").replace("pp_cplan_right_", "pp_cplan_tp_right_")
        shown = re.match(rf"\t+visible = \"\[And3\(GetPlayer\.MakeScope\.Var\('{place}'\)\.IsSet, GreaterThan_CFixedPoint\("
                         rf"GetPlayer\.MakeScope\.Var\('{place}'\)\.GetValue, '\(CFixedPoint\)(\d+)\.5'\), LessThan_CFixedPoint\("
                         rf"GetPlayer\.MakeScope\.Var\('{place}'\)\.GetValue, '\(CFixedPoint\)(\d+)\.5'\)\)\]\"\n", tile)
        assert shown, name
        low, high = int(shown.group(1)), int(shown.group(2))
        assert high - low == per_row and (low - 100) % per_row == 0, name
        assert "ScriptValue" not in tile, name
        # the layout places it: always, or while the country could use it or it is ticked (so it can be unticked)
        assert f"set_variable = {{ name = {place} value = var:pp_cplan_tc_" in layout, name
        show = name.replace("pp_cplan_pub_", "pp_cplan_pub_show_").replace("pp_cplan_right_", "pp_cplan_right_show_")
        # (a tile that always shows removes its place before it sets it: the variable's one use in script, else the
        # game's check at load logs "set but never used"; in game 2026-11-10)
        assert f"remove_variable = {place}\n" in layout, name
        if f"else = {{\n\t\tremove_variable = {place}\n" in layout:
            assert f"limit = {{ OR = {{ has_variable = {name} {show} > 0 }} }}" in layout, name
            assert show in _defined("script_values"), show
    always = [right.key for right in result.rights if right.always_shown]
    assert len(always) >= 20 and all(f"pp_cplan_right_show_{key} =" not in _read(MOD / cc.VALUES) for key in always)
    # rows of at most tiles_per_row, a row hidden while none of its tiles shows
    # (the buildings' rows are hboxes of the tab; the rights' rows flowcontainers in the scroll area's vertical
    # flowcontainer: a vbox there was stretched over the scroll area and spread four rows over its height, in game
    # 2026-11-10)
    header = (r"(?:hbox = \{\n(?:\t+visible = \"[^\n]*\"\n)?\t+layoutpolicy_horizontal = expanding"
              r"|flowcontainer = \{\n(?:\t+visible = \"[^\n]*\"\n)?\t+direction = horizontal)\n\t+ignoreinvisible = yes\n\t+spacing = 3\n")
    rows = re.split(header, gui)[1:]
    counts = [row.count("using = header_button_template") for row in rows]
    listed = gui[gui.index("scrollwidget = {"):]
    assert listed.startswith("scrollwidget = {\n\t\t\t\tflowcontainer = {\n\t\t\t\t\tdirection = vertical\n")
    assert "hbox = {" not in listed and "vbox = {" not in listed
    assert listed.count("using = header_button_template") == copies(len(result.rights))
    assert sum(counts) == len(tiles) and config.tiles_per_row == 11
    assert counts == ([len(result.buildings) - start for start in range(0, len(result.buildings), per_row)]
                      + [len(result.rights) - start for start in range(0, len(result.rights), per_row)])
    # a row shows while the grid has tiles for it; the layout runs when the tab opens and after every tick
    assert gui.count("visible = \"[And(GetPlayer.MakeScope.Var('pp_cplan_tc_pub').IsSet, ") == -(-len(result.buildings) // per_row)
    assert gui.count("visible = \"[And(GetPlayer.MakeScope.Var('pp_cplan_tc_right').IsSet, ") == -(-len(result.rights) // per_row)
    guis = _code(MOD / cc.SCRIPTED_GUIS)
    assert f"{cc.LAYOUT_GUI} = {{" in guis and guis.count(f"{cc.LAYOUT_EFFECT} = yes") == 2
    window = _read(MOD / "in_game/gui/pp_construction_plan.gui")
    assert window.count(f"onclick = \"{cc.LAYOUT_CALL}\"") == 2  # the opener and the tab's button
    assert "Not(IsPauseMenuShown)" in window[window.index('name = "pp_construction_plan"'):window.index("button_regular = {", window.index('name = "pp_construction_plan"'))]
    # the rights do not have to fit: they scroll
    assert gui.index("scrollarea = {") < gui.index("MakeScopeFlag('right_")
    assert gui.index("MakeScopeFlag('pub_") < gui.index("scrollarea = {")


def test_sections_have_one_header_row_each() -> None:
    gui = _read(MOD / cc.GUI)
    tab = gui[gui.index("type pp_cplan_country_tab = vbox {"):]
    titles = re.findall(r'pp_cplan_country_title = \{ text = "(\w+)"', tab)
    assert titles == ["PP_CPLANC_PUB", "PP_CPLANC_RANK", "PP_CPLANC_RIGHTS"]
    assert tab.count("button_checkbox = {") == 4  # one switch more would be a new section: keep the tab tight
    for variable, flag in (("pp_cplan_upgrade", "upgrade"), ("pp_cplan_rank_town", "rank_town"),
                           ("pp_cplan_rank_city", "rank_city"), ("pp_cplan_rights_on", "rights_on")):
        box = re.search(rf"button_checkbox = \{{\n\t+size = \{{ 22 22 \}}\n\t+down = \"\[GetPlayer\.MakeScope\.Var\('{variable}'\)\.IsSet\]\"\n"
                        rf"\t+tooltip = \"\w+\"\n\t+onclick = \"[^\n]*MakeScopeFlag\('{flag}'\)[^\n]*\"\n", tab)
        assert box, variable
    for line in cc.LINES:
        for direction in ("down", "up"):
            assert tab.count(f"MakeScopeFlag('{line}')).AddScope('pp_dir', MakeScopeFlag('{direction}'))") == 1, (line, direction)
    # no paragraphs in the tab: the tooltips carry the words
    assert "text_multi" not in gui


def test_every_text_exists_and_carries_no_number() -> None:
    gui = _read(MOD / cc.GUI)
    loc = dict(re.findall(r'^  (\w+): "(.*)"$', _read(MOD / cc.LOC), re.MULTILINE))
    keys = set(re.findall(r'(?:text|tooltip) = "(\w+)"', gui))
    assert keys and keys <= set(loc), sorted(keys - set(loc))[:5]
    assert set(loc) == keys, sorted(set(loc) - keys)[:5]
    config = _config()
    for key, text in loc.items():
        assert text.strip(), key
        plain = re.sub(r"\[[^\]]*\]", "", text)  # numbers come from script values
        assert not re.search(r"\d", plain), f"{key}: a number in the text"
        assert "pp_cplan" not in plain and "$" not in plain, key
    # the lines read their script values
    for key, value in (("PP_CPLANC_CONTROL_VALUE", "pp_cplan_country_control_pct"),
                       ("PP_CPLANC_TOWN_VALUE", "pp_cplan_country_town_pop"),
                       ("PP_CPLANC_KEEP_VALUE", "pp_cplan_country_keep_influence"),
                       ("PP_CPLANC_RIGHTS_LAST", "pp_cplan_country_rights_n")):
        assert f"[GetPlayer.MakeScope.ScriptValue('{value}')|0]" in loc[key], key
        assert value in _defined("script_values"), value
    assert config.tiles_per_row == 11
    # what the plan does not do is said in plain words
    assert "does not upgrade a charter" in loc["PP_CPLANC_RIGHTS_TT"]
    assert "fewer levels" in loc["PP_CPLANC_TOWN_TT"]
    # what the in-game test showed about founding, in plain words, on both switches
    for key in ("PP_CPLANC_TOWN_TT", "PP_CPLANC_CITY_TT"):
        for words in ("about a year", "construction goods from the market", "Nothing else is built in that location meanwhile",
                      "second construction slot"):
            assert words in loc[key], (key, words)
    assert "once you have researched it" in loc["PP_CPLANC_UPGRADE_TT"] and "Closed buildings" in loc["PP_CPLANC_UPGRADE_TT"]


def test_every_tile_has_a_name() -> None:
    result = _result()
    loc = dict(re.findall(r'^  (\w+): "(.*)"$', _read(MOD / cc.LOC), re.MULTILINE))
    for building in result.buildings:
        assert loc[f"PP_CPLANC_PUB_{building.key.upper()}"].startswith(f"[ShowBuildingTypeName('{building.key}')|e]\\n"), building.key
    for right in result.rights:
        assert loc[f"PP_CPLANC_RIGHT_{right.key.upper()}"].startswith(f"[ShowTownRightsName('{right.key}')]\\n"), right.key
    # the names are the game's own: every building and right has its English name
    names = cc.name_keys(result.buildings, result.rights)
    assert len(names) == 120
    assert cc.missing_names(names, MOD, _vanilla()) == []
    assert cc.missing_names(["no_such_right_anywhere"], MOD, _vanilla()) == ["no_such_right_anywhere"]


def test_config_is_checked(tmp_path: Path) -> None:
    text = PROJECT.read_text(encoding="utf-8")
    start = text.index("[construction_plan_country]")
    table = text[start:text.index("\n[", start + 1)]
    for old, new in (('"library", "university",', '"library", "library",'), ("control_pct = 50", "control_pct = 150"),
                     ("town_population = 30", "town_population = 3"), ("keep_influence = 50", "keep_influence = 500")):
        assert old in table, old
        broken = tmp_path / "broken.toml"
        broken.write_text(table.replace(old, new), encoding="utf-8")
        with pytest.raises(ValueError):
            cc.load_config(broken)
    good = tmp_path / "good.toml"
    good.write_text(table, encoding="utf-8")
    assert cc.load_config(good) == _config()
