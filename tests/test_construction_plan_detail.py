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
    assert "limit = { NOT = { has_variable = pp_cplan_log_step_107 } }" in effects
    assert "pp_cplan_why_n" not in gui and "pp_cplan_log_why" not in effects


def test_locations_list_tells_a_rule_from_a_mark() -> None:
    """The Locations group builds a location's profile rules (step = the rule's number) and its marks, the Location
    Plan's "Also build here" (step 0): the list never says "rule 0 of its profile"."""
    pane = _type_body(cpd.render_gui(), "pp_cplan_detail_profiles")
    step = "GreaterThan_CFixedPoint(Scope.ScriptValue('pp_cplan_log_step_105_n'), '(CFixedPoint)0.5')"
    assert re.search(re.escape(f'visible = "[{step}]"') + r"\n\t+text = \"PP_CPLAN_D_PROFILES_WHY\"", pane)
    assert re.search(re.escape(f'visible = "[Not({step})]"') + r"\n\t+text = \"PP_CPLAN_D_PROFILES_WHY_MARK\"", pane)
    loc = cpd.texts()
    assert "of its profile" in loc["PP_CPLAN_D_PROFILES_WHY"]
    marks = _read(LOC_FOLDER / "pp_location_plan_l_english.yml")
    title = re.search(r"^  PP_LPLAN_ALSO_TITLE: \"(.+)\"$", marks, re.MULTILINE).group(1)
    assert title in loc["PP_CPLAN_D_PROFILES_WHY_MARK"] and "marked" in loc["PP_CPLAN_D_PROFILES_WHY_MARK"]
    assert "profile or a mark" in loc["PP_CPLAN_D_OFF_PROFILES"]
    assert "a profile or marks" in loc["PP_CPLAN_D_PROFILES_SIT"]
    # the marks' pass writes step 0, a profile rule its number
    profiles = _read(MOD / "in_game/common/scripted_effects/pp_location_profiles.txt")
    marks_pass = profiles[profiles.index("\npp_lplan_location_turn = {"):]
    assert "save_temporary_scope_value_as = { name = pp_cplan_rs value = 0 }" in marks_pass[:400]
    assert marks_pass.index("name = pp_cplan_rs value = 0") < marks_pass.index("pp_lplan_location_marks = yes")


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
    gui = cpd.render_gui() + cp.render_weight_gui()
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
    # the rows still fit the window (758 px since the bars show the saved gold): label + line + bar + cog; Towns and
    # Buildings has no line (its settings
    # are on its own tab), its longer name takes that room (200 + 130 = 140 + 190)
    assert window.count("minimumsize = { 140 -1 } maximumsize = { 140 -1 }") == 5
    assert window.count("minimumsize = { 190 -1 }") == 3 and window.count("widget = { size = { 190 1 } }") == 2
    assert window.count("minimumsize = { 200 -1 } maximumsize = { 200 -1 }") == 1
    assert window.count("widget = { size = { 130 1 } }") == 1
    assert len(cp.GROUPS) == 5 + 1
    # the window grew by what the saved gold takes in every weight bar (its width + the bar's spacing)
    assert "size = { 758 820 }" in window and 758 - 690 == cp.PURSE_WIDTH + 4


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
    weights = cp.render_weight_gui()
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
        if group == "profiles":  # among its rule states instead (8 and 10)
            assert goods not in loc and "PP_CPLAN_D_PROFILES_ST8" in loc and "PP_CPLAN_D_PROFILES_ST10" in loc
            assert 'tooltip = "PP_LPROF_ST_10"' in pane
        else:
            count = f"GreaterThan_CFixedPoint(GetPlayer.MakeScope.ScriptValue('pp_cplan_d_{group}_goods'), '(CFixedPoint)0.5')"
            assert re.search(re.escape(f'visible = "[{count}]"') + rf"\n\t+text = \"{goods}\"", pane), group
            assert "construction goods" in loc[goods]
    # Towns and Buildings can save for a town or a city upgrade (no building type)
    country = _type_body(gui, "pp_cplan_detail_country")
    rank = "GetPlayer.MakeScope.ScriptValue('pp_cplan_save_rank_n_107')"
    for number, name in cpd.SAVE_RANKS.items():
        assert f"ShowLocationRankName('{name}')" in loc[f"PP_CPLAN_D_SAVE_RANK_{number}"]
        assert re.search(re.escape(f"EqualTo_CFixedPoint({rank}, '(CFixedPoint){number}'))]\"")
                         + rf"\n\t+text = \"PP_CPLAN_D_SAVE_RANK_{number}\"", country), number
    from prosper_or_perish_constructor import construction_plan_country as cpc

    assert {name: code - 100 for name, code in cpc.SAVE_RANK.items()} == {name: n for n, name in cpd.SAVE_RANKS.items()}
    # the market limit, in plain words, in the Businesses pane
    business = _type_body(gui, "pp_cplan_detail_business")
    assert 'text = "PP_CPLAN_D_LIMITED_BUSINESS"' in business
    assert "already has enough of that good on the way" in loc["PP_CPLAN_D_LIMITED_BUSINESS"]
    for key, text in loc.items():
        assert "this month's gold" not in text and "may spend" not in text, key
