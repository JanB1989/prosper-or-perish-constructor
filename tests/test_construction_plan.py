"""Construction Plan: player-only construction rules (src/prosper_or_perish_constructor/construction_plan.py,
mod/pp/.../pp_construction_plan*)."""

from __future__ import annotations

import re
from pathlib import Path

from prosper_or_perish_constructor import construction_plan as cp
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
MOD = ROOT / "mod" / "pp"
GUI_FILES = (MOD / "in_game/gui/pp_construction_plan.gui", MOD / cp.GUI, MOD / cp.HERE_GUI)
LOC = MOD / "main_menu/localization/english/pp_construction_plan_l_english.yml"
SCRIPTED_GUIS = MOD / "in_game/common/scripted_guis/pp_construction_plan.txt"
ON_ACTION = MOD / "in_game/common/on_action/pp_construction_plan.txt"
EFFECTS = MOD / "in_game/common/scripted_effects/pp_construction_plan.txt"
LOCATION_WINDOW = MOD / "in_game/gui/location_window.gui"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _defined_keys(folder: Path) -> set[str]:
    keys: set[str] = set()
    for path in folder.glob("*.txt"):
        for match in re.finditer(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{", _read(path), re.MULTILINE):
            keys.add(match.group(1))
    return keys


def test_built_mod_is_in_step() -> None:
    result = cp.apply(ROOT, PROJECT, MOD, vanilla_root(ROOT, PROJECT), write=False)
    assert result.files_changed == 0, "run ppc finalize"
    assert result.missing == [], f"buildings the game does not know: {result.missing}"
    assert len(result.goods) > 60
    assert "iron_mine" in result.producers["iron"]
    assert result.farm_lines["wheat"][0] == "wheat_farm"


def test_focus_ids_match_the_panel() -> None:
    """The panel's focus labels are written by hand for these ids."""
    ids = cp.focus_ids(cp.load_config(PROJECT))
    assert ids == {"standard": 1, "breadbasket": 2, "market_town": 3, "workshop": 4, "hands_off": 5, "custom": 6}
    gui = _read(GUI_FILES[0])
    loc = _read(LOC)
    for name, number in ids.items():
        key = f"PP_CPLAN_FOCUS_{name.upper()}"
        assert f"'(CFixedPoint){number}')]\" text = \"{key}\"" in gui
        assert f"  {key}:" in loc


def test_panel_references_exist() -> None:
    guis = _read(SCRIPTED_GUIS) + "\n"
    script_values = _defined_keys(MOD / "in_game/common/script_values")
    loc = _read(LOC)
    loc_keys = set(re.findall(r"^  ([A-Z0-9_]+):", loc, re.MULTILINE))
    cog = re.search(r"# PP: Construction Plan.*?BasicFunctionalTooltip", _read(LOCATION_WINDOW), re.DOTALL)
    assert cog, "the location window lost the Construction Plan cog"
    text = "".join(_read(path) for path in GUI_FILES) + loc + cog.group(0)
    for name in set(re.findall(r"GetScriptedGui\('([a-z0-9_]+)'\)", text)):
        assert re.search(rf"^{name} = \{{", guis, re.MULTILINE), f"scripted GUI {name} missing"
    for name in set(re.findall(r"ScriptValue\('([a-z0-9_]+)'\)", text)):
        assert name in script_values, f"script value {name} missing"
    for key in set(re.findall(r"\"(PP_CPLAN_[A-Z0-9_]+)\"", text)):
        assert key in loc_keys, f"text {key} missing"


def test_slot_counts_match_the_hand_written_parts() -> None:
    """The rule, template and profile slots of [construction_plan] are also spelled out by hand in the engine and panel."""
    config = cp.load_config(PROJECT)
    effects = _read(EFFECTS)
    rules = re.search(r"^pp_cplan_location_rules = \{(.*?)^\}", effects, re.MULTILINE | re.DOTALL).group(1)
    assert re.findall(r"pp_cplan_rule = \{ n = (\d) \}", rules) == [str(n) for n in range(1, config.rule_slots + 1)]
    add = re.search(r"^pp_cplan_add_rule = \{(.*?)^\}", effects, re.MULTILINE | re.DOTALL).group(1)
    assert sorted(set(re.findall(r"pp_cplan_fill_rule = \{ n = (\d) \}", add))) == [str(n) for n in range(1, config.rule_slots + 1)]
    gui = _read(GUI_FILES[0])
    assert re.findall(r"pp_cplan_rule_row_(\d) = \{\}", gui) == [str(n) for n in range(1, config.rule_slots + 1)]
    profiles = sorted(set(re.findall(r"MakeScopeFlag\('p(\d)'\)", gui)))
    assert profiles == [str(k) for k in range(1, config.profile_slots + 1)]
    values = _read(MOD / "in_game/common/script_values/pp_construction_plan.txt")
    for n in range(1, config.rule_slots + 1):
        assert f"pp_cplan_r{n}_est_n = {{" in values


def test_every_condition_has_a_label() -> None:
    config = cp.load_config(PROJECT)
    loc = _read(LOC)
    assert config.metrics
    for metric in config.metrics:
        assert (metric.value is None) != (metric.trigger is None), metric.key
        assert f"  PP_CPLAN_M_{metric.key.upper()}:" in loc, metric.key


def test_build_cost_data() -> None:
    """The cost formula's inputs per building (calibrated in game 2026-11-06 on 158 constructions)."""
    result = cp.apply(ROOT, PROJECT, MOD, vanilla_root(ROOT, PROJECT), write=False)
    costs, demands = result.buildings, result.demands
    assert costs["castle"].category == "fort"
    assert costs["stockade"].category == "fort"
    assert costs["dock"].category == "port"
    assert costs["cookshop"].ipl == 0.1 and costs["cookshop"].category == "std"
    # a building that names no construction demand uses the game's default (masonry and lumber, 0.1 each)
    assert costs["winery"].demand == cp.DEFAULT_DEMAND
    assert demands[cp.DEFAULT_DEMAND] == {"masonry": 0.1, "lumber": 0.1}
    assert demands["granary_construction"] == {"lumber": 0.5, "masonry": 0.5}
    values = _read(MOD / cp.VALUES)
    low, high = cp.price_impact_bounds(MOD, vanilla_root(ROOT, PROJECT))
    assert (low, high) == (0.5, 2.5)
    block = re.search(r"^pp_cplan_cd_granary_construction = \{(.*?)^\}", values, re.MULTILINE | re.DOTALL).group(1)
    assert "min = 0.5 max = 2.5 multiply = 0.5" in block and "divide = 1" in block
    # every building the goods pass can expand has its own cost data in the generated effects
    effects = _read(MOD / cp.EFFECTS)
    for names in result.producers.values():
        for name in names:
            assert f"building_type:{name} = {{ save_scope_as = pp_cplan_btype }}" in effects, name


def _plan_script_files() -> list[Path]:
    common = MOD / "in_game/common"
    return sorted(common.glob("*/pp_construction_plan*.txt"))


def test_no_not_with_several_conditions() -> None:
    """NOT = { a b } means neither a nor b, not "not both": the rule's can-build guard written that way let the plan
    queue Cookshops outside province capitals (in game 2026-11-06; construct_building itself checks no allow)."""
    for path in _plan_script_files():
        text = re.sub(r"#[^\n]*", "", _read(path))
        for match in re.finditer(r"\bNOT = \{", text):
            depth, index = 1, match.end()
            while depth:
                depth += {"{": 1, "}": -1}.get(text[index], 0)
                index += 1
            body = text[match.end():index - 1]
            top, level = 0, 0
            for token in re.finditer(r"\{|\}|[A-Za-z_:.\"()0-9?]+\s*(?:[<>=!?]+)", body):
                if token.group(0) == "{":
                    level += 1
                elif token.group(0) == "}":
                    level -= 1
                elif level == 0:
                    top += 1
            assert top <= 1, f"{path.name}: NOT with {top} conditions: {body.strip()[:80]}"


def test_constructions_check_market_goods_and_queue() -> None:
    """Every can-build check of the generated pickers also asks for the construction goods in the market (else the
    construction stalls) and for no level of the building under construction here (else levels pile up)."""
    effects = _read(MOD / cp.EFFECTS)
    triggers = _read(MOD / cp.TRIGGERS)
    checks = re.findall(r"location_and_owner_can_build = \{ building_type = (\w+) \}([^\n]*)", effects)
    assert checks
    for name, rest in checks:
        demand = re.search(r"pp_cplan_goods_here_(\w+) = yes", rest)
        assert demand, name
        assert f"pp_cplan_goods_here_{demand.group(1)} = {{" in triggers, demand.group(1)
        assert f"building_type = building_type:{name} building_levels_under_construction > 0" in rest, name


def test_expand_checks_can_build_and_payback() -> None:
    effects = _read(MOD / cp.EFFECTS)
    blocks = re.findall(
        r"limit = \{\n\t\t\tscope:pp_cplan_country = \{ NOT = \{ has_variable = pp_cplan_hit \} \}\n"
        r"\t\t\tany_buildings_in_location = \{ building_type = building_type:(\w+) [^\n]*\n"
        r"\t\t\tlocation_and_owner_can_build = \{ building_type = (\w+) \}[^\n]*\n\t\t\}\n"
        r"\t\tbuilding_type:(\w+) = \{ save_scope_as = pp_cplan_btype \}\n[^\n]*\n"
        r"\t\tif = \{\n\t\t\tlimit = \{ pp_cplan_est_payback_years <= scope:pp_cplan_country.pp_cplan_payback_line \}",
        effects,
    )
    assert len(blocks) == sum(len(names) for names in cp.apply(
        ROOT, PROJECT, MOD, vanilla_root(ROOT, PROJECT), write=False).producers.values())
    for standing, checked, scoped in blocks:
        assert standing == checked == scoped


def _widget_tree(text: str) -> list[tuple[str, str | None]]:
    """(widget, parent widget) for every block, `item` blocks passing their parent through."""
    pairs: list[tuple[str, str | None]] = []
    stack: list[str | None] = []
    for match in re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{|\}", re.sub(r"#[^\n]*", "", text)):
        if match.group(0) == "}":
            if stack:
                stack.pop()
            continue
        name = match.group(1)
        parent = stack[-1] if stack else None
        if name == "item":
            stack.append(parent)
            continue
        pairs.append((name, parent))
        stack.append(name)
    return pairs


def test_no_box_directly_inside_a_container() -> None:
    """EU5 refuses an hbox/vbox as a direct child of a (flow)container; a hot reload with one crashed the game."""
    for path in GUI_FILES:
        for name, parent in _widget_tree(_read(path)):
            if parent in {"flowcontainer", "container", "dynamicgridbox", "fixedgridbox"}:
                assert name not in {"hbox", "vbox"}, f"{path.name}: {name} directly inside {parent}"


def test_raw_text_never_replaced_other_properties() -> None:
    for path in GUI_FILES:
        assert "conraw_text" not in _read(path)


def test_only_human_countries_run_the_plan() -> None:
    text = _read(ON_ACTION)
    assert "is_ai = no" in text
    assert "has_variable = pp_cplan_on" in text


def test_effects_use_the_vanilla_can_build_check() -> None:
    """Every construction the plan starts is guarded by the location and owner can-build check."""
    effects = _read(MOD / cp.EFFECTS)
    blocks = re.findall(r"limit = \{([^\n]*)\}\n\t*pp_cplan_construct(?:_food)? = \{ type = (\w+)", effects)
    assert blocks
    for limit, building in blocks:
        if "pp_cplan_pick" in limit:
            continue  # the farm picker checked the candidate before it picked it
        assert f"location_and_owner_can_build = {{ building_type = {building} }}" in limit, building
