"""Construction Plan detail panes (src/prosper_or_perish_constructor/construction_plan_detail.py; Jan 2026-11-09: a cog
per rule group that shows what happened under the hood, what waited for gold, a chart and what was built)."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from prosper_or_perish_constructor import construction_plan as cp
from prosper_or_perish_constructor import construction_plan_detail as cpd
from prosper_or_perish_constructor import construction_plan_status as cps

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
        for name in ("ran", "started"):
            assert f"ScriptValue('pp_cplan_d_{group}_{name}')" in pane, (group, name)
        loc = cpd.texts()
        for name in ("had", "spent", "started", "need"):
            assert f"ScriptValue('pp_cplan_d_{group}_{name}')" in loc[f"PP_CPLAN_D_GOLD_{group.upper()}"], (group, name)
        # what waited for gold is the outlook's now (2026-11-20): the old lines are gone
        assert f"PP_CPLAN_D_WAIT_{group.upper()}" not in loc and "PP_CPLAN_D_NO_WAIT" not in loc
        # the order (Jan 2026-11-20): status, both charts, its working and steps, the last look's gold, the list
        order = [pane.index("PP_CPLAN_D_ST_0"), pane.index("pp_cplan_d_column = {"),
                 pane.index(f"PP_CPLAN_D_STEP_DOWN_{group.upper()}"), pane.index(f"PP_CPLAN_D_GOLD_{group.upper()}\""),
                 pane.index('"PP_CPLAN_D_BUILT"'), pane.index(f"GetList('pp_cplan_log_{cp.GROUP_WHY[group]}')")]
        assert order == sorted(order), group
        # (2026-11-20, Jan: no scrolling) everything but the list of what was built stands fixed, in content of a
        # fixed width that fits the window's right column; ONE scrollarea, after it all, holds only that list
        assert pane.count("scrollarea = {") == 1 and pane.count("scrollwidget = {") == 1, group
        fixed, scroll = pane[:pane.index("scrollarea = {")], pane[pane.index("scrollarea = {"):]
        assert pane.index("button_close_alt = {") < pane.index("PP_CPLAN_D_ST_0") < pane.index("scrollarea = {")
        assert f"maximumsize = {{ {cpd.PANE_WIDTH} -1 }}" in fixed
        assert '"PP_CPLAN_D_BUILT"' in fixed and "PP_CPLAN_D_NOTHING" in fixed and "pp_cplan_d_column" in fixed
        assert "layoutpolicy_vertical = expanding" in scroll[:scroll.index("scrollwidget = {")]
        assert re.fullmatch(
            r"scrollarea = \{.*?scrollwidget = \{\n\t+flowcontainer = \{\n\t+visible = \"\[GreaterThan_CFixedPoint\("
            rf"GetPlayer\.MakeScope\.ScriptValue\('pp_cplan_d_{group}_ran'\), '\(CFixedPoint\)0\.5'\)\]\"\n\t+"
            r"direction = vertical\n\t+datamodel = \"\[GetPlayer\.MakeScope\.GetList"
            rf"\('pp_cplan_log_{cp.GROUP_WHY[group]}'\)\]\".*", scroll, re.DOTALL), group
        assert "PP_CPLAN_D_" not in scroll.replace(f"PP_CPLAN_D_COST_{group.upper()}", "").replace(
            "PP_CPLAN_D_" + group.upper() + "_WHY", "").replace("PP_CPLAN_D_FOOD_WHY", "").replace(
            "PP_CPLAN_D_COUNTRY_WHY", "").replace("PP_CPLAN_D_PROFILES_WHY", ""), group


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
    """A pane's list reads its own group's entry of each location: its buildings there, its cost, its reason. A
    location with two construction slots can get constructions of two groups in one pass (in game 2026-11-10 each
    pane then named both buildings with the later group's cost and reason)."""
    gui = cpd.render_gui()
    loc = cpd.texts()
    for group, why in cp.GROUP_WHY.items():
        pane = _type_body(gui, f"pp_cplan_detail_{group}")
        assert f"datamodel = \"[GetPlayer.MakeScope.GetList('pp_cplan_log_{why}')]\"" in pane, group
        assert f"datamodel = \"[Scope.GetList('pp_cplan_log_types_{why}')]\"" in pane, group
        assert f'text = "PP_CPLAN_D_COST_{group.upper()}"' in pane and 'text = "PP_CPLAN_D_NOTHING"' in pane
        assert f"pp_cplan_log_cost_{why}_n" in loc[f"PP_CPLAN_D_COST_{group.upper()}"]
        others = [w for g, w in cp.GROUP_WHY.items() if g != group]
        assert not any(f"pp_cplan_log_{w}'" in pane or f"_{w}_n" in pane or f"pp_cplan_log_types_{w}" in pane
                       for w in others), group
        used = [text for key, text in loc.items() if f'"{key}"' in pane]
        assert not any(f"_{w}_n" in text for text in used for w in others), group
    food = _type_body(gui, "pp_cplan_detail_food")
    for step in cpd.FOOD_STEPS:
        assert f"EqualTo_CFixedPoint(Scope.ScriptValue('pp_cplan_log_step_101_n'), '(CFixedPoint){step}')" in food, step
        assert f'text = "PP_CPLAN_D_FOOD_WHY_{step}"' in food
    # the store a year from now for the hunger steps only
    for step in cpd.FOOD_STEPS:
        assert ("pp_cplan_log_val_101_n" in loc[f"PP_CPLAN_D_FOOD_WHY_{step}"]) == (step in (1, 2, 5)), step
    # Towns and Buildings: a town or city upgrade is no building, so its list names the upgrade itself; every other
    # group gives its reason
    for group in cp.GROUPS:
        pane = _type_body(gui, f"pp_cplan_detail_{group}")
        assert ("pp_cplan_rank_upgrade = {" in pane) == (group == "country"), group
        assert re.search(r"PP_CPLAN_D_\w+_WHY", pane), group  # every group gives its reason
    country = _type_body(gui, "pp_cplan_detail_country")
    assert (country.index("GetList('pp_cplan_log_types_107')") < country.index("pp_cplan_rank_upgrade = {")
            < country.index('text = "PP_CPLAN_IN_LOCATION"'))
    window = _read(WINDOW)
    upgrade = window[window.index("type pp_cplan_rank_upgrade = text_single"):]
    assert "visible = \"[Scope.Var('pp_cplan_log_rank').IsSet]\"" in upgrade[:upgrade.index("\n\t}\n")]
    # its reasons by kind, from what the group leaves in pp_cplan_log_val_107: a building the location's maximum
    # control, an upgrade its people
    step = "Scope.ScriptValue('pp_cplan_log_step_107_n')"
    for kind in cpd.COUNTRY_KINDS:
        shown = f"visible = \"[EqualTo_CFixedPoint({step}, '(CFixedPoint){kind}')]\""
        assert re.search(re.escape(shown) + rf"\n\t+text = \"PP_CPLAN_D_COUNTRY_WHY_{kind}\"", country), kind
        assert "pp_cplan_log_val_107_n" in loc[f"PP_CPLAN_D_COUNTRY_WHY_{kind}"]
    assert "[max_control|e]" in loc["PP_CPLAN_D_COUNTRY_WHY_1"] and "people" in loc["PP_CPLAN_D_COUNTRY_WHY_2"]
    effects = _read(MOD / "in_game/common/scripted_effects/pp_construction_plan_country.txt")
    assert "name = pp_cplan_rv value = { value = max_control multiply = 100 add = 100 }" in effects
    assert "name = pp_cplan_rv value = { value = population add = 100 }" in effects
    # an upgrade alone (kind 2: the group built nothing else there) has no building: the empty list of types takes no
    # room, the upgrade's name stands in its place
    hidden = f"visible = \"[Not(EqualTo_CFixedPoint({step}, '(CFixedPoint)2'))]\""
    assert re.search(re.escape(hidden) + r"\n\t+direction = horizontal\n\t+datamodel = \"\[Scope\.GetList\('pp_cplan_log_types_107'\)\]\"", country)
    assert "pp_cplan_rank_upgrade = {}\n" in country
    assert "limit = { NOT = { has_variable = pp_cplan_log_step_$why$ } }" in effects
    assert "pp_cplan_why_n" not in gui and "pp_cplan_log_why" not in effects


def test_locations_list_tells_a_building_from_a_rank_raise() -> None:
    """The Locations group builds for the town-right plans the locations hold (step 0) and raises a location's rank
    where a plan's producers need one (step 2, its people in thousands, as Towns and Buildings writes it): the list
    names which, never a profile or a mark (both retired 2026-11-19)."""
    pane = _type_body(cpd.render_gui(), "pp_cplan_detail_profiles")
    rank = "EqualTo_CFixedPoint(Scope.ScriptValue('pp_cplan_log_step_105_n'), '(CFixedPoint)2')"
    assert re.search(re.escape(f'visible = "[Not({rank})]"') + r"\n\t+text = \"PP_CPLAN_D_PROFILES_WHY\"", pane)
    assert re.search(re.escape(f'visible = "[{rank}]"') + r"\n\t+text = \"PP_CPLAN_D_PROFILES_WHY_RANK\"", pane)
    loc = cpd.texts()
    assert "plan" in loc["PP_CPLAN_D_PROFILES_WHY"]
    assert "[location_rank|e]" in loc["PP_CPLAN_D_PROFILES_WHY_RANK"]
    assert "pp_cplan_log_val_105_n" in loc["PP_CPLAN_D_PROFILES_WHY_RANK"]
    from prosper_or_perish_constructor import construction_plan_country as cpc

    assert cpd.PLAN_STEP_RANK == cpc.STEP_RANK
    for key, text in loc.items():
        words = re.sub(r"\[[^\]]*\]", "", text).lower()  # the player's words, without data and links
        assert not re.search(r"\bprofiles?\b|\bmark(?:s|ed)?\b", words), key
    assert "holds a plan" in loc["PP_CPLAN_D_OFF_PROFILES"]
    assert "with a plan" in loc["PP_CPLAN_D_PROFILES_SIT"]
    # script time 2026-11-20: the Locations look runs over the days of its month; the pane says how many locations of
    # the current look are still to be checked (shown only then, below the state counts) and that their plans keep the
    # state of their last turn until then
    unr = "ScriptValue('pp_cplan_d_profiles_unr')"
    assert unr in loc["PP_CPLAN_D_PROFILES_UNR"] and "still to be checked" in loc["PP_CPLAN_D_PROFILES_UNR"]
    assert "not reached" not in loc["PP_CPLAN_D_PROFILES_UNR"] and "last turn" in loc["PP_CPLAN_D_PROFILES_UNR"]
    shown = f'visible = "[GreaterThan_CFixedPoint(GetPlayer.MakeScope.{unr}, \'(CFixedPoint)0.5\')]"'
    assert re.search(re.escape(shown) + r"\n\t+text = \"PP_CPLAN_D_PROFILES_UNR\"", pane)
    assert pane.index('text = "PP_CPLAN_D_PROFILES_ST13"') < pane.index('text = "PP_CPLAN_D_PROFILES_UNR"')
    assert re.search(r"^pp_cplan_d_profiles_unr = \{", _read(MOD / cp.VALUES), re.MULTILINE)
    reset = _read(MOD / cp.EFFECTS)
    reset = reset[reset.index("pp_cplan_stats_reset_105 = {"):]
    assert "set_variable = { name = pp_cplan_ds_profiles_unr value = 100 }" in reset[:reset.index("\n}\n")]
    # the plan pass writes step 0 before the plans' turn; the rank raise sets it back to 0 after itself
    profiles = _read(MOD / "in_game/common/scripted_effects/pp_location_profiles.txt")
    marks_pass = profiles[profiles.index("\npp_lplan_location_turn = {"):]
    assert "save_temporary_scope_value_as = { name = pp_cplan_rs value = 0 }" in marks_pass[:400]
    assert marks_pass.index("name = pp_cplan_rs value = 0") < marks_pass.index("pp_lplan_location_marks = yes")
    from prosper_or_perish_constructor import town_plans as tp

    raise_effect = tp.render_effects([], [])
    assert raise_effect.rstrip().endswith("save_temporary_scope_value_as = { name = pp_cplan_rs value = 0 }\n}")


def test_titles_use_the_players_group_names() -> None:
    """The group key and the player's name differ for two groups: profiles = "Locations" (it builds what the player
    set for single locations), country = "Towns and Buildings"."""
    loc = cpd.texts()
    assert set(cpd.TITLES) == set(cp.GROUPS)
    assert loc["PP_CPLAN_D_TITLE_PROFILES"].startswith("Locations:")
    assert loc["PP_CPLAN_D_TITLE_COUNTRY"].startswith("Towns and Buildings:")
    window_loc = _read(LOC_FOLDER / "pp_construction_plan_l_english.yml")
    for group in cp.GROUPS:
        name = re.search(rf"^  PP_CPLAN_{group.upper()}_RULE: \"(.+)\"$", window_loc, re.MULTILINE)
        assert name, group
        # the pane's title and the rule's tooltip open with the name on the group's row
        assert loc[f"PP_CPLAN_D_TITLE_{group.upper()}"].startswith(name.group(1) + ":"), group
        tooltip = re.search(rf"^  PP_CPLAN_{group.upper()}_RULE_TT: \"#T (.+?)#!", window_loc, re.MULTILINE)
        assert tooltip and tooltip.group(1).split(",")[0] == name.group(1), group


def test_every_text_exists_once() -> None:
    """Every key the generated GUIs use (PP_CPLAN_D_*, the window's rule tooltips, the profile rule states) is defined
    exactly once across the mod's English files with the detail loc as rendered; no PP_CPLAN_D_ key is left unused
    (the weight bars show the saved gold with a PP_CPLAN_D_ key)."""
    gui = cpd.render_gui() + cps.render_weight_gui()
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
    # a text can name another (the outlook's state-dependent parts: [SelectLocalization(..., Localize('KEY'), ...)])
    named = set(re.findall(r"Localize\('([A-Z][A-Z0-9_]+)'\)", cpd.render_loc()))
    for key in named:
        assert counts[key] == 1, f"{key}: defined {counts[key]} times"
    assert {key for key in used | named if key.startswith("PP_CPLAN_D_")} == set(rendered)
    assert all(key.startswith("PP_CPLAN_D_") for key in rendered)
    # a text a text names ($KEY$) exists too
    hand = _read(LOC_FOLDER / "pp_construction_plan_l_english.yml")
    for key in set(re.findall(r"\$(PP_CPLAN_[A-Z0-9_]+)\$", hand)):
        assert counts[key] == 1, key


def test_texts_follow_the_rules() -> None:
    """Data in loc keys only (the GUI uses raw_text for data alone), gold as @gold!, no key a guard of
    test_construction_plan.py rejects, every ScriptValue the right scope's: the country's or a list item's."""
    gui = cpd.render_gui()
    loc = cpd.render_loc()
    assert not re.search(r"\btext = \"[^\"]*\[", gui), "a data text needs raw_text"
    assert not re.search(r"PP_CPLAN_(?:RULE_|MAX|MODE_|PRESET|FOCUS)", gui + loc)
    money = re.compile(r"ScriptValue\('(\w+_(?:had|spent|need|wait|cost_\d+_n))'\)\|0\](.{0,6})")
    found = money.findall(loc)
    assert len(found) >= 6 * len(cp.GROUPS)
    for name, after in found:
        assert after == "@gold!", name
    for match in re.finditer(r"(\w+(?:\.\w+)*)\.ScriptValue\('([a-z0-9_]+)'\)", gui + loc):
        scope, name = match.groups()
        if name.startswith("pp_cplan_log_"):  # a list item = a location
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
    assert 'text = "PP_CPLAN_LAST"' in last and "pp_cplan_last_list = {}" in last and "PP_CPLAN_LAST_SUMMARY" in last
    assert window.index(f"pp_cplan_detail_button_{cp.GROUPS[-1]} = {{}}") < start < window.index("pp_cplan_detail_profiles = {")
    close = window[window.index("button_close_alt = {"):]
    assert "on_action = \"[GetVariableSystem.Clear('pp_cplan_detail')]\"" in close
    # the rows fit the left column (2026-11-20, two columns): label + line + bar + cog + three spacings of 4; Towns and
    # Buildings has no line (its settings are on its own tab), its longer name takes that room (200 + 110 = 120 + 190)
    assert window.count("minimumsize = { 120 -1 } maximumsize = { 120 -1 }") == 5
    assert window.count("minimumsize = { 190 -1 }") == 3 and window.count("widget = { size = { 190 1 } }") == 2
    assert window.count("minimumsize = { 200 -1 } maximumsize = { 200 -1 }") == 1
    assert window.count("widget = { size = { 110 1 } }") == 1
    assert len(cp.GROUPS) == 5 + 1
    bar = 15 + 4 + cp.SEGMENT * cp.WEIGHT_STEPS + 4 + 15 + 4 + 44 + 4 + cp.PURSE_WIDTH  # pp_cplan_weight_bar_<group>
    assert 120 + 190 + bar + 26 + 3 * 4 <= cpd.LEFT_WIDTH and 200 + 110 == 120 + 190
    assert f"minimumsize = {{ {cpd.LEFT_WIDTH} -1 }}\n\t\t\t\t\t\tmaximumsize = {{ {cpd.LEFT_WIDTH} -1 }}" in window


def test_window_frame_and_two_columns() -> None:
    """Jan 2026-11-20: "I hate having to scroll". The window is 1360 x 820 (the other tabs build against it); the
    Global Settings tab is two columns: the settings and the rule groups left, the "Last month" list or a group's pane
    right over the whole height. Nothing on the tab scrolls but the two lists (the "Last month" list and a pane's list
    of what was built)."""
    window = _read(WINDOW)
    assert f"size = {{ {cpd.WINDOW_SIZE[0]} {cpd.WINDOW_SIZE[1]} }}" in window and cpd.WINDOW_SIZE == (1360, 820)
    assert "movable = yes" in window
    # the tab body: window margin 7 + tab margin 15 a side, the Global tab's own margin 10 a side
    assert cpd.TAB_INNER_WIDTH == cpd.WINDOW_SIZE[0] - 2 * 7 - 2 * 15 - 2 * 10
    right = cpd.TAB_INNER_WIDTH - cpd.LEFT_WIDTH - cpd.COLUMN_GAP
    assert cpd.PANE_WIDTH <= right
    # what a pane must hold side by side: the two charts, and the Locations group's grid of three cells
    from prosper_or_perish_constructor import construction_plan_status as cps
    assert 2 * cps.chart_width() + 24 <= cpd.PANE_WIDTH and 3 * cpd.CELL_WIDTH + 2 * 4 <= cpd.PANE_WIDTH
    start = window.index("# ======================== Global settings")
    tab = window[start:window.index("# ======================== Towns and Buildings")]
    assert tab.count("scrollarea") == 0, "the Global tab's lists are the generated types"
    assert re.search(r"hbox = \{\n\t+visible = \"\[Not\(Or\(GetVariableSystem\.HasValue\('pp_cplan_tab', 'country'\)", tab)
    assert f"spacing = {cpd.COLUMN_GAP}" in tab
    left, right_col = tab[:tab.index("# ---- right column")], tab[tab.index("# ---- right column"):]
    for name in ("PP_CPLAN_MASTER", "PP_CPLAN_RESERVE", "PP_CPLAN_BUDGET", "PP_CPLAN_FLOW_SHORT", "PP_CPLAN_RULES",
                 *(f"pp_cplan_weight_bar_{group}" for group in cp.GROUPS)):
        assert name in left and name not in right_col, name
    assert "pp_cplan_last_list = {}" in right_col and all(f"pp_cplan_detail_{g} = {{" in right_col for g in cp.GROUPS)
    # the scrollareas the tab shows: the "Last month" list and one per pane, each around a list only
    gui = cpd.render_gui()
    assert gui.count("scrollarea") == 1 + len(cp.GROUPS)
    assert _type_body(gui, cpd.LAST_LIST).count("datamodel = \"[GetPlayer.MakeScope.GetList(") == len(cp.GROUPS)
    # the other two tabs fill the whole body
    for kind in ("pp_cplan_country_tab", "pp_tplan_set_tab"):
        body = window[window.rindex("vbox = {", 0, window.index(f"{kind} = {{}}")):window.index(f"{kind} = {{}}")]
        assert "layoutpolicy_horizontal = expanding" in body and "layoutpolicy_vertical = expanding" in body, kind


def test_script_values_exist() -> None:
    """Every number the panes read is a script value of the mod (the pass writes them; script side of 2026-11-09)."""
    names: set[str] = set()
    for path in (MOD / "in_game/common/script_values").glob("*.txt"):
        names |= set(re.findall(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{", _read(path), re.MULTILINE))
    used = set(re.findall(r"ScriptValue\('([a-z0-9_]+)'\)", cpd.render_gui() + cpd.render_loc()))
    missing = sorted(used - names)
    assert not missing, f"script values missing: {missing}"


def test_budget_shows_in_the_window() -> None:
    """Budgets that save (Jan 2026-11-10): each rule group's row shows what the group has saved beside its share, with
    one tooltip that says how the budget works; its pane says what it saves for and how far it is; the things held
    back for construction goods and by the market limit show in plain words, only when there are any."""
    weights = cps.render_weight_gui()
    loc = cpd.texts()
    hand = _read(LOC_FOLDER / "pp_construction_plan_l_english.yml")
    assert re.search(r"^  PP_CPLAN_PURSE_TT: \".*\$PP_CPLAN_BUDGET_NOTE\$\"$", hand, re.MULTILINE)
    note = re.search(r"^  PP_CPLAN_BUDGET_NOTE: \"(.+)\"$", hand, re.MULTILINE).group(1)
    assert "saves" in note and "hands on" in note and not re.search(r"\d", note), "plain words, no numbers"
    gui = cpd.render_gui()
    for group in cp.GROUPS:
        why = cp.GROUP_WHY[group]
        key = group.upper()
        bar = _type_body(weights, f"pp_cplan_weight_bar_{group}")
        assert f'text = "PP_CPLAN_D_PURSE_{key}"' in bar and 'tooltip = "PP_CPLAN_PURSE_TT"' in bar
        assert loc[f"PP_CPLAN_D_PURSE_{key}"] == f"[GetPlayer.MakeScope.ScriptValue('pp_cplan_purse_n_{why}')|0]@gold!"
        # every rule tooltip ends with the same note on the budget
        rule = re.search(rf"^  PP_CPLAN_{key}_RULE_TT: \"(.+)\"$", hand, re.MULTILINE).group(1)
        assert rule.endswith("\\n\\n$PP_CPLAN_BUDGET_NOTE$"), group
        pane = _type_body(gui, f"pp_cplan_detail_{group}")
        saves = f"GreaterThan_CFixedPoint(GetPlayer.MakeScope.ScriptValue('pp_cplan_saves_{why}'), '(CFixedPoint)0.5')"
        save = loc[f"PP_CPLAN_D_SAVE_{key}"]
        assert f"Var('pp_cplan_save_type_{why}').GetBuildingType.GetName" in save
        assert f"Var('pp_cplan_save_loc_{why}').GetLocation.GetName" in save
        assert f"ScriptValue('pp_cplan_purse_n_{why}')|0] of [GetPlayer.MakeScope.ScriptValue('pp_cplan_save_cost_n_{why}')|0]@gold!" in save
        shown = re.search(rf"visible = \"\[([^\n]*)\]\"\n\t+text = \"PP_CPLAN_D_SAVE_{key}\"", pane)
        assert shown and saves in shown.group(1), group
        assert "It had" in loc[f"PP_CPLAN_D_GOLD_{key}"] and "saved" in loc[f"PP_CPLAN_D_GOLD_{key}"]
        assert "to spend" not in loc[f"PP_CPLAN_D_GOLD_{key}"], "the old month's gold"
        goods = f"PP_CPLAN_D_GOODS_{key}"
        if group == "profiles":  # among its plan states instead (8); the market limit does not hold a plan back
            assert goods not in loc and "PP_CPLAN_D_PROFILES_ST8" in loc and "PP_CPLAN_D_PROFILES_ST10" not in loc
            assert 'tooltip = "PP_LPROF_ST_8"' in pane
            # a plan waiting for a higher rank (11) has its own cell, counted by the pass
            assert 'text = "PP_CPLAN_D_PROFILES_ST11" tooltip = "PP_LPROF_ST_11"' in pane
            assert "[location_rank|e]" in loc["PP_CPLAN_D_PROFILES_ST11"]
            counter = _read(MOD / "in_game/common/scripted_effects/pp_location_profiles.txt")
            counter = counter[counter.index("\npp_lprof_count_state = {"):]
            assert "name = pp_cplan_ds_profiles_st11 add = 1" in counter[:counter.index("\n}\n")]
            assert ("st11", 100) in cp.SITUATION["profiles"], "the pass keeps the count for the pane"
        else:
            count = f"GreaterThan_CFixedPoint(GetPlayer.MakeScope.ScriptValue('pp_cplan_d_{group}_goods'), '(CFixedPoint)0.5')"
            assert re.search(re.escape(f'visible = "[{count}]"') + rf"\n\t+text = \"{goods}\"", pane), group
            assert "construction goods" in loc[goods]
    # Towns and Buildings and Locations (a plan whose producers need a higher rank) can save for a town or a city
    # upgrade (no building type)
    assert set(cpd.RANK_KEYS) == {"country", "profiles"}
    for group, prefix in cpd.RANK_KEYS.items():
        why = cp.GROUP_WHY[group]
        pane = _type_body(gui, f"pp_cplan_detail_{group}")
        rank = f"GetPlayer.MakeScope.ScriptValue('pp_cplan_save_rank_n_{why}')"
        assert f"Not(GreaterThan_CFixedPoint({rank}, '(CFixedPoint)0.5'))" in pane, group  # a building otherwise
        for number, name in cpd.SAVE_RANKS.items():
            text = loc[f"{prefix}{number}"]
            assert f"ShowLocationRankName('{name}')" in text
            assert f"Var('pp_cplan_save_loc_{why}')" in text and f"pp_cplan_save_cost_n_{why}" in text
            assert f"pp_cplan_purse_n_{why}" in text
            assert re.search(re.escape(f"EqualTo_CFixedPoint({rank}, '(CFixedPoint){number}'))]\"")
                             + rf"\n\t+text = \"{prefix}{number}\"", pane), (group, number)
    assert cpd.RANK_KEYS["country"] == "PP_CPLAN_D_SAVE_RANK_"  # the translations' keys
    from prosper_or_perish_constructor import construction_plan_country as cpc

    assert {name: code - 100 for name, code in cpc.SAVE_RANK.items()} == {name: n for n, name in cpd.SAVE_RANKS.items()}
    # the market limit, in plain words, in the Businesses pane
    business = _type_body(gui, "pp_cplan_detail_business")
    assert 'text = "PP_CPLAN_D_LIMITED_BUSINESS"' in business
    assert "already has enough of that good on the way" in loc["PP_CPLAN_D_LIMITED_BUSINESS"]
    for key, text in loc.items():
        assert "this month's gold" not in text and "may spend" not in text, key
