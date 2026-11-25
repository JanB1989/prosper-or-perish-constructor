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


def test_the_tree_is_vanilla_plus_two_chips() -> None:
    tool = _tool()
    vanilla = tool._read(_vanilla() / tool.GUI / tool.TECH_VIEW)
    mod = tool._read(MOD_ROOT / tool.GUI / tool.TECH_VIEW)
    assert mod == tool.port_technology_view(vanilla), "run tools/port_vanilla_gui.py"
    added = [line.strip() for line in mod.splitlines() if tool.ADVANCE_TIME_MARK in line]
    assert added == [f"using = pp_advance_time_chip_round {tool.ADVANCE_TIME_MARK}",
                     f"using = pp_advance_time_chip {tool.ADVANCE_TIME_MARK}"]
    # nothing else differs from vanilla
    stripped = "\n".join(line for line in mod.splitlines() if tool.ADVANCE_TIME_MARK not in line)
    assert re.sub(r"\n{2,}", "\n", stripped) == re.sub(r"\n{2,}", "\n", vanilla.rstrip("\n"))


def test_each_chip_closes_its_own_node() -> None:
    """The chip is the last child of the node whose `visible` names the form, so it is drawn on top of the node."""
    tool = _tool()
    mod = tool._read(MOD_ROOT / tool.GUI / tool.TECH_VIEW)
    for visible, template in tool._ADVANCE_NODE_FORMS:
        at = mod.index(visible)
        end = tool._block_end(mod, mod.rfind("{", 0, at))
        tail = mod[:end].rstrip("}").rstrip()
        assert tail.endswith(f"using = {template} {tool.ADVANCE_TIME_MARK}"), template


def test_the_chip_templates_and_their_text() -> None:
    tool = _tool()
    gui = tool._read(MOD_ROOT / tool.GUI / tool.ADVANCE_TIME_GUI)
    assert gui == tool.advance_time_gui(), "run tools/port_vanilla_gui.py"
    for template in ("pp_advance_time_body", "pp_advance_time_chip", "pp_advance_time_chip_round"):
        assert gui.count(f"template {template} {{") == 1
    assert gui.count("{") == gui.count("}")
    years = tool.advance_years()
    assert "'pp_advance_cost'" in years and "'pp_advance_cost_past'" in years and "HasResearchCostDiscount" in years
    assert "research_speed" in years and "research_speed_modifier" in years
    # three colour bands that cover every duration exactly once
    assert gui.count('visible = "[') == 5   # three colour bands, and each chip only where the cost is known
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
