"""Construction Plan outlook (Jan 2026-11-20: feedback for the "money sliders": looking at a rule group's bar you
should see its situation, whether gold holds it back, whether more gold would build more, or whether it already has
more than it needs).

Three places show it, all read from the country script values the monthly pass leaves (``FORECAST``):

- the weight bar of each rule group (``render_weight_gui``, replaces ``construction_plan.render_weight_gui`` and goes to
  the same file ``gui/pp_construction_plan_weights.gui``): under the gold bar (the weight the player gives) a thin
  white bar on the same scale (the weight at which the group would pay for all it wants within a year); the - and +
  buttons say what one step does (its share now -> after, and its years now -> after while it lacks gold);
- a status line under each row (``pp_cplan_status_<group>``, the same file; placed by ``pp_construction_plan.gui``):
  a coloured status phrase and the group's situation fact, with a tooltip that gives the working;
- the group's detail pane (construction_plan_detail.py calls ``outlook`` and ``look_chart``): the status sentence and
  what one step more or less would do, and beside the gold chart a chart of the situation number over its last looks.

Every text is a PP_CPLAN_D_ key (``texts``); construction_plan_detail.texts merges them, so they land in the generated
detail loc file. The window's summary line (gold coming in, what all groups lack) is hand-written in
``pp_construction_plan.gui`` and ``pp_construction_plan_l_english.yml``.
"""

from __future__ import annotations

from prosper_or_perish_constructor import construction_plan as cp
from prosper_or_perish_constructor import construction_plan_detail as cpd

LOOKS = 12  # looks the situation chart shows (pp_cplan_hq_<group>_p_<k>, k = 1 the last look)
NEED_HEIGHT = 6  # px of the white bar, right under the gold bar
BAR_HEIGHT = 14  # px of the gold bar (the click zones' height)
STATUS_FONT = 13
BRONZE = "gfx/interface/progressbars/progress_bar_bronze_rotated.dds"
BLACK = "gfx/interface/progressbars/progress_black.dds"
# the white bar: vanilla's light bar (mean brightness ~227, against the black background ~25 and the gold bar ~172)
LIGHT = "gfx/interface/progressbars/progress_bar_whiteish.dds"

# the group's status (pp_cplan_f_<group>_status): 0 off (bar empty or nothing to do), 1 has not looked yet, 2 it has the
# gold for all it asks for, 3 keeping up (pays for all it wants within a year), 4 short of gold (longer), 5 short of
# gold and no gold is coming in. "4n" is 4 at years >= NEVER (it would never get there at this rate).
STATES = (0, 1, 2, 3, 4, 5)
NEVER = 98.5  # years at or above (the pass writes 99) = never at this rate

# the situation number each group counts at its look (pp_cplan_f_<group>_sit and its history); Towns and Buildings has
# none
SITUATION_GROUPS = ("profiles", "food", "logistics", "improve", "business")


# ---- the script values (the script side writes them; tests/test_construction_plan_status.py lists them) ----------


def f_value(group: str, name: str) -> str:
    """The group's forecast: status, missing, rate, years, need_w, up_part, up_years, down_part, down_years, sit."""
    return f"pp_cplan_f_{group}_{name}"


def look_value(group: str, look: int, scaled: bool = True) -> str:
    """The group's situation number at a look (1 = the last), 0..100 of the largest of the LOOKS, or raw."""
    return f"pp_cplan_hq_{group}_p_{look}" if scaled else f"pp_cplan_hq_{group}_{look}"


def look_max(group: str) -> str:
    return f"pp_cplan_hq_{group}_max"


FLOW = "pp_cplan_flow_n"
FLOW_KNOWN = "pp_cplan_flow_known"
ALL_MISSING = "pp_cplan_f_all_missing"
ALL_YEARS = "pp_cplan_f_all_years"
PROFILES_BLOCKED = "pp_cplan_f_profiles_blocked"
F_NAMES = ("status", "missing", "rate", "years", "need_w", "need_up", "up_part", "up_years", "down_part", "down_years")


def forecast_values() -> set[str]:
    """Every new script value this module (and the window's summary line) reads."""
    names = {FLOW, FLOW_KNOWN, ALL_MISSING, ALL_YEARS, PROFILES_BLOCKED}
    for group in cp.GROUPS:
        names |= {f_value(group, name) for name in F_NAMES}
        if group in SITUATION_GROUPS:
            names.add(f_value(group, "sit"))
            names.add(look_max(group))
            for look in range(1, LOOKS + 1):
                names |= {look_value(group, look), look_value(group, look, scaled=False)}
    return names


def weight_value(group: str) -> str:
    return f"pp_cplan_{group}_w"


def part_value(group: str) -> str:
    return f"pp_cplan_part_{group}"


# ---- conditions ---------------------------------------------------------------------------------------------------

_c = cpd._country


def _status(group: str) -> str:
    return _c(f_value(group, "status"))


def is_state(group: str, state: int | str) -> str:
    """The GUI condition of a status (4 = short of gold with years to go, "4n" = short and never at this rate)."""
    status = _status(group)
    never = cpd._above(_c(f_value(group, "years")), NEVER)
    number = 4 if state == "4n" else int(state)
    # a band of +-0.5 around the number, so a status a hair off its whole number still shows; 0 takes everything below
    # 0.5 and 5 everything from 4.5 up, so no value shows nothing
    if number == 0:
        exact = cpd._not(cpd._above(status, 0.5))
    elif number == STATES[-1]:
        exact = cpd._above(status, number - 0.5)
    else:
        exact = cpd._both(cpd._above(status, number - 0.5), cpd._not(cpd._above(status, number + 0.5)))
    if state == 4:
        return cpd._both(exact, cpd._not(never))
    if state == "4n":
        return cpd._both(exact, never)
    return exact


def has_looked(group: str) -> str:
    """Status 2..5: the group looked and the numbers are its own."""
    return cpd._above(_status(group), 1.5)


def lacks(group: str) -> str:
    """Status 4..5: short of gold (more than a year to pay for all it wants, or never). Only then does a step of the
    bar name its years; a group that keeps up (3) pays within a year, so its steps name only the share (in game
    2026-11-20 they read about 0.0 years -> about 0.0 years)."""
    return cpd._above(_status(group), 3.5)


def bar_full(group: str) -> str:
    return cpd._above(_c(weight_value(group)), cp.WEIGHT_STEPS - 0.5)


def _select(condition: str, yes: str, no: str) -> str:
    """Text that depends on a state inside one key (vanilla's LOW_FOOD_CAP_TEXT form)."""
    return f"[SelectLocalization({condition}, Localize('{yes}'), Localize('{no}'))]"


# ---- texts --------------------------------------------------------------------------------------------------------

GOLD = cpd.GOLD_ICON
# what each group's situation number counts: the row's fact, the chart's caption, and the fact's tooltip
FACT = {
    "food": "[provinces|e] short of food a year from now: {n}",
    "logistics": "[locations|e] below the [market_access|e] line: {n}",
    "improve": "[locations|e] near their [population_capacity|e]: {n}",
    "business": "[locations|e] where a business pays back in time: {n}",
    "profiles": "Plans held back for gold: {n}, waiting for workers or goods: {m}",
}
CAPTION = {
    "food": "[provinces|e] short of food",
    "logistics": "[locations|e] below the access line",
    "improve": "[locations|e] near capacity",
    "business": "[locations|e] with a business in time",
    "profiles": "Plans held back for gold",
}
FACT_TT = {
    "food": ("At its last look, the [provinces|e] whose food store would be short a year from now, as the Food rule "
             "group reads it."),
    "logistics": "At its last look, the [locations|e] whose [market_access|e] was below the line set on this row.",
    "improve": ("At its last look, the [locations|e] whose population had reached the share of their "
                "[population_capacity|e] set on this row."),
    "business": ("At its last look, the [locations|e] where a business would pay back its cost within the years set on "
                 "this row."),
    "profiles": ("At its last look, the plans on your [locations|e] that waited only for gold, and those that waited "
                 "for something gold does not buy: free workers, construction goods, a higher [location_rank|e] or a "
                 "closed [building|e]."),
}
OFF_REASON = {
    "profiles": "its bar is empty, the plan is off, or no [location|e] holds a plan",
    "country": "its bar is empty, the plan is off, or nothing is switched on in its tab",
}


def texts() -> dict[str, str]:
    """Every PP_CPLAN_D_ key of the outlook with its English text."""
    show = cpd._show
    out: dict[str, str] = {
        # the status phrases on the rows and in the panes (4 needs the group's years, so it is per group)
        "PP_CPLAN_D_ST_0": "#weak Off#!",
        "PP_CPLAN_D_ST_1": "#weak Has not looked yet#!",
        "PP_CPLAN_D_ST_2": "#P Has the gold for all it asks for#!",
        "PP_CPLAN_D_ST_3": "Keeping up: pays for all it wants within a year",
        "PP_CPLAN_D_ST_4N": "#N Short of gold:#! it never gets there at this rate",
        "PP_CPLAN_D_ST_5": "#N Short of gold, and none is coming in#!",
        "PP_CPLAN_D_NEVER": "never at this rate",
        "PP_CPLAN_D_FULL": "Its bar is full: one step more changes nothing.",
        "PP_CPLAN_D_NEED_FULL": ("Even a full bar may not pay for it within a year with the other bars as they are: "
                                 "lower bars elsewhere or a lower gold reserve give it more."),
        "PP_CPLAN_D_OUTLOOK_1": ("It has not looked at your country yet. Each rule group looks a few times a year; after "
                                 "its first look this says what it lacks and how long that takes."),
        "PP_CPLAN_D_GOLD_CAPTION": "Gold, by month",
        "PP_CPLAN_D_OLDEST_LOOK": "oldest look",
        "PP_CPLAN_D_LAST_LOOK": "last look",
    }
    for group in cp.GROUPS:
        key = group.upper()
        missing = f"{show(f_value(group, 'missing'))}{GOLD}"
        rate = f"{show(f_value(group, 'rate'), 1)}{GOLD}"
        years = show(f_value(group, "years"), 1)
        part = show(part_value(group))

        def years_at(which: str) -> str:
            name = f_value(group, "years" if which == "now" else f"{which}_years")
            return _select(cpd._above(_c(name), NEVER), "PP_CPLAN_D_NEVER", f"PP_CPLAN_D_Y_{which.upper()}_{key}")

        for which in ("now", "up", "down"):
            name = f_value(group, "years" if which == "now" else f"{which}_years")
            out[f"PP_CPLAN_D_Y_{which.upper()}_{key}"] = f"about {show(name, 1)} years"
        out[f"PP_CPLAN_D_ST_4_{key}"] = f"#N Short of gold:#! about {years} years to pay for all it wants"
        # the working, one sentence per state: the status lines' tooltips and the panes' outlook
        reason = OFF_REASON.get(group, "its bar is empty, the plan is off, or it has nothing to do")
        out[f"PP_CPLAN_D_OUTLOOK_0_{key}"] = (
            f"It takes no part of the gold: {reason}. A filled bar gives it a share once it has something to build.")
        handed = "gold it does not need is handed on to the groups that save, so nothing is lost"
        out[f"PP_CPLAN_D_OUTLOOK_2_{key}"] = (
            f"At its last look it had the gold for all it wanted, and it gets {rate} a month at the current bars. Its "
            f"bar can go lower: {handed}.")
        out[f"PP_CPLAN_D_OUTLOOK_3_{key}"] = (
            f"It lacks {missing} for all it wanted at its last look and gets {rate} a month at the current bars, so it "
            "pays for it all within a year. Its bar is about right: a fuller one builds sooner, a lower one leaves "
            "more for the other groups.")
        need = _select(cpd._above(_c(f_value(group, "need_w")), cp.WEIGHT_STEPS - 0.5),
                       "PP_CPLAN_D_NEED_FULL", f"PP_CPLAN_D_NEED_AT_{key}")
        out[f"PP_CPLAN_D_NEED_AT_{key}"] = (
            f"A bar of {show(f_value(group, 'need_up'))} would pay for it within a year, with the other bars as they "
            "are.")
        out[f"PP_CPLAN_D_OUTLOOK_4_{key}"] = (
            f"It lacks {missing} for all it wanted at its last look and gets {rate} a month at the current bars: about "
            f"{years} years to pay for it all. {need}")
        out[f"PP_CPLAN_D_OUTLOOK_4N_{key}"] = (
            f"It lacks {missing} for all it wanted at its last look and gets only {rate} a month at the current bars: "
            f"at this rate it never pays for it all. {need}")
        out[f"PP_CPLAN_D_OUTLOOK_5_{key}"] = (
            f"It lacks {missing} for all it wanted at its last look, and no gold is coming in for it. The rule groups "
            "share only what your treasury gains above the gold reserve, so its bar alone cannot help: a lower "
            "reserve or more income can.")
        # one step of the bar: its share, and while it lacks gold its years
        up = f"{show(f_value(group, 'up_part'))}"
        down = f"{show(f_value(group, 'down_part'))}"
        out[f"PP_CPLAN_D_STEP_UP_{key}"] = f"One step more: its share {part}% -> {up}%."
        out[f"PP_CPLAN_D_STEP_DOWN_{key}"] = f"One step less: its share {part}% -> {down}%."
        out[f"PP_CPLAN_D_STEP_UP_LACK_{key}"] = (
            f"One step more: its share {part}% -> {up}%, the time to pay for all it wants {years_at('now')} -> "
            f"{years_at('up')}.")
        out[f"PP_CPLAN_D_STEP_DOWN_LACK_{key}"] = (
            f"One step less: its share {part}% -> {down}%, the time to pay for all it wants {years_at('now')} -> "
            f"{years_at('down')}.")
        out[f"PP_CPLAN_D_UP_TT_{key}"] = (
            "$PP_CPLAN_WEIGHT_TT$\n\n"
            + _select(lacks(group), f"PP_CPLAN_D_STEP_UP_LACK_{key}", f"PP_CPLAN_D_STEP_UP_{key}"))
        out[f"PP_CPLAN_D_DOWN_TT_{key}"] = (
            "$PP_CPLAN_WEIGHT_TT$\n\n"
            + _select(lacks(group), f"PP_CPLAN_D_STEP_DOWN_LACK_{key}", f"PP_CPLAN_D_STEP_DOWN_{key}"))
        out[f"PP_CPLAN_D_NEED_TT_{key}"] = (
            "#T What you give and what it asks for#!\n"
            f"Gold: the weight you give this rule group, {show(weight_value(group))}. White: the weight at which it "
            f"would pay for all it wants within a year with the other bars as they are, "
            f"{show(f_value(group, 'need_up'))}.\nWhite longer than gold: it is short of gold. White shorter: it gets "
            f"more than it asks for, and {handed}. While it is off or has not looked yet the white bar stays empty.\n\n"
            "$PP_CPLAN_WEIGHT_TT$")
        if group in SITUATION_GROUPS:
            n = show(f_value(group, "sit"))
            out[f"PP_CPLAN_D_FACT_{key}"] = "#weak " + FACT[group].format(n=n, m=show(PROFILES_BLOCKED)) + "#!"
            out[f"PP_CPLAN_D_FACT_TT_{key}"] = (
                FACT_TT[group] + " Its details show how this changed over its last looks.")
            out[f"PP_CPLAN_D_LOOK_CAPTION_{key}"] = f"{CAPTION[group]}, by look"
            out[f"PP_CPLAN_D_LOOK_LEGEND_{key}"] = (
                f"Last look: {show(look_value(group, 1, scaled=False))}, the most: {show(look_max(group))}")
            out[f"PP_CPLAN_D_LOOK_TT_{key}"] = (
                f"#T {CAPTION[group]}, its last looks#!\n{FACT_TT[group]}\nOne column a look, the last look on "
                "the right; a look before its first shows nothing. Each against the largest of them, "
                f"{show(look_max(group))}.")
    return out


# ---- the weight bars and the status lines (gui/pp_construction_plan_weights.gui) ----------------------------------


def _call(group: str, extra: str) -> str:
    """The weight bar's scripted GUI call, exactly as construction_plan.render_weight_gui writes it."""
    return (f"[GetScriptedGui('pp_cplan_weight').Execute(GuiScope.SetRoot(GetPlayer.MakeScope)"
            f".AddScope('pp_key', MakeScopeFlag('{group}')){extra}.End)]")


def _weight_bar(group: str) -> list[str]:
    block = cpd._block
    key = group.upper()
    width = cp.SEGMENT * cp.WEIGHT_STEPS
    value = _c(weight_value(group))
    zones: list[str] = []
    for n in range(1, cp.WEIGHT_STEPS + 1):
        zones += block("button", [
            f"position = {{ {(n - 1) * cp.SEGMENT} 0 }}",
            f"size = {{ {cp.SEGMENT} {BAR_HEIGHT + NEED_HEIGHT} }}",
            f'tooltip = "PP_CPLAN_D_NEED_TT_{key}"',
            f"onclick = \"{_call(group, f".AddScope('pp_n', MakeScopeFlag('w{n}'))")}\"",
        ])
    # white: the weight at which it would pay for all it wants within a year, touching the gold bar; the click zones
    # cover both bars and carry the explanation of the two
    need = block("progressbar", [
        f"position = {{ 0 {BAR_HEIGHT} }}",
        f"size = {{ {width} {NEED_HEIGHT} }}",
        "min = 0",
        f"max = {cp.WEIGHT_STEPS}",
        f"value = \"[FixedPointToFloat({_c(f_value(group, 'need_w'))})]\"",
        f'progresstexture = "{LIGHT}"',
        f'noprogresstexture = "{BLACK}"',
    ])
    bar = block("widget", [
        f"size = {{ {width} {BAR_HEIGHT + NEED_HEIGHT} }}",
        *block("progressbar_framed", [
            "position = { 0 0 }",
            f"size = {{ {width} {BAR_HEIGHT} }}",
            "using = progress_bar_goldish",
            "min = 0",
            f"max = {cp.WEIGHT_STEPS}",
            f'value = "[FixedPointToFloat({value})]"',
        ]),
        "# white: the weight at which it would pay for all it wants within a year (pp_cplan_f_<group>_need_w)",
        *need,
        *zones,
    ])
    return [f"# the {group} group", *block(f"type pp_cplan_weight_bar_{group} = hbox", [
        "spacing = 4",
        *block("button_square_minus", [
            "size = { 15 15 }",
            f'tooltip = "PP_CPLAN_D_DOWN_TT_{key}"',
            f"onclick = \"{_call(group, ".AddScope('pp_dir', MakeScopeFlag('down'))")}\"",
        ]),
        *bar,
        *block("button_square_plus", [
            "size = { 15 15 }",
            f'tooltip = "PP_CPLAN_D_UP_TT_{key}"',
            f"onclick = \"{_call(group, ".AddScope('pp_dir', MakeScopeFlag('up'))")}\"",
        ]),
        *block("text_single", [
            f"raw_text = \"[{_c(part_value(group))}|0]%\"",
            'tooltip = "PP_CPLAN_SHARE_TT"',
            "minimumsize = { 44 -1 }",
            "maximumsize = { 44 -1 }",
            "align = right|nobaseline",
        ]),
        "# what the group has saved (its purse)",
        *block("text_single", [
            f'text = "PP_CPLAN_D_PURSE_{key}"',
            'tooltip = "PP_CPLAN_PURSE_TT"',
            f"minimumsize = {{ {cp.PURSE_WIDTH} -1 }}",
            f"maximumsize = {{ {cp.PURSE_WIDTH} -1 }}",
            "align = right|nobaseline",
        ]),
    ])]


def status_phrases(group: str) -> list[tuple[str, str, str]]:
    """(condition, phrase key, working key) per status; exactly one condition holds for any status 0..5."""
    key = group.upper()
    return [
        (is_state(group, 0), "PP_CPLAN_D_ST_0", f"PP_CPLAN_D_OUTLOOK_0_{key}"),
        (is_state(group, 1), "PP_CPLAN_D_ST_1", "PP_CPLAN_D_OUTLOOK_1"),
        (is_state(group, 2), "PP_CPLAN_D_ST_2", f"PP_CPLAN_D_OUTLOOK_2_{key}"),
        (is_state(group, 3), "PP_CPLAN_D_ST_3", f"PP_CPLAN_D_OUTLOOK_3_{key}"),
        (is_state(group, 4), f"PP_CPLAN_D_ST_4_{key}", f"PP_CPLAN_D_OUTLOOK_4_{key}"),
        (is_state(group, "4n"), "PP_CPLAN_D_ST_4N", f"PP_CPLAN_D_OUTLOOK_4N_{key}"),
        (is_state(group, 5), "PP_CPLAN_D_ST_5", f"PP_CPLAN_D_OUTLOOK_5_{key}"),
    ]


def _status_line(group: str) -> list[str]:
    block = cpd._block
    body = ["layoutpolicy_horizontal = expanding", "ignoreinvisible = yes", "margin = { 6 0 }", "spacing = 10"]
    for condition, phrase, working in status_phrases(group):
        body += block("pp_cplan_status_text", [f'visible = "[{condition}]"', f'text = "{phrase}"',
                                               f'tooltip = "{working}"'])
    if group in SITUATION_GROUPS:
        body += block("pp_cplan_status_text", [f'visible = "[{has_looked(group)}]"',
                                               f'text = "PP_CPLAN_D_FACT_{group.upper()}"',
                                               f'tooltip = "PP_CPLAN_D_FACT_TT_{group.upper()}"'])
    body.append("expand = {}")
    return [f"# the {group} group's status: how it stands for gold, and its situation at its last look",
            *block(f"type pp_cplan_status_{group} = hbox", body)]


def render_weight_gui() -> str:
    """One weight bar per rule group (``pp_cplan_weight_bar_<group>``: - and +, a gold bar of WEIGHT_STEPS steps whose
    every step sets the weight when clicked, under it the white bar of the weight it asks for, the group's part in % and
    the gold it has saved) and its status line (``pp_cplan_status_<group>``). A real slider cannot be used: its value
    only reaches the engine's own functions, never a script."""
    body = [
        "# a status line's text: smaller than the row",
        *cpd._block("type pp_cplan_status_text = text_single", [
            "autoresize = yes", "align = left|nobaseline", f"fontsize = {STATUS_FONT}"]),
        "",
    ]
    for group in cp.GROUPS:
        body += [*_weight_bar(group), "", *_status_line(group), ""]
    return cp.HEADER + "\n" + "\n".join(cpd._block("types PPConstructionPlanWeights", body[:-1])) + "\n"


# ---- the detail panes (construction_plan_detail._pane) ------------------------------------------------------------


def headline(group: str) -> list[str]:
    """The pane's first line: the group's status phrase (one of them shows for any status)."""
    lines: list[str] = []
    for condition, phrase, _working in status_phrases(group):
        lines += cpd._line(phrase, condition, kind="pp_cplan_title")
    return [f"# the {group} group's status", *lines]


def outlook(group: str) -> list[str]:
    """The pane's outlook under the charts: the status's working and what one step more or less of the bar would do
    (two lines: with its years each step's line takes most of the pane's width)."""
    block = cpd._block
    key = group.upper()
    lines: list[str] = []
    for condition, _phrase, working in status_phrases(group):
        lines += cpd._line(working, condition)
    looked = has_looked(group)
    steps = [
        (cpd._both(looked, cpd._both(cpd._not(bar_full(group)), lacks(group))), f"PP_CPLAN_D_STEP_UP_LACK_{key}"),
        (cpd._both(looked, cpd._both(cpd._not(bar_full(group)), cpd._not(lacks(group)))), f"PP_CPLAN_D_STEP_UP_{key}"),
        (cpd._both(looked, bar_full(group)), "PP_CPLAN_D_FULL"),
        (cpd._both(looked, lacks(group)), f"PP_CPLAN_D_STEP_DOWN_LACK_{key}"),
        (cpd._both(looked, cpd._not(lacks(group))), f"PP_CPLAN_D_STEP_DOWN_{key}"),
    ]
    for condition, text in steps:
        lines += cpd._line(text, condition)
    return [f"# the {group} group's outlook: why it stands so for gold, and what a step of its bar does",
            *block("vbox", ["layoutpolicy_horizontal = expanding", "ignoreinvisible = yes", "spacing = 2", *lines])]


def chart_width() -> int:
    width, _height = cpd.COLUMN
    return cp.HISTORY_MONTHS * width + (cp.HISTORY_MONTHS - 1) * cpd.COLUMN_SPACING


def look_chart(group: str) -> list[str]:
    """The situation number over the last LOOKS looks, one column a look, the last look on the right (beside the gold
    chart); Towns and Buildings has none."""
    if group not in SITUATION_GROUPS:
        return []
    block = cpd._block
    key = group.upper()
    tooltip = f"PP_CPLAN_D_LOOK_TT_{key}"
    columns: list[str] = []
    for look in range(LOOKS, 0, -1):  # the oldest left, the last look right
        columns += block("pp_cplan_d_look_column", [
            f'tooltip = "{tooltip}"',
            *block('blockoverride "pp_cplan_d_look"',
                   [f'value = "[FixedPointToFloat({_c(look_value(group, look))})]"']),
        ])
    return block("vbox", [
        "spacing = 2",
        f"minimumsize = {{ {chart_width()} -1 }}",
        f'pp_cplan_label = {{ text = "PP_CPLAN_D_LOOK_CAPTION_{key}" tooltip = "{tooltip}" '
        f"maximumsize = {{ {chart_width()} -1 }} }}",
        *block("hbox", [f"spacing = {cpd.COLUMN_SPACING}", *columns]),
        *block("hbox", [
            "layoutpolicy_horizontal = expanding",
            'pp_cplan_label = { text = "PP_CPLAN_D_OLDEST_LOOK" default_format = "#weak" }',
            "expand = {}",
            'pp_cplan_label = { text = "PP_CPLAN_D_LAST_LOOK" default_format = "#weak" }',
        ]),
        *block("hbox", ["spacing = 6", "pp_cplan_d_swatch_look = {}",
                        f'pp_cplan_label = {{ text = "PP_CPLAN_D_LOOK_LEGEND_{key}" tooltip = "{tooltip}" }}']),
    ])


def shared_types() -> list[str]:
    """The situation chart's column (one bronze bar, the gold chart's size) and its swatch."""
    width, height = cpd.COLUMN
    return [
        "# one look of the situation chart: bronze, 0..100 of the largest of its looks",
        *cpd._block("type pp_cplan_d_look_column = widget", [
            f"size = {{ {width} {height} }}",
            *cpd._block("background", ["using = color_super_dark_brown_texture", "alpha = 0.6"]),
            *cpd._block("progressbar", cpd._bar(BRONZE, "pp_cplan_d_look")),
        ]),
        "",
        *cpd._block("type pp_cplan_d_swatch_look = icon", ["size = { 10 14 }", f'texture = "{BRONZE}"']),
    ]
