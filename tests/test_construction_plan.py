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


# ---- Baseline rules (Jan 2026-11-08) ----

TRIGGERS = MOD / "in_game/common/scripted_triggers/pp_construction_plan.txt"
VALUES = MOD / "in_game/common/script_values/pp_construction_plan.txt"


def _effect(text: str, name: str) -> str:
    match = re.search(rf"^{name} = \{{\n(.*?)^\}}", text, re.MULTILINE | re.DOTALL)
    assert match, name
    return match.group(1)


def test_baseline_defaults() -> None:
    config = cp.load_config(PROJECT)
    assert config.access_threshold == 97
    assert (config.granary_capacity_months, config.granary_fill_pct) == (24, 85)
    assert (config.grange_surplus_pct, config.famine_months, config.yard_payback_years) == (5, 3, 10)
    assert config.granges == ("grange",) and config.yards == ("victualling_yard",)
    assert config.access_blacklist == ("staple_port_commercial_stagnation_modifier",)


def test_nothing_is_kept_between_passes() -> None:
    """Jan: no history. The baseline rules read the game as it stands; no counter variables, no watch effects."""
    for path in (EFFECTS, TRIGGERS, VALUES, SCRIPTED_GUIS):
        text = _read(path)
        for gone in ("pp_cplan_gw", "pp_cplan_fw", "pp_cplan_al", "pp_cplan_mm", "pp_cplan_mkt",
                     "pp_cplan_count_up", "pp_cplan_reset_watch", "_watch = yes"):
            assert gone not in text, f"{path.name}: {gone}"


def test_food_pass_order() -> None:
    """One food construction a province a month: famine Tavern, farm, kitchen, Tavern, Granary, Grange, Yard."""
    body = _effect(_read(EFFECTS), "pp_cplan_food_province")
    steps = ["# 1.", "# 2.", "# 3.", "# 4.", "# 5.", "# 6.", "# 7.", "# the state"]
    places = [body.index(step) for step in steps]
    assert places == sorted(places)
    part = {n: body[places[n - 1]:places[n]] for n in range(1, 8)}
    assert "pp_cplan_famine = yes" in part[1] and "pp_cplan_try_tavern_here" in part[1]
    assert "pp_cplan_hungry = yes" in part[2] and "pp_cplan_try_farm_here" in part[2]
    assert "order_by = pp_cplan_farm_best_roi" in part[2]
    assert "pp_cplan_hungry" not in part[3] and "pp_cplan_try_kitchen_here" in part[3]
    assert "pp_cplan_hungry = yes" in part[4] and "pp_cplan_try_tavern_here" in part[4]
    assert "pp_cplan_granary_due = yes" in part[5] and "pp_cplan_try_granary_here" in part[5]
    assert "pp_cplan_grange_due = yes" in part[6] and "pp_cplan_try_grange_here" in part[6]
    assert "pp_cplan_try_yard_here" in part[7]
    # Taverns only where the market holds victuals; every step after the first asks whether the province built already
    assert "pp_cplan_victuals_here = yes" in part[1] and "pp_cplan_victuals_here = yes" in part[4]
    for n in range(2, 8):
        assert "pp_cplan_may_try = yes" in part[n], n


def test_hunger_reads_a_normal_year() -> None:
    triggers = _read(TRIGGERS)
    assert "pp_cplan_food_in_a_year < pp_cplan_band_lo" in _effect(triggers, "pp_cplan_hungry")
    assert "pp_cplan_food_in_a_year < scope:pp_cplan_country.pp_cplan_famine_months" in _effect(triggers, "pp_cplan_famine")
    values = _read(VALUES)
    gain = _effect(values, "pp_cplan_normal_gain")
    assert "add = pp_cplan_harvest_food" in gain and "pp_cplan_spoil_rate" in gain
    assert "subtract = pp_cplan_harvest_food" in _effect(values, "pp_cplan_normal_consumption")
    granary = _effect(triggers, "pp_cplan_granary_due")
    for part in ("pp_cplan_capacity_months < scope:pp_cplan_country.pp_cplan_granary_cap",
                 "pp_cplan_fill_pct >= scope:pp_cplan_country.pp_cplan_granary_fill", "pp_cplan_normal_gain > 0"):
        assert part in granary
    assert "pp_cplan_normal_gain_pct >= scope:pp_cplan_country.pp_cplan_grange_surplus" in _effect(triggers, "pp_cplan_grange_due")


def test_harvest_blacklist_covers_every_harvest_modifier() -> None:
    rates = cp.harvest_rates(MOD)
    assert len(rates) >= 15
    names = re.findall(r"^(pp_harvest_\w+) = \{", _read(MOD / cp.HARVEST_MODIFIERS), re.MULTILINE)
    generated = _read(MOD / cp.VALUES)
    block = _effect(generated, "pp_cplan_harvest_rate")
    for name in names:
        assert f"has_location_modifier = {name} }}" in block, name
    # bad years make the peasants eat more, good years less
    assert rates["western_europe"]["abysmal"] > 0 > rates["western_europe"]["bountiful"]
    assert all(set(found) == set(cp.HARVEST_SEVERITIES) for found in rates.values()), rates


def test_logistics_reads_access_without_events() -> None:
    triggers = _read(TRIGGERS)
    wanted = _effect(triggers, "pp_cplan_logistics_wanted")
    assert "controller ?= owner" in wanted and "pp_cplan_access_normal < pp_cplan_access_line" in wanted
    block = _effect(_read(MOD / cp.VALUES), "pp_cplan_access_normal")
    assert "has_location_modifier = staple_port_commercial_stagnation_modifier } subtract = -0.25" in block


def test_farms_pick_the_fastest_payback() -> None:
    config = cp.load_config(PROJECT)
    generated = _read(MOD / cp.VALUES)
    effects = _read(MOD / cp.EFFECTS)
    picker = _effect(effects, "pp_cplan_try_farm_here")
    lines = re.findall(r"limit = \{ pp_cplan_farm_line_roi_(\w+) > var:pp_cplan_best \}", picker)
    assert lines and len(lines) == len(set(lines))
    for line in lines:
        block = _effect(generated, f"pp_cplan_farm_line_roi_{line}")
        assert "location_and_owner_can_build" in block and "pp_cplan_mode_" in block
        assert f"min = pp_cplan_farm_line_roi_{line}" in _effect(generated, "pp_cplan_farm_best_roi")
    # the estimate reads the market's prices and the location's output of the good a method makes
    est = _effect(generated, "pp_cplan_fm_wheat_farmstead_2_1")
    assert 'market.market_price(goods:wheat)' in est and "modifier:local_wheat_output_modifier" in est
    assert 'subtract = { value = "market.market_price(goods:tools)"' in est
    assert config.yards[0] in _effect(effects, "pp_cplan_try_yard_here")


def test_kitchen_successor_first() -> None:
    config = cp.load_config(PROJECT)
    assert config.kitchens[0] == "public_kitchen" and "cookshop" in config.kitchens
    kitchen = _effect(_read(MOD / cp.EFFECTS), "pp_cplan_try_kitchen_here")
    assert kitchen.index("public_kitchen") < kitchen.index("cookshop")


def test_hunger_rule_waits_only_for_food_makers() -> None:
    queued = _effect(_read(MOD / cp.TRIGGERS), "pp_cplan_food_queued")
    assert "building_type:tavern" in queued and "building_type:wheat_farm" in queued
    assert "building_type:cookshop" not in queued  # kitchens are built anyway, they must not hold farms back
    assert "building_type:granary" not in queued and "building_type:grange" not in queued


def test_new_settings_step_and_travel_in_profiles() -> None:
    guis = _read(SCRIPTED_GUIS)
    for flag, var in (("granary_cap", "pp_cplan_gcap"), ("granary_fill", "pp_cplan_gfill"),
                      ("grange_surplus", "pp_cplan_gsur"), ("famine", "pp_cplan_famine"), ("yard_payback", "pp_cplan_ypb")):
        assert f"flag:{flag} = {{ pp_cplan_step_var = {{ var = {var} " in guis, flag
        assert var in cp.PROFILE_NUMBERS
        assert f"MakeScopeFlag('{flag}')" in _read(GUI_FILES[0]), flag
    assert "flag:access_line = { pp_cplan_step_var = { var = pp_cplan_access current = pp_cplan_access_pct step = 1" in guis


def test_hunger_bucket_holds_every_staple_food_maker() -> None:
    """Farms, orchards, fisheries, herds and forest villages compete in one bucket by payback (Jan 2026-11-08)."""
    result = cp.apply(ROOT, PROJECT, MOD, vanilla_root(ROOT, PROJECT), write=False)
    buildings = {b for tiers in result.food_lines.values() for b in tiers}
    for name in ("wheat_farm", "fruit_orchard", "fishing_village", "ocean_fishery", "forest_village", "sheep_farms"):
        assert name in buildings, name
    assert "cookshop" not in buildings and "tavern" not in buildings
    assert result.food_lines["forest_village"][0] == "forest_village"


def test_improvements_cheap_and_much_first() -> None:
    """Jan 2026-11-08: where people fill the line of a location's capacity, the improvement with the most capacity
    per gold; the fullest locations first."""
    result = cp.apply(ROOT, PROJECT, MOD, vanilla_root(ROOT, PROJECT), write=False)
    assert {"land_clearance", "field_management", "irrigation_systems", "polders"} <= set(result.improvements)
    generated = _read(MOD / cp.VALUES)
    picker = _effect(_read(MOD / cp.EFFECTS), "pp_cplan_try_improve_here")
    for key in result.improvements:
        assert f"pp_cplan_imp_{key} > var:pp_cplan_best" in picker, key
        assert f"location_and_owner_can_build = {{ building_type = {key} }}" in picker, key
        value = _effect(generated, f"pp_cplan_imp_{key}")
        assert f"building_type:{key}.building_base_cost_in_gold" in value
    run = _effect(_read(EFFECTS), "pp_cplan_run")
    block = run[run.index("pp_cplan_improve_off"):run.index("pp_cplan_try_improve_here")]
    assert "location_population_percentage >= scope:pp_cplan_country.pp_cplan_improve_line" in block
    assert "order_by = pp_cplan_fill_here" in block
    assert cp.load_config(PROJECT).improve_fill_pct == 90
    assert "pp_cplan_improve_off" in cp.PROFILE_FLAGS and "pp_cplan_imp" in cp.PROFILE_NUMBERS
