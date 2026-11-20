"""Construction Plan outlook (src/prosper_or_perish_constructor/construction_plan_status.py; Jan 2026-11-20: looking at
a rule group's bar you should see whether gold holds it back, whether more gold would build more, or whether it has
more than it needs): the white need bar under each gold bar, the step tooltips of - and +, a status line under each row,
the window's summary line, and the panes' outlook and situation chart. Checked on the rendered output, no finalize."""

from __future__ import annotations

import re
from itertools import product
from pathlib import Path

from prosper_or_perish_constructor import construction_plan as cp
from prosper_or_perish_constructor import construction_plan_detail as cpd
from prosper_or_perish_constructor import construction_plan_status as cps

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mod" / "pp"
WINDOW = MOD / "in_game/gui/pp_construction_plan.gui"
HAND_LOC = MOD / "main_menu/localization/english/pp_construction_plan_l_english.yml"

# the script side's names (2026-11-20), written out by hand so a typo on either side fails
SITUATION = ("profiles", "food", "logistics", "improve", "business")
NEW_VALUES = {"pp_cplan_flow_n", "pp_cplan_flow_known", "pp_cplan_f_all_missing", "pp_cplan_f_all_years",
              "pp_cplan_f_profiles_blocked", "pp_cplan_f_budget_binds", "pp_cplan_f_budget_held"}
for _group in ("profiles", "food", "logistics", "improve", "business", "country"):
    NEW_VALUES |= {f"pp_cplan_f_{_group}_{name}" for name in (
        "status", "missing", "rate", "years", "need_w", "need_up", "up_part", "up_years", "down_part", "down_years")}
for _group in SITUATION:
    NEW_VALUES |= {f"pp_cplan_f_{_group}_sit", f"pp_cplan_hq_{_group}_max"}
    NEW_VALUES |= {f"pp_cplan_hq_{_group}_p_{k}" for k in range(1, 13)}
    NEW_VALUES |= {f"pp_cplan_hq_{_group}_{k}" for k in range(1, 13)}
# what the bars read before (the weight, its part in %, the saved gold)
OLD_VALUES = ({f"pp_cplan_{g}_w" for g in cp.GROUPS} | {f"pp_cplan_part_{g}" for g in cp.GROUPS}
              | {cp.purse_value(g) for g in cp.GROUPS})


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _type_body(gui: str, name: str) -> str:
    match = re.search(rf"^\ttype {name} = \w+ \{{\n", gui, re.MULTILINE)
    assert match, name
    depth, index = 1, match.end()
    while depth:
        depth += {"{": 1, "}": -1}.get(gui[index], 0)
        index += 1
    return gui[match.end():index - 1]


def _balanced(text: str) -> bool:
    depth = 0
    for char in re.sub(r'"[^"\n]*"', '""', re.sub(r"(?m)^\s*#.*$", "", text)):
        depth += {"{": 1, "}": -1}.get(char, 0)
        if depth < 0:
            return False
    return depth == 0


def _hand_keys() -> dict[str, str]:
    return dict(re.findall(r"^  ([A-Za-z0-9_.]+): \"(.*)\"$", _read(HAND_LOC), re.MULTILINE))


def _truth(condition: str, values: dict[str, float]) -> bool:
    """Evaluates a GUI condition of these files (GreaterThan/EqualTo_CFixedPoint, And/And3/Or, Not, ScriptValue)."""
    expression = re.sub(r"GetPlayer\.MakeScope\.ScriptValue\('([a-z0-9_]+)'\)", r"V['\1']", condition)
    expression = re.sub(r"'\(CFixedPoint\)([0-9.]+)'", r"\1", expression)
    functions = {
        "GreaterThan_CFixedPoint": lambda a, b: a > b, "EqualTo_CFixedPoint": lambda a, b: a == b,
        "And": lambda *a: all(a), "And3": lambda *a: all(a), "Or": lambda *a: any(a), "Not": lambda a: not a,
    }
    return bool(eval(expression, {"__builtins__": {}}, {**functions, "V": values}))  # noqa: S307 (our own text)


def _shown(gui: str, key: str) -> list[str]:
    """The visible conditions of every widget whose text is `key`."""
    return re.findall(rf"visible = \"\[([^\n]*)\]\"\n\t*text = \"{key}\"", gui)


def _gui_all() -> str:
    return cps.render_weight_gui() + cpd.render_gui()


def test_every_group_has_its_bar_status_and_tooltips() -> None:
    gui = cps.render_weight_gui()
    assert gui.startswith(cp.HEADER) and _balanced(gui)
    for group in cp.GROUPS:
        key = group.upper()
        bar = _type_body(gui, f"pp_cplan_weight_bar_{group}")
        # the clicks are exactly the old bar's: - and +, and ten zones that set the weight
        call = ("[GetScriptedGui('pp_cplan_weight').Execute(GuiScope.SetRoot(GetPlayer.MakeScope)"
                f".AddScope('pp_key', MakeScopeFlag('{group}')){{}}.End)]")
        clicks = re.findall(r'onclick = "([^"]+)"', bar)
        expected = [call.format(".AddScope('pp_dir', MakeScopeFlag('down'))")]
        expected += [call.format(f".AddScope('pp_n', MakeScopeFlag('w{n}'))") for n in range(1, cp.WEIGHT_STEPS + 1)]
        expected += [call.format(".AddScope('pp_dir', MakeScopeFlag('up'))")]
        assert clicks == expected, group
        # the ten zones cover both bars and explain them (in game 2026-11-20 the white strip's own tooltip never showed);
        # that text keeps the weight's click explanation
        zone_height = cps.BAR_HEIGHT + cps.NEED_HEIGHT
        zones = re.findall(rf"button = \{{\n\t+position = \{{ \d+ 0 \}}\n\t+size = \{{ {cp.SEGMENT} {zone_height} \}}\n"
                           rf"\t+tooltip = \"PP_CPLAN_D_NEED_TT_{key}\"\n", bar)
        assert len(zones) == cp.WEIGHT_STEPS and "PP_CPLAN_WEIGHT_TT" not in bar, group
        assert cpd.texts()[f"PP_CPLAN_D_NEED_TT_{key}"].endswith("$PP_CPLAN_WEIGHT_TT$")
        size = r" = \{\n\t+size = \{ 15 15 \}\n\t+tooltip = "
        assert re.search(r"button_square_minus" + size + f'"PP_CPLAN_D_DOWN_TT_{key}"', bar), group
        assert re.search(r"button_square_plus" + size + f'"PP_CPLAN_D_UP_TT_{key}"', bar), group
        # the white bar: the same scale and width as the gold bar, touching it from below, light against the black
        width = cp.SEGMENT * cp.WEIGHT_STEPS
        need = re.search(r"\n\t+progressbar = \{\n(.*?)\n\t+\}", bar, re.DOTALL).group(1)
        assert f"value = \"[FixedPointToFloat(GetPlayer.MakeScope.ScriptValue('pp_cplan_f_{group}_need_w'))]\"" in need
        assert f"max = {cp.WEIGHT_STEPS}" in need and f"size = {{ {width} {cps.NEED_HEIGHT} }}" in need
        assert f"position = {{ 0 {cps.BAR_HEIGHT} }}" in need and cps.NEED_HEIGHT >= 6
        assert cps.LIGHT in need and cps.BLACK in need
        assert bar.index("progressbar = {") < bar.index("button = {"), "the zones on top, so they get the mouse"
        assert f"ScriptValue('pp_cplan_part_{group}')" in bar and f'text = "PP_CPLAN_D_PURSE_{key}"' in bar
        # the old bar's test reads the type up to its first "\n\t}\n"
        old = re.search(rf"type pp_cplan_weight_bar_{group} = hbox \{{(.*?)\n\t\}}\n", gui, re.DOTALL).group(1)
        assert "button_square_plus" in old and f"PP_CPLAN_D_PURSE_{key}" in old
        status = _type_body(gui, f"pp_cplan_status_{group}")
        assert "ignoreinvisible = yes" in status
        assert ('text = "PP_CPLAN_D_FACT_' + key + '"' in status) == (group in SITUATION), group


def test_every_value_is_a_known_name() -> None:
    assert cps.forecast_values() == NEW_VALUES
    defined: set[str] = set()
    for path in (MOD / "in_game/common/script_values").glob("*.txt"):
        defined |= set(re.findall(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{", _read(path), re.MULTILINE))
    assert not sorted(NEW_VALUES - defined), "the script side writes every one"
    texts = cpd.texts()
    window = _read(WINDOW)
    read = set(re.findall(r"ScriptValue\('([a-z0-9_]+)'\)", _gui_all() + "".join(texts.values()) + window
                          + "".join(_hand_keys().values())))
    new = {name for name in read if name.startswith(("pp_cplan_f_", "pp_cplan_hq_", "pp_cplan_flow"))}
    assert new <= NEW_VALUES, sorted(new - NEW_VALUES)
    outlook = set(re.findall(r"ScriptValue\('([a-z0-9_]+)'\)", cps.render_weight_gui()
                             + "".join(cps.texts().values())))
    assert outlook <= NEW_VALUES | OLD_VALUES, sorted(outlook - NEW_VALUES - OLD_VALUES)
    for group in cp.GROUPS:  # what each group's texts read is its own
        others = [g for g in cp.GROUPS if g != group]
        for key, text in cps.texts().items():
            if key.endswith(f"_{group.upper()}"):
                assert not any(f"_f_{g}_" in text or f"_hq_{g}_" in text for g in others), key


def test_every_text_exists() -> None:
    texts = cpd.texts()
    hand = _hand_keys()
    gui = _gui_all() + _read(WINDOW)
    used = set(re.findall(r"(?:text|tooltip|title) = \"(PP_CPLAN_[A-Z0-9_]+)\"", gui))
    for key in used:
        assert (key in texts) != (key in hand), key
    for key in cps.texts():
        assert key.startswith("PP_CPLAN_D_") and key in texts, key
    # keys a text names: $KEY$ and Localize('KEY')
    for text in list(texts.values()) + list(hand.values()):
        for key in re.findall(r"\$([A-Z][A-Z0-9_]+)\$", text) + re.findall(r"Localize\('([A-Z0-9_]+)'\)", text):
            assert key in texts or key in hand, key
    # every outlook key is used somewhere (the GUIs or another text)
    everything = gui + "".join(texts.values())
    for key in cps.texts():
        assert f'"{key}"' in everything or f"'{key}'" in everything, key
    assert "PP_CPLAN_WEIGHT_TT" in hand
    for group in cp.GROUPS:
        for kind in ("UP", "DOWN"):
            assert texts[f"PP_CPLAN_D_{kind}_TT_{group.upper()}"].startswith("$PP_CPLAN_WEIGHT_TT$\n\n"), group


def test_texts_follow_the_rules() -> None:
    """Plain text: no numbers but live data, links as the other texts, no blank text, gold as @gold!."""
    texts = {**cps.texts(), **{k: v for k, v in _hand_keys().items() if k.startswith("PP_CPLAN_FLOW")}}
    for key, text in texts.items():
        words = re.sub(r"\[[^\]]*\]|\$[A-Z0-9_]+\$|#[A-Za-z]+ |#!", "", text)
        assert words.strip() or "Localize('" in text, f"{key} shows blank"
        assert not re.search(r"\d", words), f"{key}: a number in the text"
        assert not re.search(r"\b(?:feature|profiles?|marks?)\b", words, re.IGNORECASE), key
        for name in re.findall(r"ScriptValue\('(\w+(?:missing))'\)\|0\]", text):
            assert re.search(rf"ScriptValue\('{name}'\)\|0\]@gold!", text), (key, name)
        assert text.count("[") == text.count("]"), key
    # years >= 99 never print as a number: every years value sits behind a never test, or in a never-free state
    for key, text in cps.texts().items():
        if re.search(r"_years'\)\|1\]", text):
            assert key.startswith(("PP_CPLAN_D_Y_", "PP_CPLAN_D_ST_4_", "PP_CPLAN_D_OUTLOOK_4_")), key
    for group in cp.GROUPS:
        key = group.upper()
        for which in ("NOW", "UP", "DOWN"):
            assert f"Localize('PP_CPLAN_D_Y_{which}_{key}')" in "".join(cps.texts().values())
        assert "[provinces|e]" in cps.texts()["PP_CPLAN_D_FACT_FOOD"]
        assert "[market_access|e]" in cps.texts()["PP_CPLAN_D_FACT_LOGISTICS"]
        assert "[population_capacity|e]" in cps.texts()["PP_CPLAN_D_FACT_IMPROVE"]
    assert "handed on to the groups that save" in cps.texts()["PP_CPLAN_D_OUTLOOK_2_FOOD"]
    # the need bar is white (in game 2026-11-20); only the gold chart's "wanted" columns are grey
    for key, text in cps.texts().items():
        assert "grey" not in text.lower(), key
    assert "White:" in cps.texts()["PP_CPLAN_D_NEED_TT_FOOD"]
    # the bar it names is rounded up (8.5 needs 9, in game 2026-11-20); the white bar and the full-bar test keep the
    # exact value
    for group in cp.GROUPS:
        key = group.upper()
        for text in (cps.texts()[f"PP_CPLAN_D_NEED_AT_{key}"], cps.texts()[f"PP_CPLAN_D_NEED_TT_{key}"]):
            assert f"pp_cplan_f_{group}_need_up')|0]" in text and f"pp_cplan_f_{group}_need_w'" not in text, key
        assert f"ScriptValue('pp_cplan_f_{group}_need_w'), '(CFixedPoint)9.5')" in cps.texts()[f"PP_CPLAN_D_OUTLOOK_4_{key}"]


def test_no_status_without_a_text() -> None:
    """Every status 0..5 at any years shows exactly one phrase on its row and in its pane; the fact only once the group
    has looked; the steps once it has looked, one up and one down."""
    weights = cps.render_weight_gui()
    panes = cpd.render_gui()
    for group in cp.GROUPS:
        key = group.upper()
        row = _type_body(weights, f"pp_cplan_status_{group}")
        pane = _type_body(panes, f"pp_cplan_detail_{group}")
        phrases = [phrase for _condition, phrase, _working in cps.status_phrases(group)]
        for status, years, weight in product((0, 1, 2, 3, 4, 5), (0.4, 3.0, 99), (1, 5, 10)):
            values = {f"pp_cplan_f_{group}_status": status, f"pp_cplan_f_{group}_years": years,
                      f"pp_cplan_{group}_w": weight}
            shown = [p for p in phrases if any(_truth(c, values) for c in _shown(row, p))]
            assert len(shown) == 1, (group, status, years, shown)
            # the pane: the same phrase as its headline, and its working under the charts
            in_pane = [p for p in phrases if any(_truth(c, values) for c in _shown(pane, p))]
            assert in_pane == shown, (group, status, years)
            workings = [w for _c, _p, w in cps.status_phrases(group) if any(_truth(c, values) for c in _shown(pane, w))]
            assert len(workings) == 1, (group, status, years, workings)
            if group in SITUATION:
                fact = _shown(row, f"PP_CPLAN_D_FACT_{key}")
                assert len(fact) == 1 and _truth(fact[0], values) == (status >= 2), (group, status)
            ups = [k for k in (f"PP_CPLAN_D_STEP_UP_LACK_{key}", f"PP_CPLAN_D_STEP_UP_{key}", "PP_CPLAN_D_FULL")
                   if any(_truth(c, values) for c in _shown(pane, k))]
            downs = [k for k in (f"PP_CPLAN_D_STEP_DOWN_LACK_{key}", f"PP_CPLAN_D_STEP_DOWN_{key}")
                     if any(_truth(c, values) for c in _shown(pane, k))]
            assert len(ups) == len(downs) == (1 if status >= 2 else 0), (group, status, ups, downs)
            if status >= 2:
                assert (ups[0] == "PP_CPLAN_D_FULL") == (weight == 10)
                assert downs[0].endswith(f"LACK_{key}") == (status >= 4)
                assert ups[0].endswith(f"LACK_{key}") == (status >= 4 and weight < 10)
            # the - and + tooltips: the years only while short of gold (4, 5), the share alone otherwise
            for kind in ("UP", "DOWN"):
                tooltip = cpd.texts()[f"PP_CPLAN_D_{kind}_TT_{key}"]
                condition, yes, no = re.search(r"\[SelectLocalization\((.*), Localize\('(\w+)'\), Localize\('(\w+)'\)\)\]",
                                               tooltip).groups()
                picked = yes if _truth(condition, values) else no
                assert picked == (f"PP_CPLAN_D_STEP_{kind}_LACK_{key}" if status >= 4 else f"PP_CPLAN_D_STEP_{kind}_{key}")
    texts = cpd.texts()
    for group in cp.GROUPS:
        for _condition, phrase, working in cps.status_phrases(group):
            assert texts[phrase].strip() and texts[working].strip()


def test_summary_line_always_says_something() -> None:
    window = _read(WINDOW)
    keys = ("PP_CPLAN_FLOW_UNKNOWN", "PP_CPLAN_FLOW_ENOUGH", "PP_CPLAN_FLOW_SHORT", "PP_CPLAN_FLOW_NEVER")
    conditions = {key: _shown(window, key) for key in keys}
    assert all(len(c) == 1 for c in conditions.values()), conditions
    for known, missing, years in product((0, 1), (0, 250), (0.5, 4, 99)):
        values = {"pp_cplan_flow_known": known, "pp_cplan_f_all_missing": missing, "pp_cplan_f_all_years": years}
        shown = [key for key, (condition,) in conditions.items() if _truth(condition, values)]
        assert len(shown) == 1, (known, missing, years, shown)
    hand = _hand_keys()
    assert "pp_cplan_flow_n" in hand["PP_CPLAN_FLOW_SHORT"] and "pp_cplan_f_all_years" in hand["PP_CPLAN_FLOW_SHORT"]
    assert "never" in hand["PP_CPLAN_FLOW_NEVER"] and "month to tell" in hand["PP_CPLAN_FLOW_UNKNOWN"]
    # above the rule groups, below the gold reserve
    assert window.index('text = "PP_CPLAN_RESERVE"') < window.index("PP_CPLAN_FLOW_UNKNOWN") < window.index(
        'text = "PP_CPLAN_RULES"')


def test_window_places_status_lines() -> None:
    window = _read(WINDOW)
    assert _balanced(window)
    for group in cp.GROUPS:
        assert window.count(f"pp_cplan_status_{group} = {{}}") == 1, group
        # in a vbox with its row, right after the row's hbox (which ends with the cog)
        status = window.index(f"pp_cplan_status_{group} = {{}}")
        start = window.rindex("vbox = {", 0, status)
        depth, index = 1, start + len("vbox = {")
        while depth:
            depth += {"{": 1, "}": -1}.get(window[index], 0)
            index += 1
        box = window[start:index]
        assert re.match(r"vbox = \{\n\t+layoutpolicy_horizontal = expanding\n\t+spacing = 1\n\t+hbox = \{\n", box), group
        assert re.search(rf"pp_cplan_detail_button_{group} = \{{\}}\n\t+\}}\n\t+pp_cplan_status_{group} = \{{\}}\n\t+\}}$",
                         box), group
    assert "size = { 1360 820 }" in window


def test_panes_show_the_outlook_and_the_situation_chart() -> None:
    gui = cpd.render_gui()
    assert _balanced(gui)
    column = _type_body(gui, "pp_cplan_d_look_column")
    width, height = cpd.COLUMN
    assert f"size = {{ {width} {height} }}" in column and cps.BRONZE in column and "max = 100" in column
    for group in cp.GROUPS:
        pane = _type_body(gui, f"pp_cplan_detail_{group}")
        # the outlook right under the header, before the "has not looked" line
        assert pane.index("PP_CPLAN_D_ST_0") < pane.index("pp_cplan_d_column = {")
        assert pane.index('text = "PP_CPLAN_D_GOLD_CAPTION"') < pane.index("pp_cplan_d_column = {")
        assert pane.count("pp_cplan_d_look_column = {") == (cps.LOOKS if group in SITUATION else 0), group
        if group not in SITUATION:
            continue
        places = []
        for look in range(1, cps.LOOKS + 1):
            value = f"ScriptValue('pp_cplan_hq_{group}_p_{look}')"
            assert pane.count(value) == 1, (group, look)
            places.append(pane.index(value))
        assert places == sorted(places, reverse=True), "the oldest look left, the last look right"
        # beside the gold chart: the gold chart's last column comes before the first look column
        assert pane.rindex("pp_cplan_d_column = {") < pane.index("pp_cplan_d_look_column = {")
        assert f'text = "PP_CPLAN_D_LOOK_CAPTION_{group.upper()}"' in pane
    # both charts fit the tab's ~694 px with the spacing between them
    assert 2 * cps.chart_width() + 24 < 694


def test_no_box_directly_inside_a_container() -> None:
    stack: list[str | None] = []
    opener = r"([A-Za-z_][A-Za-z0-9_]*)\s*(?:\"[^\"]*\"\s*)?(?:=\s*\w*\s*)?\{|\}"
    for match in re.finditer(opener, re.sub(r"(?m)^\s*#.*$", "", cps.render_weight_gui())):
        if match.group(0) == "}":
            stack.pop()
            continue
        name = match.group(1)
        parent = stack[-1] if stack else None
        if parent in {"flowcontainer", "container", "dynamicgridbox", "fixedgridbox"}:
            assert name not in {"hbox", "vbox"}, f"{name} directly inside {parent}"
        stack.append(name)
    assert not stack
