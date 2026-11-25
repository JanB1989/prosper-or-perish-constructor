"""The advance tree shows every unresearched advance's research time in years (tools/port_vanilla_gui.py)."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MOD_ROOT = REPO / "mod" / "pp"


def _tool():
    spec = importlib.util.spec_from_file_location("port_vanilla_gui", REPO / "tools" / "port_vanilla_gui.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _vanilla() -> Path:
    from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

    root = vanilla_root(REPO, REPO / "constructor.toml") / "game"
    if not root.is_dir():
        pytest.skip("no vanilla game files")
    return root


def test_the_tree_is_vanilla_plus_the_badges() -> None:
    tool = _tool()
    vanilla = tool._read(_vanilla() / tool.GUI / tool.TECH_VIEW)
    mod = tool._read(MOD_ROOT / tool.GUI / tool.TECH_VIEW)
    assert mod == tool.port_technology_view(vanilla), "run tools/port_vanilla_gui.py"
    added = [line.strip() for line in mod.splitlines() if tool.ADVANCE_TIME_MARK in line]
    mark = tool.ADVANCE_TIME_MARK
    # the round icon's button, the card's button, then the card's six unlock artwork widgets
    assert added == [f"using = pp_advance_time_chip_round {mark}", f"using = pp_advance_time_chip {mark}"] + \
        [f"using = pp_advance_time_chip_art {mark}"] * 6
    # nothing else differs from vanilla
    stripped = "\n".join(line for line in mod.splitlines() if mark not in line)
    assert re.sub(r"\n{2,}", "\n", stripped) == re.sub(r"\n{2,}", "\n", vanilla.rstrip("\n"))


def test_the_badge_sits_in_the_layers_that_are_drawn_on_top() -> None:
    """The card's button and every unlock artwork widget of the card end with the badge (a widget added to the node
    itself is drawn behind the card); both placements name the same spot of the card."""
    tool = _tool()
    mod = tool._read(MOD_ROOT / tool.GUI / tool.TECH_VIEW)
    visible, _ = tool._ADVANCE_NODE_FORMS[1]
    at = mod.index(visible)
    end = tool._block_end(mod, mod.rfind("{", 0, at))
    node = mod[at:end]
    button = node.index("# button not in progress")
    block = node[button:tool._block_end(node, node.index("{", button))]
    assert block.rstrip("}").rstrip().endswith(f"using = pp_advance_time_chip {tool.ADVANCE_TIME_MARK}")
    starts = [m.start() for m in re.finditer(r"widget = \{\s*#unlock", node)]
    assert len(starts) == 6
    for start in starts:
        block = node[start:tool._block_end(node, node.index("{", start))]
        assert block.rstrip("}").rstrip().endswith(f"using = pp_advance_time_chip_art {tool.ADVANCE_TIME_MARK}")
    gui = tool._read(MOD_ROOT / tool.GUI / tool.ADVANCE_TIME_GUI)
    width, right, top = tool.ADVANCE_TIME_BADGE[0], tool.ADVANCE_TIME_BADGE_RIGHT, tool.ADVANCE_TIME_BADGE_TOP
    assert f"position = {{ -{right} {top} }}" in gui                       # in the 270-wide button
    assert f"position = {{ -{right + (305 - 270) // 2} {top - 2} }}" in gui   # in the 305-wide artwork, 2 lower
    assert right + width < (270 - 113) // 2 + 10                           # clear of the medallion (113 wide, centred)


def test_the_chip_templates_and_their_text() -> None:
    tool = _tool()
    gui = tool._read(MOD_ROOT / tool.GUI / tool.ADVANCE_TIME_GUI)
    assert gui == tool.advance_time_gui(), "run tools/port_vanilla_gui.py"
    for template in ("pp_advance_time_number", "pp_advance_time_badge", "pp_advance_time_chip",
                     "pp_advance_time_chip_art", "pp_advance_time_chip_round"):
        assert gui.count(f"template {template} {{") == 1
    assert gui.count("{") == gui.count("}")
    years = tool.advance_years()
    assert "'pp_advance_cost'" in years and "'pp_advance_cost_past'" in years and "HasResearchCostDiscount" in years
    assert "research_speed" in years and "research_speed_modifier" in years
    # three colour bands that cover every duration exactly once
    assert gui.count('visible = "[') == 6   # three colour bands, and each of the three placements only where the cost is known
    for fmt in ("pp_advance_time_fast", "pp_advance_time_middling", "pp_advance_time_slow"):
        assert gui.count(f"name = {fmt}\n") == 1 and gui.count(f'default_format = "#{fmt}"') == 1
    assert gui.count("name = pp_advance_time_unit\n") == 1
    assert f"'(float){tool.ADVANCE_TIME_FAST_YEARS}'" in gui and f"'(float){tool.ADVANCE_TIME_SLOW_YEARS}'" in gui
    assert tool.ADVANCE_TIME_FAST_YEARS < tool.ADVANCE_TIME_SLOW_YEARS
    loc = (MOD_ROOT / "main_menu/localization/english/pp_advance_time_l_english.yml").read_text(encoding="utf-8-sig")
    assert "PP_ADVANCE_YEARS_UNIT:" in loc and "Localize('PP_ADVANCE_YEARS_UNIT')" in gui


def test_the_cost_maps_cover_the_advances_and_follow_the_engine_formula() -> None:
    """Every advance of the base game and the mod has an entry in both maps; the ladder's dearer gates are in."""
    from prosper_or_perish_constructor import advance_research_cost as arc

    vanilla = _vanilla().parent
    rows = {r.advance: r for r in arc.costs(vanilla, MOD_ROOT)}
    values = arc.defines(vanilla, MOD_ROOT)
    base, unique_base = values["BASE_RESEARCH_COST"], values["BASE_UNIQUE_RESEARCH_COST"]
    plain = rows["hospital_advance"]                      # first age, no research_cost of its own
    assert (plain.current, plain.past) == (base, base + values["PREVIOUS_AGE_REDUCTION"])
    gate = rows["written_alphabet"]                        # the ladder's REPLACE block carries its research_cost
    assert gate.research_cost > 2.0 and gate.current == base * (1 + gate.research_cost)
    charter = rows["kouroukan_fouga_advance"]              # a country advance: the small base, floor 1 once past
    assert charter.unique and charter.current == unique_base and charter.past == 1.0
    later = next(r for r in rows.values() if r.age_index == 2 and not r.unique and r.research_cost == 0)
    assert abs(later.current - base * (1 + 2 * values["AGE_RESEARCH_MODIFIER"])) < 1e-9
    text = (MOD_ROOT / arc.OUTPUT).read_text(encoding="utf-8-sig")
    assert text == arc.render(list(rows.values())), "run `uv run ppc advance-cost apply`"
    written = [r for r in rows.values() if not r.dlc_only]
    assert text.count(f"name = {arc.CURRENT_MAP} key = advance_type:") == len(written)
    assert text.count(f"name = {arc.PAST_MAP} key = advance_type:") == len(written)
    # the on_action reads both maps itself, so the game does not log them as set but never used
    assert f"has_global_variable_map = {arc.CURRENT_MAP}" in text and f"has_global_variable_map = {arc.PAST_MAP}" in text
    assert "set_global_variable" not in text
