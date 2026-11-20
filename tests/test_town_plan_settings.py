"""The Construction Plan window's Plans tab (town_plan_settings_gui.py, 2026-11-20, Jan): the settings every
town-right plan shares (payback limit, never at a loss, wait for workers, take turns, the game's close-buildings
automation) and, per plan, an icon that selects it and a card with what it builds and its own payback limit."""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import pytest

from prosper_or_perish_constructor import town_plan_options as tpo
from prosper_or_perish_constructor import town_plan_settings_gui as tps
from prosper_or_perish_constructor import town_plans
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
MOD = ROOT / "mod" / "pp"
WINDOW = MOD / "in_game/gui/pp_construction_plan.gui"
WINDOW_LOC = MOD / "main_menu/localization/english/pp_construction_plan_l_english.yml"
LOC_DIR = MOD / "main_menu/localization"
DATA_TYPES = Path(r"C:\Users\Anwender\Documents\Paradox Interactive\Europa Universalis V\logs\data_types")
DATA_TYPES_WSL = Path("/mnt/c/Users/Anwender/Documents/Paradox Interactive/Europa Universalis V/logs/data_types")
PLANS = "GetVariableSystem.HasValue('pp_cplan_tab', 'plans')"
COUNTRY = "GetVariableSystem.HasValue('pp_cplan_tab', 'country')"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


@cache
def _items() -> list[tps.Item]:
    return tps.build_items(ROOT, PROJECT, MOD, vanilla_root(ROOT, PROJECT))


@cache
def _gui() -> str:
    return _read(MOD / tps.GUI)


@cache
def _loc() -> dict[str, str]:
    return dict(re.findall(r'^  ([A-Za-z0-9_.]+): "(.*)"$', _read(MOD / tps.LOC), re.MULTILINE))


@cache
def _all_loc_keys() -> set[str]:
    keys: set[str] = set()
    for path in LOC_DIR.rglob("*_l_english.yml"):
        keys |= set(re.findall(r"(?m)^\s*([A-Za-z0-9_.\-]+):\d*\s*\"", _read(path)))
    return keys


def _block(text: str, start: int) -> str:
    depth, index = 0, text.index("{", start)
    while True:
        depth += {"{": 1, "}": -1}.get(text[index], 0)
        index += 1
        if depth == 0:
            return text[start:index]


def test_generated_files_are_current() -> None:
    assert _gui() == tps.render_gui(_items()), "run the town_plan_settings_gui pass (ppc build)"
    assert _read(MOD / tps.LOC) == tps.render_loc(_items()).lstrip("\ufeff")


def test_plans_is_the_third_tab_and_its_body_is_gated() -> None:
    window = _read(WINDOW)
    tabs = re.findall(r"button_main_tab_alt = \{.*?text = \"(PP_CPLAN_TAB_\w+)\"", window, re.DOTALL)
    assert tabs == ["PP_CPLAN_TAB_PLAN", "PP_CPLAN_TAB_COUNTRY", "PP_CPLAN_TAB_PLANS"]
    first = f"[Not(Or({COUNTRY}, {PLANS}))]"
    assert window.count(f'down = "{first}"') == 1 and window.count(f'visible = "{first}"') == 1
    assert window.count(f'down = "[{PLANS}]"') == 1
    assert window.count(f"onclick = \"[GetVariableSystem.Set('pp_cplan_tab', 'plans')]\"") == 1
    # the body: one vbox shown only on this tab, holding the generated type and nothing else to evaluate
    at = window.index(f'visible = "[{PLANS}]"')
    body = _block(window, window.rindex("vbox = {", 0, at))
    assert f"{tps.TAB_TYPE} = {{}}" in body and window.count(f"{tps.TAB_TYPE} = {{}}") == 1
    assert f"type {tps.TAB_TYPE} = vbox {{" in _gui()
    loc = _read(WINDOW_LOC)
    assert '  PP_CPLAN_TAB_PLANS: "Plans"\n' in loc and "  PP_CPLAN_TAB_PLANS_TT: " in loc


def test_every_plan_has_an_icon_and_a_card() -> None:
    gui = _gui()
    keys = [plan.key for plan in town_plans.plans(ROOT, PROJECT, MOD, vanilla_root(ROOT, PROJECT))]
    assert [item.key for item in _items()] == keys
    for item in _items():
        assert gui.count(f"onclick = \"[GetVariableSystem.Set('{tps.SELECTED}', '{item.key}')]\"") == 1, item.key
        assert gui.count(f'tooltip = "PP_TPLAN_SET_PICK_{item.upper}"') == 1, item.key
        assert gui.count(f'visible = "[{tps.selected(item)}]"') == 2, item.key  # the icon's frame and the card
        card = _block(gui, gui.index(f"vbox = {{ # {item.key}\n"))
        assert f'text = "PP_TPLAN_SET_CARD_{item.upper}"' in card
        for gui_name in (tps.PB_UP, tps.PB_DOWN, tps.PB_RESET):
            assert f"GetScriptedGui('{gui_name}').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).AddScope('pp_key', MakeScopeFlag('{item.key}')).End)" in card
        assert f'visible = "[{tps.own(item)}]"' in card and f'visible = "[Not({tps.own(item)})]"' in card
        # its own limit or a per-plan option of its own: a dot on its icon
        assert gui.count(f'visible = "[{tps.marked(item)}]" size = {{ 10 10 }}') == 1
        assert tps.own(item) in tps.marked(item)
        for option in tpo.per_plan():
            assert (tps.is_on(option.own_value + item.key) in tps.marked(item)) == item.good, item.key
    # the card names every building of the plan as a link, lowest tier first (or tells a long list in a sentence)
    for item in _items():
        text = _loc()[f"PP_TPLAN_SET_CARD_{item.upper}"]
        named = re.findall(r"\[ShowBuildingTypeName\('(\w+)'\)\|e\]", text)
        if len(item.builds) <= tps.MAX_NAMES:
            assert named == list(item.builds), item.key
        assert ("[ShowLocationRankName(" in text) == bool(item.rank), item.key
        for right in (item.charter, item.rights):
            if right:
                assert f"[ShowTownRightsName('{right}')]" in text, item.key
    assert any(item.rights for item in _items()) and any(item.rank for item in _items())


def _used_guis(text: str) -> set[str]:
    return set(re.findall(r"GetScriptedGui\('(\w+)'\)", text))


def _used_values(text: str) -> set[str]:
    return set(re.findall(r"ScriptValue\('(\w+)'\)", text))


def test_only_contract_names_are_called() -> None:
    """Every scripted GUI and script value the tab uses is one of the names agreed with the script side."""
    texts = _gui() + "\n".join(_loc().values())
    assert _used_guis(texts) == set(tps.CONTRACT_GUIS)
    assert _used_values(texts) <= tps.used_values(_items())
    assert {tps.PB_ALL, tps.LOSS, tps.STAFF, tps.ORDER, tps.CLOSE} <= _used_values(texts)
    keys = {item.key for item in _items()} | {tps.ALL}
    assert set(re.findall(r"MakeScopeFlag\('(\w+)'\)", _gui())) <= keys
    # the payback reset takes a plan, never all
    assert f"GetScriptedGui('{tps.PB_RESET}').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).AddScope('pp_key', MakeScopeFlag('all'))" not in _gui()


def _defined(folder: str) -> set[str]:
    found: set[str] = set()
    for path in (MOD / "in_game/common" / folder).glob("*.txt"):
        found |= set(re.findall(r"(?m)^(\w+)\s*=\s*\{", _read(path)))
    return found


def test_contract_names_exist_once_the_script_side_is_in() -> None:
    guis = _defined("scripted_guis")
    if not set(tps.CONTRACT_GUIS) & guis:
        pytest.skip("the town plan settings scripts are not in the mod yet")
    assert set(tps.CONTRACT_GUIS) <= guis, sorted(set(tps.CONTRACT_GUIS) - guis)
    values = _defined("script_values")
    missing = sorted(tps.used_values(_items()) - values)
    assert not missing, missing[:10]
    assert hasattr(town_plans, "PAYBACK_STEPS")


def test_every_text_exists_and_none_is_blank() -> None:
    keys = _all_loc_keys()
    used = set(re.findall(r'(?:text|tooltip) = "([A-Z][A-Z0-9_]+)"', _gui()))
    for text in _loc().values():
        used |= set(re.findall(r"'(PP_[A-Z0-9_]+)'", text)) | set(re.findall(r"\$(PP_[A-Z0-9_]+)\$", text))
    used |= {"PP_CPLAN_TAB_PLANS", "PP_CPLAN_TAB_PLANS_TT"}
    missing = sorted(used - keys)
    assert not missing, missing
    blank = {key for key, text in _loc().items() if not text and key != "PP_TPLAN_SET_EMPTY"}
    assert not blank, blank


def test_no_numbers_in_player_text() -> None:
    texts = dict(_loc())
    window = dict(re.findall(r'^  (PP_CPLAN_TAB_PLANS\w*): "(.*)"$', _read(WINDOW_LOC), re.MULTILINE))
    texts.update(window)
    for key, text in texts.items():
        plain = re.sub(r"\[[^\]]*\]|\$[A-Za-z0-9_|]+\$|#[A-Za-z_]+|#!|\\n", "", text)
        assert not re.search(r"\d", plain), (key, plain)
    # the card names buildings and rights by the game's own names, never typed
    for item in _items():
        assert "ShowBuildingTypeNameWithNoTooltip" not in texts[f"PP_TPLAN_SET_CARD_{item.upper}"]


def test_braces_balance() -> None:
    for text in (_gui(), _read(WINDOW)):
        depth = 0
        for char in text:
            depth += {"{": 1, "}": -1}.get(char, 0)
            assert depth >= 0
        assert depth == 0
        assert text.count("[") == text.count("]")


def test_alone_and_rights_settings() -> None:
    """2026-11-20: other businesses in planned locations (pp_tplan_alone) and grant a plan's charter and rights
    (pp_tplan_rights_off): a value (1 = the default), a toggle that flips the variable, a row with its texts."""
    values = _read(MOD / town_plans.VALUES)
    for value, var in ((tps.ALONE, town_plans.ALONE_VAR), (tps.RIGHTS, town_plans.RIGHTS_OFF_VAR)):
        block = _block(values, values.index(f"\n{value} = {{") + 1)
        assert block.startswith(f"{value} = {{\n\tvalue = 1\n") and f"limit = {{ has_variable = {var} }}" in block
        assert "value = 0" in block
    guis = _read(MOD / town_plans.SETTINGS_GUIS)
    for gui, var in ((tps.TOGGLES["alone"], town_plans.ALONE_VAR), (tps.TOGGLES["rights"], town_plans.RIGHTS_OFF_VAR)):
        block = _block(guis, guis.index(f"\n{gui} = {{") + 1)
        assert "scope = country" in block and "is_ai = no" in block
        assert f"pp_cplan_flip = {{ var = {var} }}" in block
    assert (tps.ALONE, tps.RIGHTS) == (town_plans.ALONE_VALUE, town_plans.RIGHTS_VALUE)
    assert (tps.TOGGLES["alone"], tps.TOGGLES["rights"]) == (town_plans.TOGGLE_ALONE_GUI, town_plans.TOGGLE_RIGHTS_GUI)
    gui = _gui()
    for key, value in (("ALONE", tps.ALONE), ("RIGHTS", tps.RIGHTS)):
        assert f'pp_tplan_set_label = {{ text = "PP_TPLAN_SET_{key}" tooltip = "PP_TPLAN_SET_{key}_TT" }}' in gui
        assert gui.count(f"ScriptValue('{value}')") == 2  # the On and the Off switch
        assert _loc()[f"PP_TPLAN_SET_{key}"] and _loc()[f"PP_TPLAN_SET_{key}_TT"].startswith("#T ")
    assert "[political_influence|e]" in _loc()["PP_TPLAN_SET_RIGHTS_TT"]
    assert "[town_rights|e]" in _loc()["PP_TPLAN_SET_RIGHTS_TT"]
    assert "[location|e]" in _loc()["PP_TPLAN_SET_ALONE_TT"]


def test_settings_rows_in_order_and_close_together() -> None:
    gui = _gui()
    rows = re.findall(r'pp_tplan_set_label = \{ text = "(PP_TPLAN_SET_[A-Z]+)" tooltip = "PP_TPLAN_SET_[A-Z]+_TT" \}',
                      gui[:gui.index("# ---- Each plan")])
    assert rows == ["PP_TPLAN_SET_PB", "PP_TPLAN_SET_LOSS", "PP_TPLAN_SET_STAFF", "PP_TPLAN_SET_FREE",
                    "PP_TPLAN_SET_ALONE", "PP_TPLAN_SET_ORDER", "PP_TPLAN_SET_RIGHTS", "PP_TPLAN_SET_CLOSE"]
    # the eight rows and the new shared options sit in one tighter vbox
    match = re.search(r"vbox = \{\n\s*layoutpolicy_horizontal = expanding\n\s*spacing = 2\n", gui)
    assert match and match.start() < gui.index("# ---- Each plan")
    block = _block(gui, match.start())
    assert all(f'text = "{row}"' in block for row in rows)
    assert all(f'text = "{tps.opt_key(option)}"' in block for option in tpo.options(tpo.ALL))


# ---- the layout without scrolling and the options of town_plan_options.py (2026-11-20)


def test_no_scrolling_and_the_tab_fits() -> None:
    gui = _gui()
    assert "scrollarea" not in gui and "scrollbar" not in gui and "scrollwidget" not in gui
    # every plan icon at once: rows per group from the real plan list
    groups = tps.groups(_items())
    assert tps.grid_rows(_items()) == sum(-(-len(members) // tps.PER_ROW) for _, members in groups)
    assert tps.GUTTER + tps.GUTTER_GAP + tps.PER_ROW * (tps.TILE_SIZE + tps.TILE_GAP) - tps.TILE_GAP <= tps.RIGHT_W
    assert 2 * tps.MARGIN_X + tps.LEFT_W + tps.COL_GAP + tps.RIGHT_W <= tps.TAB_W
    # the fixed heights of the taller column (the right one with the tallest card) within the budget
    heights = tps.layout_heights(_items())
    assert max(heights["left"], heights["right"]) <= tps.TAB_H, heights
    for item in _items():
        rows = tps.card_rows(item)
        assert rows == 1 + len(tps.card_options(item))
    food = next(item for item in _items() if item.key == "food")
    assert tps.card_rows(food) == 1 + len(tpo.options(tpo.FOOD))
    # the card's text column and its rows fit the right column
    assert tps.CARD_TEXT_W + tps.CARD_COL_GAP < tps.RIGHT_W


def test_a_line_divides_the_two_columns() -> None:
    # Jan 2026-11-21: "it looks like they are connected". One line over the tab's height between "All plans" and
    # "Each plan", with clear room on both sides.
    gui = _gui()
    all_plans, each_plan = gui.index("---- All plans ----"), gui.index("---- Each plan")
    between = gui[all_plans:each_plan]
    assert between.count("using = color_new_gold_texture") == 1
    line = between[between.index("icon = {"):]
    assert "layoutpolicy_vertical = expanding" in line and f"size = {{ {tps.DIVIDER_W} -1 }}" in line
    assert tps.DIVIDER_PAD >= 24 and tps.COL_GAP == 2 * tps.DIVIDER_PAD + tps.DIVIDER_W
    assert f"spacing = {tps.DIVIDER_PAD}\n" in gui[:all_plans]


def _cards_removed(gui: str) -> str:
    for item in _items():
        at = gui.index(f"vbox = {{ # {item.key}\n")
        gui = gui[:at] + gui[at + len(_block(gui, at)):]
    return gui


def test_options_rendered_where_they_belong() -> None:
    gui = _gui()
    goods = [item for item in _items() if item.good]
    outside = _cards_removed(gui)
    left = gui[:gui.index("# ---- Each plan")]
    for option in tpo.OPTIONS:
        label = f'pp_tplan_set_label = {{ text = "{tps.opt_key(option)}" tooltip = "{tps.opt_key(option, "_TT")}" }}'
        if option.where == tpo.ALL:
            assert label in left, option.key
            key = tps.ALL if option.per_plan else None
            for gui_name in option.guis[:2] if option.kind == "stepper" else option.guis[:1]:
                assert tps.call(gui_name, key) in left, (option.key, gui_name)
        else:
            assert label not in outside, option.key
        if option.per_plan:
            assert option.kind == "stepper" and len(option.guis) == 3
            # the reset takes a plan, never all
            assert tps.call(option.guis[2], tps.ALL) not in gui
            for item in goods:
                card = _block(gui, gui.index(f"vbox = {{ # {item.key}\n"))
                assert label in card and f'text = "{tps.opt_value_key(option, item.key)}"' in card, item.key
                for gui_name in option.guis:
                    assert tps.call(gui_name, item.key) in card, (item.key, gui_name)
                own = tps.is_on(option.own_value + item.key)
                assert f'visible = "[Not({own})]" text = "PP_TPLAN_SET_SAME"' in card
                assert f'visible = "[{own}]" text = "PP_TPLAN_SET_RESET"' in card
        if option.where in (tpo.FOOD, tpo.TRADE):
            for item in _items():
                card = _block(gui, gui.index(f"vbox = {{ # {item.key}\n"))
                assert (label in card) == (item.key == option.where), (option.key, item.key)
    # kinds: a switch two buttons, a cycle one button per state, a stepper its value and two steps
    for option in tpo.OPTIONS:
        if option.kind == "switch":
            assert gui.count(f'text = "{tps.opt_key(option, "_S1")}"') == gui.count(f'text = "{tps.opt_key(option, "_S0")}"') == 1
        elif option.kind == "cycle":
            for index in range(len(option.states)):
                assert gui.count(f'visible = "[{tps.equals(option.value, index)}]" text = "{tps.opt_key(option, f"_S{index}")}"') == 1
        else:
            assert f'tooltip = "{tps.opt_key(option, "_DOWN_TT")}"' in gui and f'tooltip = "{tps.opt_key(option, "_UP_TT")}"' in gui


def test_per_plan_reads_only_in_the_selected_card() -> None:
    """A visible widget evaluates its values every frame: outside the cards (only the selected plan's shows) a plan's
    value is read only by its icon's dot."""
    outside = _used_values(_cards_removed(_gui()))
    prefixes = {tps.PB_YEARS, *(o.value for o in tpo.per_plan()), *(o.set_value for o in tpo.per_plan())}
    dots = {tps.PB_OWN, *(o.own_value for o in tpo.per_plan())}
    for item in _items():
        assert not {prefix + item.key for prefix in prefixes} & outside, item.key
        assert {prefix + item.key for prefix in dots} & outside <= {tps.PB_OWN + item.key} | (
            {o.own_value + item.key for o in tpo.per_plan()} if item.good else set())


def test_option_texts() -> None:
    loc = _loc()
    goods = [item.key for item in _items() if item.good]
    for option in tpo.OPTIONS:
        assert loc[tps.opt_key(option)] == option.label
        assert loc[tps.opt_key(option, "_TT")] == option.tooltip.replace('"', '\\"').replace("\n", "\\n")
        if option.kind == "stepper":
            for key in ([tps.ALL, *goods] if option.per_plan else [None]):
                name, set_name, _ = tps.opt_names(option, key)
                shown = loc[tps.opt_value_key(option, key)]
                assert tps.is_on(set_name) in shown and tps.opt_key(option, "_S0") in shown
                assert f"ScriptValue('{name}')|0]" in loc[tps.opt_value_key(option, key, "_N")]
        else:
            assert [loc[tps.opt_key(option, f"_S{i}")] for i in range(len(option.states))] == list(option.states)


def test_option_values_and_guis_are_in_the_contract() -> None:
    goods = [item.key for item in _items() if item.good]
    assert tpo.value_names(goods) <= tps.used_values(_items())
    assert tpo.gui_names() <= set(tps.CONTRACT_GUIS)
    assert tpo.value_names(goods) <= _used_values(_gui() + "\n".join(_loc().values()))


def test_gui_functions_exist_in_the_data_type_dump() -> None:
    folder = DATA_TYPES if DATA_TYPES.is_dir() else DATA_TYPES_WSL
    if not folder.is_dir():
        pytest.skip("no data type dump")
    dump = "".join(path.read_text(encoding="utf-8", errors="replace") for path in folder.glob("data_types_*.txt"))
    names = set(re.findall(r"^([A-Za-z_][A-Za-z0-9_.]*)(?:\(|$)", dump, re.MULTILINE))
    used = set(re.findall(r"([A-Z][A-Za-z0-9_]*)\(", _gui() + "\n".join(_loc().values())))
    # (the GuiScope builder the scripted GUI calls use is the window's own, in game since 2026-11-06)
    used |= {"VariableSystem.HasValue", "VariableSystem.Set", "VariableSystem.Exists", "ScriptedGui.Execute",
             "Scope.ScriptValue", "Country.MakeScope"}
    used -= {"CFixedPoint"}  # a cast, not a function
    missing = sorted(name for name in used if name not in names and f"{name}(" not in dump)
    assert not missing, missing
