"""Starting technology ladder (src/prosper_or_perish_constructor/start_technology.py, 2026-11-25).

A game update that adds, removes or renames countries or first-age advances, or changes an advance this pass
replaces, fails here with the names in the message.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from prosper_or_perish_constructor import start_technology as st
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

REPO = Path(__file__).resolve().parents[1]
PROJECT = REPO / "constructor.toml"
MOD = REPO / "mod" / st.MOD_FOLDER


@pytest.fixture(scope="module")
def vanilla() -> Path:
    return vanilla_root(REPO, PROJECT)


@pytest.fixture(scope="module")
def ladder() -> st.Ladder:
    return st.load_ladder(REPO)


@pytest.fixture(scope="module")
def advances(vanilla: Path) -> dict[str, st.Advance]:
    return st.effective_advances(vanilla, MOD)


@pytest.fixture(scope="module")
def plan(ladder: st.Ladder, advances: dict[str, st.Advance]) -> st.AdvancePlan:
    return st.plan_advances(ladder, advances)


@pytest.fixture(scope="module")
def countries(vanilla: Path) -> list[st.Country]:
    return st.country_blocks(vanilla, MOD)


@pytest.fixture(scope="module")
def groups(ladder: st.Ladder, countries: list[st.Country], vanilla: Path) -> list[st.CountryGroup]:
    return st.country_groups(REPO, vanilla, MOD, ladder, countries)


def test_country_table_has_exactly_the_setup_countries(countries: list[st.Country]) -> None:
    rows = st.read_country_rows(REPO)
    setup = [c.tag for c in countries]
    table = [r["tag"] for r in rows]
    missing = sorted(set(setup) - set(table))
    extra = sorted(set(table) - set(setup))
    assert not missing and not extra, f"setup countries without a row: {missing}; rows the setup does not have: {extra}"
    assert len(table) == len(set(table)) == len(setup) > 2000


def test_country_table_errors_name_the_tags(tmp_path: Path, countries: list[st.Country]) -> None:
    (tmp_path / "config").mkdir()
    shutil.copy(REPO / st.CONFIG, tmp_path / st.CONFIG)
    rows = st.read_country_rows(REPO)
    rows = [r for r in rows if r["tag"] != countries[0].tag]
    rows.append({"tag": "ZZQ", "group": "3", "confidence": "", "basis": "", "note": ""})
    rows[0] = {**rows[0], "group": "12"}
    (tmp_path / st.COUNTRIES_CSV).write_text(st._csv_text(st.COUNTRIES_HEADER, rows), encoding="utf-8")
    with pytest.raises(st.StartTechnologyError) as error:
        st.country_groups(tmp_path, Path("/nonexistent"), None, st.load_ladder(tmp_path), countries)
    message = str(error.value)
    assert countries[0].tag in message and "ZZQ" in message and f"{rows[0]['tag']}='12'" in message


def test_every_general_first_age_advance_has_a_level(ladder: st.Ladder, advances: dict[str, st.Advance]) -> None:
    general = st.general_first_age(advances)
    missing = sorted(general - set(ladder.levels))
    unknown = sorted(set(ladder.levels) - set(advances))
    not_general = sorted((set(ladder.levels) & set(advances)) - general)
    assert not missing, f"general first-age advances without a level in [levels]: {missing}"
    assert not unknown, f"[levels] names advances the game does not have: {unknown}"
    assert not not_general, f"[levels] names advances that are not general first-age advances: {not_general}"
    assert len(general) > 60


def test_children_never_start_below_their_parents(ladder: st.Ladder, advances: dict[str, st.Advance]) -> None:
    parents = st.parents_after(ladder, advances)
    low = []
    for key, level in ladder.levels.items():
        ps = [p for p in parents[key] if p in ladder.levels]
        if ps and level < min(ladder.levels[p] for p in ps):
            low.append(f"{key} {level} < {min(ladder.levels[p] for p in ps)} ({', '.join(ps)})")
    # a specific advance moved by [requires]: without a level it starts with its new parent (fine); with one, that
    # level is never below its lowest parent
    specific = st.specific_first_age(advances)
    for key, ps in ladder.requires.items():
        if key in ladder.levels:
            continue
        assert key in specific, f"[requires] {key} is neither in [levels] nor a specific first-age advance"
        level = advances[key].level
        if level is not None and ps:
            new = ladder.specific_remap[level]
            parent_levels = [ladder.levels.get(p, advances[p].level or 0) for p in ps]
            if new < min(parent_levels):
                low.append(f"{key} {new} < {min(parent_levels)} ({', '.join(ps)})")
    assert not low, low
    assert all(level <= ladder.nobody for level in ladder.levels.values())
    assert set(ladder.levels.values()) <= {*ladder.groups, ladder.nobody}


def test_specific_remap_covers_every_level_and_never_lowers(ladder: st.Ladder, advances: dict[str, st.Advance],
                                                              plan: st.AdvancePlan) -> None:
    assert all(new >= old for old, new in ladder.specific_remap.items()), ladder.specific_remap
    levelled = {k for k in st.specific_first_age(advances) if advances[k].level is not None}
    assert set(plan.remapped) == levelled
    assert all(new >= old for old, new in plan.remapped.values())
    later = [k for k in plan.injects if advances[k].age != st.AGE1]
    assert not later, f"advances of later ages touched: {later}"


def _configured_keys(ladder: st.Ladder, key: str) -> set[str]:
    keys = {st.LEVEL_KEY}
    if key in ladder.requires:
        keys |= {"requires", "depth"}
    if key in ladder.research_cost:
        keys.add("research_cost")
    if key in ladder.ai_weight:
        keys.add("ai_weight")
    if key in ladder.research_speed:
        keys.add(st.RESEARCH_KEY)
    return keys


def test_generated_blocks_match_the_effective_advances(ladder: st.Ladder, advances: dict[str, st.Advance],
                                                       plan: st.AdvancePlan) -> None:
    """Every REPLACE block is the effective block (vanilla and the other mod files) but for the configured keys, so a
    vanilla change to that advance is carried on the next apply or caught here; every INJECT sets the level only."""
    blocks = st.output_blocks(MOD)
    assert set(blocks) == set(plan.injects) | set(plan.replaces)
    off = []
    for key, (mode, body) in blocks.items():
        if mode.endswith("INJECT"):
            assert [s.key for s in body] == [st.LEVEL_KEY], key
            continue
        skip = _configured_keys(ladder, key)
        if [s for s in body if s.key not in skip] != [s for s in advances[key].body if s.key not in skip]:
            off.append(key)
        level = [s.value for s in body if s.key == st.LEVEL_KEY]
        # a specific advance moved by [requires] carries a level only if it had one (then the remapped level)
        assert level == ([str(plan.final_levels[key])] if key in plan.final_levels else []), key
        if key not in ladder.levels:
            assert key in plan.specific and set(_configured_keys(ladder, key)) == {st.LEVEL_KEY, "requires", "depth"}
        if key in ladder.requires:
            assert [s.value for s in body if s.key == "requires"] == ladder.requires[key], key
        if key in ladder.research_cost:
            assert [float(s.value) for s in body if s.key == "research_cost"] == [ladder.research_cost[key]], key
        if key in ladder.ai_weight:
            weights = [s.value for s in body if s.key == "ai_weight"]
            assert len(weights) == 1 and float(dict((s.key, s.value) for s in weights[0])["add"]) == ladder.ai_weight[key]
        if key in ladder.research_speed:
            assert [float(s.value) for s in body if s.key == st.RESEARCH_KEY] == [ladder.research_speed[key]], key
    assert not off, f"REPLACE blocks that differ from the effective advance: {off} (run uv run ppc start-tech apply)"
    # the engine ignores an inject into a block another mod file replaced: those must be replaced again here
    assert not [k for k in plan.injects if advances[k].replaced]


def test_advance_file_sorts_after_every_advance_file(vanilla: Path) -> None:
    names = [p.name for p in st.layered_files(vanilla, MOD, st.ADVANCES_DIR) if p.name != st.ADVANCES_OUTPUT.name]
    assert all(name < st.ADVANCES_OUTPUT.name for name in names), max(names)


def test_setup_file_sets_every_country_after_the_floors(groups: list[st.CountryGroup], countries: list[st.Country],
                                                         ladder: st.Ladder, vanilla: Path) -> None:
    text = (MOD / st.SETUP_OUTPUT).read_text(encoding="utf-8")
    assert not (MOD / st.SETUP_OUTPUT).read_bytes().startswith(b"\xef\xbb\xbf"), "setup files take no BOM"
    import re

    written = dict(re.findall(rf"(?m)^\t\t(\w+) = \{{ {st.LEVEL_KEY} = (\d+) \}}$", text))
    assert list(written) == [c.tag for c in countries]
    assert {int(v) for v in written.values()} <= set(ladder.groups)
    overlords = {o for o, _s, _k in st.dependencies(vanilla, MOD)}
    kinds = {c.tag: c.country_type for c in countries}
    assert sum(1 for k in kinds.values() if k == "pop") > 400, "the setup's societies of pops were not recognised"
    for group in groups:
        assert int(written[group.tag]) == group.level
        expected = max(group.csv_group, ladder.floors["overlord"]) if group.tag in overlords else group.csv_group
        if kinds[group.tag] == "pop":
            expected = min(expected, ladder.caps["society_of_pops"])
        assert group.level == expected, group
        assert bool(group.floor) == (group.level != group.csv_group)


def test_setup_file_is_read_after_every_file_that_sets_a_level(vanilla: Path) -> None:
    setters = [p.name for p in st.layered_files(vanilla, MOD, st.SETUP_DIR)
               if p.name != st.SETUP_OUTPUT.name and st.LEVEL_KEY in p.read_text(encoding="utf-8-sig")]
    assert setters == [st.COUNTRIES_FILE]
    assert all(name < st.SETUP_OUTPUT.name for name in setters)


def test_building_table_is_current(ladder: st.Ladder, advances: dict[str, st.Advance]) -> None:
    text = (REPO / st.BUILDINGS_CSV).read_text(encoding="utf-8")
    assert text == st.render_building_table(st.building_gates(ladder, advances)), "run uv run ppc start-tech apply"


def test_no_start_building_above_its_owners_group(groups: list[st.CountryGroup], vanilla: Path) -> None:
    level = {g.tag: g.level for g in groups}
    needs = st.load_building_table(REPO)
    bad = [f"{tag} {building} at {location} ({needs[building][0]} {needs[building][1]} > group {level.get(tag)})"
           for tag, building, location, n in st.setup_building_rows(vanilla, MOD)
           if n > 0 and building in needs and needs[building][1] > level.get(tag, 0)]
    assert not bad, f"{len(bad)} start buildings above their owner's group (rebuild: ppc build): {bad[:20]}"


def test_group_nine_keeps_todays_start(ladder: st.Ladder, advances: dict[str, st.Advance]) -> None:
    """The top group holds exactly the general advances a vanilla level-3 country holds today."""
    general = st.general_first_age(advances)
    today = st.granted(general, {k: a.requires for k, a in advances.items()},
                       {k: a.level or 0 for k, a in advances.items()}, 3)
    top = st.granted(general, st.parents_after(ladder, advances), ladder.levels, max(ladder.groups))
    assert top == today, f"only in group 9: {sorted(top - today)}; only today: {sorted(today - top)}"
    assert len(st.granted(general, st.parents_after(ladder, advances), ladder.levels, min(ladder.groups))) == 0


def _start_research(ladder: st.Ladder, advances: dict[str, st.Advance], group: int) -> float:
    held = st.granted(st.general_first_age(advances), st.parents_after(ladder, advances), ladder.levels, group)
    return ladder.research_base + sum(v for k, v in ladder.research_speed.items() if k in held)


def test_research_speed_adds_up_to_vanillas_base(ladder: st.Ladder, advances: dict[str, st.Advance]) -> None:
    """Base and advances add up to vanilla's flat research: the top groups research as before, nobody gains, and no
    group starts faster than the group above it."""
    assert ladder.research_base is not None and ladder.research_speed
    assert ladder.research_base + sum(ladder.research_speed.values()) == pytest.approx(st.VANILLA_RESEARCH_BASE)
    by_group = {g: _start_research(ladder, advances, g) for g in sorted(ladder.groups)}
    assert by_group[max(ladder.groups)] == pytest.approx(st.VANILLA_RESEARCH_BASE)
    assert by_group[min(ladder.groups)] == pytest.approx(ladder.research_base)
    values = [by_group[g] for g in sorted(by_group)]
    assert values == sorted(values), by_group
    # none of them sits behind an institution or a region: every country can research its way to full speed
    gates = st.gate_classes(advances)
    assert {gates[k] for k in ladder.research_speed} == {"free"}


def test_research_advances_outweigh_every_gate(ladder: st.Ladder) -> None:
    """The AI puts no value on flat research, so the weight is what makes a country behind take these first."""
    others = [w for k, w in ladder.ai_weight.items() if k not in ladder.research_speed]
    assert set(ladder.research_speed) <= set(ladder.ai_weight)
    assert min(ladder.ai_weight[k] for k in ladder.research_speed) > max(others)


def test_research_base_replaces_vanillas_flat_research(ladder: st.Ladder, vanilla: Path) -> None:
    """The auto modifier file is vanilla's blocks with one number changed; the societies of pops keep theirs."""
    blocks = st.research_base_blocks(ladder, vanilla, MOD)
    assert {"location_tt_name", "building_tt_name", "army_tt_name", "navy_tt_name"} <= set(blocks)
    assert "pop_tt_name" not in blocks
    text = (MOD / st.RESEARCH_OUTPUT).read_text(encoding="utf-8-sig")
    assert text == st.render_research_base(ladder, blocks), "run uv run ppc start-tech apply"
    written = {s.key: s.value for s in st.parse_statements(text) if s.key and s.is_block}
    assert set(written) == {f"REPLACE:{k}" for k in blocks}
    vanilla_blocks = {}
    for path in st.layered_files(vanilla, None, st.AUTO_MODIFIERS_DIR):
        for s in st.parse_statements(path.read_text(encoding="utf-8-sig")):
            if s.key in blocks:
                vanilla_blocks[s.key] = s.value
    for key, body in blocks.items():
        assert [s for s in body if s.key != st.RESEARCH_KEY] == [s for s in vanilla_blocks[key] if s.key != st.RESEARCH_KEY]
        assert [float(s.value) for s in body if s.key == st.RESEARCH_KEY] == [ladder.research_base]


def test_check_is_current_after_apply(vanilla: Path) -> None:
    result = st.apply(REPO, PROJECT, MOD, vanilla, write=False)
    assert not result.changed, f"run uv run ppc start-tech apply: {result.changed}"


def test_statement_parser_keeps_operators_and_quotes() -> None:
    body = st.parse_statements('a = { b ?= { c = "x y" } d >= 2.50 # note\n e }')[0].value
    assert st.render_statements(body) == ['b ?= { c = "x y" }', "d >= 2.50", "e"]
