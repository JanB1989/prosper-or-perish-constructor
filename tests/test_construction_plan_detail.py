"""Construction Plan detail panes (src/prosper_or_perish_constructor/construction_plan_detail.py; Jan 2026-11-09: a cog
per rule group that shows what happened under the hood, what waited for gold, a chart and what was built)."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from prosper_or_perish_constructor import construction_plan as cp
from prosper_or_perish_constructor import construction_plan_detail as cpd

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mod" / "pp"
WINDOW = MOD / "in_game/gui/pp_construction_plan.gui"
LOC_FOLDER = MOD / "main_menu/localization/english"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _type_body(gui: str, name: str) -> str:
    """The body of `type <name> = <base> {`, by brace depth."""
    match = re.search(rf"^\ttype {name} = \w+ \{{\n", gui, re.MULTILINE)
    assert match, name
    depth, index = 1, match.end()
    while depth:
        depth += {"{": 1, "}": -1}.get(gui[index], 0)
        index += 1
    return gui[match.end():index - 1]


def _loc_keys(text: str) -> list[str]:
    return re.findall(r"^  ([A-Za-z0-9_.]+):", text, re.MULTILINE)


def test_files_in_step() -> None:
    assert (MOD / cpd.DETAIL_GUI).read_text(encoding="utf-8") == cpd.render_gui(), "run ppc finalize"
    assert (MOD / cpd.DETAIL_LOC).read_text(encoding="utf-8") == cpd.render_loc(), "run ppc finalize"
    assert cpd.render_gui().startswith(cp.HEADER)
    assert cpd.render_loc().startswith("﻿l_english:\n")
    assert all(line.startswith("  ") for line in cpd.render_loc().splitlines()[1:])


def test_a_cog_and_a_pane_per_group() -> None:
    gui = cpd.render_gui()
    for group in cp.GROUPS:
        cog = _type_body(gui, f"pp_cplan_detail_button_{group}")
        assert cog.count("button_automation_shortcut = {") == 2, group
        assert f"on_action = \"[GetVariableSystem.Set('pp_cplan_detail', '{group}')]\"" in cog
        assert "on_action = \"[GetVariableSystem.Clear('pp_cplan_detail')]\"" in cog
        assert f"visible = \"[Not(GetVariableSystem.HasValue('pp_cplan_detail', '{group}'))]\"" in cog
        assert f"visible = \"[GetVariableSystem.HasValue('pp_cplan_detail', '{group}')]\"" in cog
        assert re.search(r"^\t\tsize = \{ 2\d 2\d \}", cog, re.MULTILINE), "a clickable widget needs a real size"
        pane = _type_body(gui, f"pp_cplan_detail_{group}")
        assert f'tooltip = "PP_CPLAN_{group.upper()}_RULE_TT"' in pane
        assert "on_action = \"[GetVariableSystem.Clear('pp_cplan_detail')]\"" in pane  # its close button
        for name in ("ran", "waitn", "started"):
            assert f"ScriptValue('pp_cplan_d_{group}_{name}')" in pane, (group, name)
        loc = cpd.texts()
        for name in ("had", "spent", "started", "need"):
            assert f"ScriptValue('pp_cplan_d_{group}_{name}')" in loc[f"PP_CPLAN_D_GOLD_{group.upper()}"], (group, name)
        for name in ("waitn", "wait"):
            assert f"ScriptValue('pp_cplan_d_{group}_{name}')" in loc[f"PP_CPLAN_D_WAIT_{group.upper()}"], (group, name)


def test_chart_has_a_column_per_month_oldest_left() -> None:
    gui = cpd.render_gui()
    assert cp.HISTORY_MONTHS == 12
    column = _type_body(gui, "pp_cplan_d_column")
    assert column.count("direction = vertical") == 2 and column.count("max = 100") == 2
    assert "progress_bar_silver_rotated.dds" in column and "progress_bar_goldish_rotated.dds" in column
    for group in cp.GROUPS:
        pane = _type_body(gui, f"pp_cplan_detail_{group}")
        assert pane.count("pp_cplan_d_column = {") == cp.HISTORY_MONTHS, group
        places = []
        for month in range(1, cp.HISTORY_MONTHS + 1):
            need = f"ScriptValue('pp_cplan_h_{group}_needp_{month}')"
            spent = f"ScriptValue('pp_cplan_h_{group}_spentp_{month}')"
            assert pane.count(need) == 1 and pane.count(spent) == 1, (group, month)
            places.append(pane.index(need))
        assert places == sorted(places, reverse=True), "the oldest month left, last month right"
        tooltip = cpd.texts()[f"PP_CPLAN_D_CHART_TT_{group.upper()}"]
        assert f"pp_cplan_h_{group}_sum_need" in tooltip and f"pp_cplan_h_{group}_sum_spent" in tooltip


def test_lists_read_each_groups_constructions() -> None:
    gui = cpd.render_gui()
    for group, why in cp.GROUP_WHY.items():
        pane = _type_body(gui, f"pp_cplan_detail_{group}")
        assert f"datamodel = \"[GetPlayer.MakeScope.GetList('pp_cplan_log_{why}')]\"" in pane, group
        assert "datamodel = \"[Scope.GetList('pp_cplan_log_types')]\"" in pane
        assert 'text = "PP_CPLAN_D_COST"' in pane and 'text = "PP_CPLAN_D_NOTHING"' in pane
        others = [w for g, w in cp.GROUP_WHY.items() if g != group]
        assert not any(f"GetList('pp_cplan_log_{w}')" in pane for w in others), group
    food = _type_body(gui, "pp_cplan_detail_food")
    for step in cpd.FOOD_STEPS:
        assert f"EqualTo_CFixedPoint(Scope.ScriptValue('pp_cplan_log_step_n'), '(CFixedPoint){step}')" in food, step
        assert f'text = "PP_CPLAN_D_FOOD_WHY_{step}"' in food
    loc = cpd.texts()
    # the store a year from now for the hunger steps only
    for step in cpd.FOOD_STEPS:
        assert ("pp_cplan_log_val_n" in loc[f"PP_CPLAN_D_FOOD_WHY_{step}"]) == (step in (1, 2, 5)), step
    assert "pp_cplan_log_cost_n" in loc["PP_CPLAN_D_COST"]


def test_every_text_exists_once() -> None:
    """Every key the detail GUI uses (PP_CPLAN_D_*, the window's rule tooltips, the profile rule states) is defined
    exactly once across the mod's English files with the detail loc as rendered; no PP_CPLAN_D_ key is left unused."""
    gui = cpd.render_gui()
    counts: Counter[str] = Counter()
    for path in sorted(LOC_FOLDER.glob("*.yml")):
        if path.name != cpd.DETAIL_LOC.name:
            counts.update(_loc_keys(_read(path)))
    rendered = _loc_keys(cpd.render_loc())
    counts.update(rendered)
    used = set(re.findall(r"(?:text|tooltip|title) = \"([A-Z][A-Z0-9_]+)\"", gui))
    assert {f"PP_CPLAN_{group.upper()}_RULE_TT" for group in cp.GROUPS} <= used
    for key in used:
        assert counts[key] == 1, f"{key}: defined {counts[key]} times"
    assert {key for key in used if key.startswith("PP_CPLAN_D_")} == set(rendered)
    assert all(key.startswith("PP_CPLAN_D_") for key in rendered)


def test_texts_follow_the_rules() -> None:
    """Data in loc keys only (the GUI uses raw_text for data alone), gold as @gold!, no key a guard of
    test_construction_plan.py rejects, every ScriptValue the right scope's: the country's or a list item's."""
    gui = cpd.render_gui()
    loc = cpd.render_loc()
    assert not re.search(r"\btext = \"[^\"]*\[", gui), "a data text needs raw_text"
    assert not re.search(r"PP_CPLAN_(?:RULE_|MAX|MODE_|PRESET|FOCUS)", gui + loc)
    money = re.compile(r"ScriptValue\('(\w+_(?:had|spent|need|wait|cost_n))'\)\|0\](.{0,6})")
    found = money.findall(loc)
    assert len(found) >= 6 * len(cp.GROUPS)
    for name, after in found:
        assert after == "@gold!", name
    for match in re.finditer(r"(\w+(?:\.\w+)*)\.ScriptValue\('([a-z0-9_]+)'\)", gui + loc):
        scope, name = match.groups()
        if name.startswith("pp_cplan_log_"):
            assert scope == "Scope", name
        else:
            assert scope == "GetPlayer.MakeScope", name


def test_no_box_directly_inside_a_container() -> None:
    """EU5 refuses an hbox/vbox as a direct child of a (flow)container; a hot reload with one crashed the game."""
    stack: list[str | None] = []
    opener = r"([A-Za-z_][A-Za-z0-9_]*)\s*(?:\"[^\"]*\"\s*)?(?:=\s*\w*\s*)?\{|\}"
    # whole-line comments only: "#weak" in a default_format is no comment
    for match in re.finditer(opener, re.sub(r"(?m)^\s*#.*$", "", cpd.render_gui())):
        if match.group(0) == "}":
            stack.pop()
            continue
        name = match.group(1)
        parent = stack[-1] if stack else None
        if name == "item":
            stack.append(parent)
            continue
        if parent in {"flowcontainer", "container", "dynamicgridbox", "fixedgridbox"}:
            assert name not in {"hbox", "vbox"}, f"{name} directly inside {parent}"
        stack.append(name)
    assert not stack


def test_window_places_cogs_and_panes() -> None:
    window = _read(WINDOW)
    rows = window[window.index("# profiles\n"):window.index('pp_cplan_title = { text = "PP_CPLAN_LAST" }')]
    for group in cp.GROUPS:
        assert window.count(f"pp_cplan_detail_button_{group} = {{}}") == 1, group
        after_bar = rf"pp_cplan_weight_bar_{group} = \{{\}}\n\t+pp_cplan_detail_button_{group} = \{{\}}\n"
        assert re.search(after_bar, rows), group
        shown = f"GetVariableSystem.HasValue('pp_cplan_detail', '{group}')"
        assert window.count(f"pp_cplan_detail_{group} = {{ visible = \"[{shown}]\" }}") == 1, group
    # the last month list only while no pane is open; the window's close button closes the pane too
    hidden = window.index("visible = \"[Not(GetVariableSystem.Exists('pp_cplan_detail'))]\"")
    start = window.rindex("vbox = {", 0, hidden)
    depth, index = 1, start + len("vbox = {")
    while depth:
        depth += {"{": 1, "}": -1}.get(window[index], 0)
        index += 1
    last = window[start:index]
    assert 'text = "PP_CPLAN_LAST"' in last and "GetList('pp_cplan_log')" in last and "PP_CPLAN_LAST_SUMMARY" in last
    assert window.index("pp_cplan_detail_button_business = {}") < start < window.index("pp_cplan_detail_profiles = {")
    close = window[window.index("button_close_alt = {"):]
    assert "on_action = \"[GetVariableSystem.Clear('pp_cplan_detail')]\"" in close
    # the rows still fit the window (690 px): label + line + bar + cog
    assert window.count("minimumsize = { 140 -1 } maximumsize = { 140 -1 }") == 5
    assert window.count("minimumsize = { 190 -1 }") == 3 and window.count("widget = { size = { 190 1 } }") == 2


def test_script_values_exist() -> None:
    """Every number the panes read is a script value of the mod (the pass writes them; script side of 2026-11-09)."""
    names: set[str] = set()
    for path in (MOD / "in_game/common/script_values").glob("*.txt"):
        names |= set(re.findall(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{", _read(path), re.MULTILINE))
    used = set(re.findall(r"ScriptValue\('([a-z0-9_]+)'\)", cpd.render_gui() + cpd.render_loc()))
    missing = sorted(used - names)
    assert not missing, f"script values missing: {missing}"
