"""Construction Plan: player-only construction rules (src/prosper_or_perish_constructor/construction_plan.py,
mod/pp/.../pp_construction_plan*)."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from prosper_or_perish_constructor import construction_plan as cp
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
MOD = ROOT / "mod" / "pp"
WINDOW = MOD / "in_game/gui/pp_construction_plan.gui"
PROFILES_GUI = MOD / "in_game/gui/pp_location_profiles.gui"
LOC = MOD / "main_menu/localization/english/pp_construction_plan_l_english.yml"
SCRIPTED_GUIS = MOD / "in_game/common/scripted_guis/pp_construction_plan.txt"
ON_ACTION = MOD / "in_game/common/on_action/pp_construction_plan.txt"
EFFECTS = MOD / "in_game/common/scripted_effects/pp_construction_plan.txt"
TRIGGERS = MOD / "in_game/common/scripted_triggers/pp_construction_plan.txt"
VALUES = MOD / "in_game/common/script_values/pp_construction_plan.txt"
LOCATION_WINDOW = MOD / "in_game/gui/location_window.gui"
PROFILE_EFFECTS = MOD / "in_game/common/scripted_effects/pp_location_profiles.txt"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _defined_keys(folder: Path) -> set[str]:
    keys: set[str] = set()
    for path in folder.glob("*.txt"):
        for match in re.finditer(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{", _read(path), re.MULTILINE):
            keys.add(match.group(1))
    return keys


def _effect(text: str, name: str) -> str:
    match = re.search(rf"^{name} = \{{\n(.*?)^\}}", text, re.MULTILINE | re.DOTALL)
    assert match, name
    return match.group(1)


def _plan_script_files() -> list[Path]:
    common = MOD / "in_game/common"
    return sorted(common.glob("*/pp_construction_plan*.txt"))


@lru_cache(maxsize=1)
def _result() -> cp.Result:
    return cp.apply(ROOT, PROJECT, MOD, vanilla_root(ROOT, PROJECT), write=False)


def test_built_mod_is_in_step() -> None:
    result = _result()
    assert result.files_changed == 0, "run ppc finalize"
    assert result.missing == [], f"buildings the game does not know: {result.missing}"
    assert len(result.businesses) > 150
    assert result.businesses["iron_mine"] == "iron" and result.businesses["wheat_farm"] == "wheat"
    assert result.farm_lines["wheat"][0] == "wheat_farm"


# ---- The window: two tabs (Jan 2026-11-09) ----


def test_window_references_exist() -> None:
    guis = _read(SCRIPTED_GUIS) + "\n"
    script_values = _defined_keys(MOD / "in_game/common/script_values")
    loc = _read(LOC)
    loc_keys = set(re.findall(r"^  ([A-Z0-9_]+):", loc, re.MULTILINE))
    text = _read(WINDOW) + loc
    for name in set(re.findall(r"GetScriptedGui\('([a-z0-9_]+)'\)", text)):
        assert re.search(rf"^{name} = \{{", guis, re.MULTILINE), f"scripted GUI {name} missing"
    for name in set(re.findall(r"ScriptValue\('([a-z0-9_]+)'\)", text)):
        assert name in script_values, f"script value {name} missing"
    for key in set(re.findall(r"\"(PP_CPLAN_[A-Z0-9_]+)\"", text)):
        assert key in loc_keys, f"text {key} missing"
    # the second tab is the profile editor, a type of the profiles' GUI file
    assert "pp_lprof_editor_tab = {}" in _read(WINDOW)
    assert re.search(r"type pp_lprof_editor_tab = vbox", _read(PROFILES_GUI))


def test_three_tabs_and_nothing_else() -> None:
    """Jan 2026-11-09: Global settings and Location profiles; 2026-11-10: Towns and Buildings, the settings of the
    rule group of that name (type pp_cplan_country_tab, construction_plan_country.py), hosted like the profile editor.
    The Food, Goods, Logistics, Locations and Here tabs, the monthly construction limit, the presets, the goods modes,
    the per-location own rules and modes, the logistics overrides and the province focus are gone from the window, the
    scripts and the texts."""
    window = _read(WINDOW)
    tabs = re.findall(r"button_main_tab_alt = \{.*?text = \"(PP_CPLAN_TAB_\w+)\"", window, re.DOTALL)
    assert tabs == ["PP_CPLAN_TAB_PLAN", "PP_CPLAN_TAB_PROFILES", "PP_CPLAN_TAB_COUNTRY"]
    # every tab's page shows for exactly its own value of pp_cplan_tab; the first for anything else
    profiles, country = (f"GetVariableSystem.HasValue('pp_cplan_tab', '{tab}')" for tab in ("profiles", "country"))
    first = f"[Not(Or({profiles}, {country}))]"
    assert window.count(f'down = "{first}"') == 1 and window.count(f'visible = "{first}"') == 1
    for shown, page in ((profiles, "pp_lprof_editor_tab = {}"), (country, "pp_cplan_country_tab = {}")):
        assert window.count(f'down = "[{shown}]"') == 1
        body = window[window.index(f'visible = "[{shown}]"'):]
        assert page in body[:body.index("\n\t\t\t\t}")], page
    assert window.count("pp_cplan_country_tab = {}") == 1
    files = [WINDOW, LOC, *_plan_script_files(), PROFILE_EFFECTS, LOCATION_WINDOW]
    gone = re.compile(
        r"pp_cplan_(?:max|preset|g_|mode|own|rule|r\d_|logi(?!stics)|focus|status|sel\b|select|cands|goods_run|keep|"
        r"auto_|template|band_)|PP_CPLAN_(?:TAB_HERE|TAB_GOODS|TAB_FOOD|TAB_LOGISTICS|TAB_LOCATIONS|PRESET|MAX|"
        r"LOCATION_COG|MODE_|RULE_|FOCUS)")
    for path in files:
        found = gone.search(_read(path))
        assert not found, f"{path.name}: {found.group(0) if found else ''}"
    assert not (MOD / "in_game/gui/pp_construction_plan_goods.gui").exists()
    assert not (MOD / "in_game/gui/pp_construction_plan_here.gui").exists()
    assert "Construction Plan, this location's own rules" not in _read(LOCATION_WINDOW)
    assert not hasattr(cp, "add_location_cog")


def test_lines_step_as_jan_asked() -> None:
    """Gold reserve in gold (default 1,000; 100 a click, 1,000 a right-click); improvements in steps of ten percent up
    to three times the capacity; businesses in whole years; logistics in steps of one percent."""
    config = cp.load_config(PROJECT)
    assert config.reserve_gold == 1000 and config.improve_fill_pct == 90 and config.business_years == 10
    guis = _read(SCRIPTED_GUIS)
    assert "flag:reserve = { pp_cplan_step_var = { var = pp_cplan_reserve current = pp_cplan_reserve_gold step = 100 min = 100" in guis
    assert "flag:reserve_big = { pp_cplan_step_var = { var = pp_cplan_reserve current = pp_cplan_reserve_gold step = 1000 min = 100" in guis
    assert "flag:improve_line = { pp_cplan_step_var = { var = pp_cplan_imp current = pp_cplan_improve_pct step = 10 min = 150 max = 400 }" in guis
    assert "flag:business_line = { pp_cplan_step_var = { var = pp_cplan_biz current = pp_cplan_business_years step = 1 min = 101 max = 150 }" in guis
    assert "flag:access_line = { pp_cplan_step_var = { var = pp_cplan_access current = pp_cplan_access_pct step = 1" in guis
    window = _read(WINDOW)
    assert window.count("MakeScopeFlag('reserve_big')") == 2 and window.count("onrightclick") == 2
    values = _read(MOD / cp.VALUES)
    assert "pp_cplan_reserve_gold = {\n\tvalue = 1000\n" in values


def test_budget_is_the_gold_above_the_reserve() -> None:
    """No monthly count any more: each pass may spend the gold above the reserve; every rule group gets its weight over
    the sum of the weights (Jan 2026-11-09: a part per group, every bar full = equal parts, an empty bar = off), a part
    left unused passes on; no construction takes the treasury below the reserve."""
    run = _effect(_read(EFFECTS), "pp_cplan_run")
    assert "set_variable = { name = pp_cplan_pot value = { value = pp_cplan_free_gold min = 0 add = 100 } }" in run
    values = _read(VALUES)
    assert "subtract = pp_cplan_reserve_gold" in _effect(values, "pp_cplan_free_gold")
    generated = _read(MOD / cp.VALUES)
    total = _effect(generated, "pp_cplan_w_total")
    # two groups count only while they have something to do, so an idle group holds no gold back: the locations'
    # while a location has a profile or a mark, Towns and Buildings while something is ticked on its tab
    assert cp.COUNTED_WEIGHTS == {"profiles": "pp_cplan_profiles_cw", "country": "pp_cplan_country_cw"}
    assert "multiply = pp_lprof_group_n" in _effect(generated, "pp_cplan_profiles_cw")
    assert ("limit = { pp_cplan_country_active > 0 }\n\t\tvalue = pp_cplan_country_w"
            in _effect(generated, "pp_cplan_country_cw"))
    country_values = _read(MOD / "in_game/common/script_values/pp_construction_plan_country.txt")
    assert re.search(r"^pp_cplan_country_active = \{", country_values, re.MULTILINE)
    assert re.search(r"^pp_lprof_group_n = \{", _read(MOD / "in_game/common/script_values/pp_location_profiles_generated.txt"), re.MULTILINE)
    for group in cp.GROUPS:
        share = _effect(generated, f"pp_cplan_share_{group}")
        weight = cp.counted_weight(group)
        assert weight == cp.COUNTED_WEIGHTS.get(group, f"pp_cplan_{group}_w")
        assert "value = pp_cplan_pot_n" in share and f"multiply = {weight}" in share and "divide = pp_cplan_w_total" in share
        part = _effect(generated, f"pp_cplan_part_{group}")
        assert f"value = {weight}\n\t\tmultiply = 100\n\t\tdivide = pp_cplan_w_total" in part  # the shown % follows
        assert total.count(f"add = {weight}\n") == 1
        if group in cp.COUNTED_WEIGHTS:
            assert f"add = pp_cplan_{group}_w\n" not in total
        if group not in ("profiles", "country"):  # those two start themselves (pp_lprof_run, pp_cplan_group_country)
            body = _effect(_read(EFFECTS), f"pp_cplan_group_{group}")
            assert (f"limit = {{ pp_cplan_{group}_w > 0 }}\n\t\tpp_cplan_group_start = {{ why = {cp.GROUP_WHY[group]} "
                    f"add = pp_cplan_share_{group} }}") in body
    config = cp.load_config(PROJECT)
    assert dict(config.weights) == {group: 5 for group in cp.GROUPS}
    triggers = _read(TRIGGERS)
    budget = _effect(triggers, "pp_cplan_budget_left")
    assert "pp_cplan_spent_n < pp_cplan_cap_n" in budget and "pp_cplan_free_gold > 0" in budget
    assert "pp_cplan_est_cost <= scope:pp_cplan_country.pp_cplan_free_gold" in _effect(triggers, "pp_cplan_affordable")
    start = _effect(_read(EFFECTS), "pp_cplan_group_start")
    assert "change_variable = { name = pp_cplan_cap add = $add$ }" in start
    # the gold is checked by the construction itself, so what the gold does not reach is counted (the detail panes)
    scoped = _effect(_read(EFFECTS), "pp_cplan_construct_scoped")
    assert (scoped.index("pp_cplan_btype_data = yes") < scoped.index("pp_cplan_budget_left = yes")
            < scoped.index("pp_cplan_affordable = yes") < scoped.index("pp_cplan_construct_now")
            < scoped.index("pp_cplan_note_wait"))


def test_weight_bars() -> None:
    """One bar per rule group: - and +, ten steps that set the weight when clicked, the part in %; 0..10."""
    gui = _read(MOD / cp.WEIGHT_GUI)
    window = _read(WINDOW)
    effects = _read(EFFECTS)
    for group in cp.GROUPS:
        bar = re.search(rf"type pp_cplan_weight_bar_{group} = hbox \{{(.*?)\n\t\}}\n", gui, re.DOTALL).group(1)
        for n in range(1, cp.WEIGHT_STEPS + 1):
            assert f"AddScope('pp_key', MakeScopeFlag('{group}')).AddScope('pp_n', MakeScopeFlag('w{n}'))" in bar, (group, n)
        assert "MakeScopeFlag('down')" in bar and "MakeScopeFlag('up')" in bar
        assert f"ScriptValue('pp_cplan_{group}_w')" in bar and f"ScriptValue('pp_cplan_part_{group}')" in bar
        assert f"pp_cplan_weight_bar_{group} = {{}}" in window, group
        assert f"flag:{group} = {{ pp_cplan_set_weight = {{ var = pp_cplan_w_{group} current = pp_cplan_{group}_w }} }}" in _read(SCRIPTED_GUIS)
    setter = _effect(effects, "pp_cplan_set_weight")
    for n in range(1, cp.WEIGHT_STEPS + 1):
        assert f"flag:w{n} = {{ set_variable = {{ name = $var$ value = {100 + n} }} }}" in setter
    assert "step = 1 min = 100 max = 110" in setter
    assert "toggle_module" not in window + _read(SCRIPTED_GUIS)


def test_last_month_list_names_every_entry() -> None:
    """Nothing shows blank: an entry is its building types, or, for a town or city upgrade of the Towns and Buildings
    group (no building: code 7 with kind 2, an empty list of types), the upgrade's own name; then the location and the
    rule group in brackets, one label per group, the ones that do not apply taking no room."""
    window = _read(WINDOW)
    last = window[window.index('text = "PP_CPLAN_LAST"'):window.index("# the rule groups' detail panes")]
    assert "ignoreinvisible = yes" in last
    assert (last.index("GetList('pp_cplan_log_types')") < last.index("pp_cplan_rank_upgrade = {}")
            < last.index('text = "PP_CPLAN_IN_LOCATION"'))
    for group, why in cp.GROUP_WHY.items():
        shown = f"visible = \"[EqualTo_CFixedPoint(Scope.ScriptValue('pp_cplan_why_n'), '(CFixedPoint){why - 100}')]\""
        assert last.count(shown) == 1, group
    upgrade = window[window.index("type pp_cplan_rank_upgrade = text_single"):window.index("# ---- Opener")]
    assert ("And(EqualTo_CFixedPoint(Scope.ScriptValue('pp_cplan_why_n'), '(CFixedPoint)7'), "
            "EqualTo_CFixedPoint(Scope.ScriptValue('pp_cplan_log_step_n'), '(CFixedPoint)2'))") in upgrade
    assert 'text = "PP_CPLAN_RANK_UPGRADE"' in upgrade
    loc = _read(LOC)
    assert re.search(r"^  PP_CPLAN_RANK_UPGRADE: \".*\[location_rank\|e\].*\"$", loc, re.MULTILINE)
    # the player's names of the two groups whose key differs from their name
    assert '  PP_CPLAN_PROFILES_RULE: "Locations"\n' in loc and '  PP_CPLAN_COUNTRY_RULE: "Towns and Buildings"\n' in loc
    assert '  PP_CPLAN_TAB_PROFILES: "Location Profiles"\n' in loc and '  PP_CPLAN_TAB_COUNTRY: "Towns and Buildings"\n' in loc
    # test runs: a marker line per construction code
    for why in cp.GROUP_WHY.values():
        assert re.search(rf"^  PP_CPLAN_TLOG_{why}: \"PPCPLAN;B;\w+\"$", loc, re.MULTILINE), why


def test_businesses_and_profiles_need_workers() -> None:
    """Jan 2026-11-09: no business where nobody can work in it. A level finds its workers in the idle peasants the
    buildings there do not already need (they are promoted into any class) or in idle pops of its own class."""
    result = _result()
    assert result.staff["iron_mine"] == ("laborers", 0.8)
    assert all(size > 0 for _, size in result.staff.values())
    # a size given through a script value is read as its number
    numbers = cp.script_value_numbers(MOD, vanilla_root(ROOT, PROJECT))
    assert numbers["manpower_employment"] > 0
    pick = _effect(_read(MOD / cp.EFFECTS), "pp_cplan_business_pick")
    assert "save_temporary_scope_value_as = { name = pp_cplan_free_peasants value = pp_cplan_free_peasants_here }" in pick
    for name in result.businesses:
        if name in result.staff:
            pop, size = result.staff[name]
            assert f"pp_cplan_staff = {{ type = {pop} size = {cp._num(size)} }}" in pick, name
    staff = _effect(_read(TRIGGERS), "pp_cplan_staff")
    assert "scope:pp_cplan_free_peasants >= $size$" in staff
    assert "pp_cplan_idle_$type$ >= $size$" in staff
    free = _effect(_read(VALUES), "pp_cplan_free_peasants_here")
    assert '"unemployed_pops_of_pop_type_in_location(pop_type:peasants)"' in free
    assert "value = building_employment_size_amount" in free and "subtract = building_employed_amount" in free


def test_worker_check_names_every_pop_type_outside_quotes() -> None:
    """In game 2026-11-10: with the pop type passed into the quoted call ("unemployed_pops_of_pop_type_in_location(
    pop_type:$type$)") the trigger logged a script error on every check, about 2,000 lines a session. The idle pops are
    read through one value per pop type with the type written out (as vanilla writes the call); no plan script puts
    an argument inside quotes."""
    result = _result()
    assert {"peasants", "laborers", "burghers"} <= set(result.pop_types)
    assert {pop for pop, _ in result.staff.values()} <= set(result.pop_types)
    values = _read(MOD / cp.VALUES)
    for pop in result.pop_types:
        body = re.search(rf"^pp_cplan_idle_{pop} = \{{ value = (.*?) \}}$", values, re.MULTILINE)
        assert body, pop
        # the peasants' own count is the check's first line (the idle peasants less the open jobs)
        expected = "0" if pop == "peasants" else f'"unemployed_pops_of_pop_type_in_location(pop_type:{pop})"'
        assert body.group(1) == expected, pop
    for path in _plan_script_files():
        code = re.sub(r"#[^\n]*", "", _read(path))
        found = re.search(r"\"[^\"\n]*\$\w+\$[^\"\n]*\"", code)
        assert not found, f"{path.name}: an argument inside quotes: {found.group(0) if found else ''}"


def test_groups_take_turns_by_month() -> None:
    """With little gold the group that went first took it every month (AI run 2026-11-09): the order turns with the
    game's month, every month has an order, every order is the window's order turned, and every group goes first
    equally often over the year."""
    run = _effect(_read(EFFECTS), "pp_cplan_run")
    blocks = re.findall(r"(?:if|else_if|else) = \{\n(?:\t\tlimit = \{ OR = \{ ([^}]*) \} \}\n)?((?:\t\tpp_cplan_group_\w+ = yes\n)+)", run)
    assert len(blocks) == len(cp.GROUPS) == 6
    months: dict[int, str] = {}
    for limit, body in blocks:
        order = re.findall(r"pp_cplan_group_(\w+) = yes", body)
        turn = cp.GROUPS.index(order[0])
        assert tuple(order) == cp.GROUPS[turn:] + cp.GROUPS[:turn], order
        named = [int(month) for month in re.findall(r"current_month = (\d+)", limit)]
        assert bool(named) == bool(limit)
        for month in named or sorted(set(range(1, 13)) - set(months)):  # the else block: the months left
            assert month not in months, month
            months[month] = order[0]
    assert blocks[-1][0] == "", "the last block is the else"
    assert set(months) == set(range(1, 13))
    firsts = {group: sum(1 for first in months.values() if first == group) for group in cp.GROUPS}
    assert set(firsts.values()) == {12 // len(cp.GROUPS)}, firsts
    # every group runs exactly once a pass, and the rights of Towns and Buildings (no gold) after all of them
    for group in cp.GROUPS:
        assert run.count(f"pp_cplan_group_{group} = yes") == len(blocks), group
    assert run.count("pp_cplan_country_rights = yes") == 1
    # the never-run branch declares the flags of every tab's buttons
    never = run[run.index("limit = { always = no }"):]
    for declare in ("pp_cplan_declare_flags", "pp_cplan_country_declare", "pp_lprof_declare_flags"):
        assert f"{declare} = yes" in never, declare
    assert run.rindex("pp_cplan_group_business = yes") < run.index("pp_cplan_country_rights = yes") < run.index("pp_cplan_history_push = yes")


# ---- Businesses (Jan 2026-11-09) ----


def test_business_types_leave_the_other_rules_their_buildings() -> None:
    result = _result()
    config = cp.load_config(PROJECT)
    own = set(config.kitchens) | set(config.taverns) | set(config.granaries) | set(config.granges) | set(config.yards)
    own |= set(config.logistics_order) | set(result.improvements)
    assert not own & set(result.businesses)
    assert not set(result.businesses.values()) & config.hidden_goods
    # farms are businesses too: the food rule builds them when a province is short, the business rule when they pay
    assert {"wheat_farm", "iron_mine", "lumber_mill"} <= set(result.businesses)


def test_business_pick_checks_every_candidate() -> None:
    result = _result()
    effects = _read(MOD / cp.EFFECTS)
    pick = _effect(effects, "pp_cplan_business_pick")
    types = _effect(effects, "pp_cplan_business_types")
    clear = _effect(effects, "pp_cplan_business_types_clear")
    assert pick.startswith("\tpp_cplan_business_harvest = yes\n")
    assert "set_variable = { name = pp_cplan_bz_roi value = scope:pp_cplan_country.pp_cplan_business_min_roi }" in pick
    for name, good in result.businesses.items():
        block = re.search(rf"has_variable = pp_cplan_bz_{name} \}}\n(.*?)set_variable = {{ name = pp_cplan_bz_pick value = building_type:{name} }}",
                          pick, re.DOTALL)
        assert block, name
        body = block.group(1)
        assert f"can_build_building = building_type:{name}\n" in body, name
        assert f"NOT = {{ pp_lprof_has_good = {{ g = {good} }} }}" in body, name
        assert re.search(r"pp_cplan_goods_here_\w+ = yes", body), name
        assert f"building_type = building_type:{name} building_level > 0 is_opened = no" in body, name
        assert f"building_type:{name} = {{ save_scope_as = pp_cplan_btype }}" in body, name
        assert f"value = pp_cplan_bz_roi_{name} }}" in body and "limit = { scope:pp_cplan_r > var:pp_cplan_bz_roi }" in body, name
        assert f"limit = {{ can_build_building = building_type:{name} }} set_variable = {{ name = pp_cplan_bz_{name} value = yes }}" in types
        assert f"remove_variable = pp_cplan_bz_{name}\n" in clear
    # a profile's building category stays the profile's (trade buildings are businesses and a profile category)
    assert "NOT = { pp_lprof_has_category = { c = trade_category } }" in pick


def test_business_estimate_takes_this_years_harvest_out() -> None:
    """The same estimate for a new building and one more level: each slot's best method at the market's prices and the
    location's output without this year's Variable Harvest, x 12 over the level's build cost (the engine's formula)."""
    values = _read(MOD / cp.VALUES)
    roi = _effect(values, "pp_cplan_bz_roi_wheat_farm")
    assert "value = pp_cplan_bz_est_wheat_farm" in roi and "multiply = 1200" in roi
    assert "divide = { value = pp_cplan_est_cost min = 0.01 }" in roi
    est = _effect(values, "pp_cplan_bz_est_wheat_farm")
    slots = re.findall(r"add = (pp_cplan_bs_wheat_farm_\d+)", est)
    assert slots
    method = _effect(values, "pp_cplan_bm_wheat_farm_1_1")
    assert '"market.market_price(goods:wheat)"' in method
    assert "modifier:local_wheat_output_modifier add = 1 subtract = scope:pp_cplan_hv_wheat min = 0" in method
    # goods no harvest touches keep their output modifier alone
    iron = "".join(_effect(values, name) for name in re.findall(r"^(pp_cplan_bm_iron_mine_\d+_\d+) = \{", values, re.MULTILINE))
    assert "modifier:local_iron_output_modifier add = 1 min = 0" in iron and "pp_cplan_hv_iron" not in iron
    harvest = _effect(_read(MOD / cp.EFFECTS), "pp_cplan_business_harvest")
    names = re.findall(r"^(pp_harvest_\w+) = \{", _read(MOD / cp.HARVEST_MODIFIERS), re.MULTILINE)
    for name in names:
        assert f"has_location_modifier = {name} }}" in harvest, name
    assert "save_temporary_scope_value_as = { name = pp_cplan_hv_wheat value = -0.26 }" in harvest
    assert "pp_cplan_business_min_roi = {\n\tvalue = 100\n\tdivide = { value = pp_cplan_business_years min = 1 }" in values


def test_business_group_builds_the_best_returns_first() -> None:
    group = _effect(_read(EFFECTS), "pp_cplan_group_business")
    assert group.index("pp_cplan_business_types = yes") < group.index("pp_cplan_business_pick = yes") < group.index("order_by = pp_cplan_bz_roi_n")
    assert "limit = { pp_cplan_business_site = yes }" in group
    assert "pp_cplan_construct_scoped = { why = 103 }" in group
    assert group.index("order_by = pp_cplan_bz_roi_n") < group.index("pp_cplan_business_types_clear = yes")
    site = _effect(_read(TRIGGERS), "pp_cplan_business_site")
    for part in ("pp_cplan_location_ok = yes", "NOT = { has_variable = pp_lprof_xg }", "pp_cplan_site_free = yes",
                 "market ?= { always = yes }"):
        assert part in site, part


def test_business_group_does_not_look_without_gold() -> None:
    """The pick is the pass's dear part (every free site against every business type). A group that starts without
    gold to spend can build nothing, so it does not look; it marks that for its pane, which then says so instead of
    "nothing waited for gold" (what the businesses would have cost is not counted in such a month)."""
    group = _effect(_read(EFFECTS), "pp_cplan_group_business")
    start = group.index("pp_cplan_group_start = { why = 103 add = pp_cplan_share_business }")
    gate = group.index("limit = { pp_cplan_budget_left = yes }")
    skipped = group.index("else = {\n\t\t\tset_variable = { name = pp_cplan_ds_business_skipped value = 101 }")
    # the part is added first (the gate reads the gold of the groups so far, this one included); everything dear
    # sits behind the gate
    assert start < gate < group.index("pp_cplan_business_types = yes") < group.index("pp_cplan_business_pick = yes")
    assert group.index("pp_cplan_business_types_clear = yes") < skipped
    assert group.count("pp_cplan_budget_left") == 1
    assert ("skipped", 100) in cp.SITUATION["business"]
    from prosper_or_perish_constructor import construction_plan_detail as cpd

    gui = cpd.render_gui()
    pane = gui[gui.index("type pp_cplan_detail_business = vbox"):]
    looked = "Not(GreaterThan_CFixedPoint(GetPlayer.MakeScope.ScriptValue('pp_cplan_d_business_skipped'), '(CFixedPoint)0.5'))"
    for key in ("PP_CPLAN_D_NO_WAIT", "PP_CPLAN_D_BUSINESS_NONE"):
        line = re.search(rf"visible = \"\[([^\n]*)\]\"\n\t+text = \"{key}\"", pane)
        assert line and line.group(1).endswith(f", {looked})"), key
    assert re.search(r"visible = \"\[GreaterThan_CFixedPoint\(GetPlayer\.MakeScope\.ScriptValue\('pp_cplan_d_business_skipped'\), "
                     r"'\(CFixedPoint\)0\.5'\)\]\"\n\t+text = \"PP_CPLAN_D_BUSINESS_SKIPPED\"", pane)
    assert "did not look" in cpd.texts()["PP_CPLAN_D_BUSINESS_SKIPPED"]
    assert "did not look" in cpd.texts()["PP_CPLAN_D_CHART_TT_BUSINESS"]


# ---- Shared guards ----


def test_build_cost_data() -> None:
    """The cost formula's inputs per building (calibrated in game 2026-11-06 on 158 constructions)."""
    result = _result()
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
    """Every can-build check of the generated food, logistics and improvement pickers also asks for the construction
    goods in the market (else the construction stalls) and for no level of the building under construction here."""
    effects = _read(MOD / cp.EFFECTS)
    triggers = _read(MOD / cp.TRIGGERS)
    checks = re.findall(r"location_and_owner_can_build = \{ building_type = (\w+) \}([^\n]*)", effects)
    assert checks
    for name, rest in checks:
        demand = re.search(r"pp_cplan_goods_here_(\w+) = yes", rest)
        assert demand, name
        assert f"pp_cplan_goods_here_{demand.group(1)} = {{" in triggers, demand.group(1)
        assert f"building_type = building_type:{name} building_levels_under_construction > 0" in rest, name


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
    for name, parent in _widget_tree(_read(WINDOW)):
        if parent in {"flowcontainer", "container", "dynamicgridbox", "fixedgridbox"}:
            assert name not in {"hbox", "vbox"}, f"{name} directly inside {parent}"


def test_raw_text_never_replaced_other_properties() -> None:
    assert "conraw_text" not in _read(WINDOW)


def test_only_human_countries_run_the_plan() -> None:
    text = _read(ON_ACTION)
    assert "is_ai = no" in text
    assert "has_variable = pp_cplan_on" in text


def test_effects_use_the_vanilla_can_build_check() -> None:
    """Every construction the generated pickers start is guarded by the location and owner can-build check."""
    effects = _read(MOD / cp.EFFECTS)
    blocks = re.findall(r"limit = \{([^\n]*)\}\n\t*pp_cplan_construct(?:_food)? = \{ type = (\w+)", effects)
    assert blocks
    for limit, building in blocks:
        if "pp_cplan_pick" in limit:
            continue  # the farm and improvement pickers checked the candidate before they picked it
        assert f"location_and_owner_can_build = {{ building_type = {building} }}" in limit, building


def test_game_automation_is_respected() -> None:
    """Jan 2026-11-09: the plan and the game's own automation must not undo each other: the plan never adds a level to a
    closed building and never starts a construction where one is under way (whoever started it)."""
    scoped = _effect(_read(EFFECTS), "pp_cplan_construct_scoped")
    assert "pp_cplan_bt_queued < 0.5" in scoped and "is_opened = no" in scoped
    # one construction at a time per location: the engine builds them one after another (test world 2026-11-09)
    assert "pp_cplan_site_free = yes" in scoped
    # the location profiles ask the same before a rule tries (their state 3), by the plan's trigger or the engine's count
    profiles = re.sub(r"#[^\n]*", "", _read(PROFILE_EFFECTS))
    assert "pp_cplan_site_free" in profiles or "num_civil_constructions > 0" in profiles


def test_one_place_says_when_a_site_is_free() -> None:
    """The plan starts nothing where a construction is under way. The engine's max_constructions_at_same_time would
    allow more in some locations (not verified in game), so the check sits in ONE trigger, pp_cplan_site_free, and no
    other plan script reads num_civil_constructions."""
    assert _effect(_read(TRIGGERS), "pp_cplan_site_free").strip() == "num_civil_constructions < pp_cplan_site_slots"
    for path in _plan_script_files():
        code = re.sub(r"#[^\n]*", "", _read(path))
        if path == TRIGGERS:
            code = code.replace(_effect(code, "pp_cplan_site_free"), "")
        assert "num_civil_constructions" not in code, path.name
    effects = _read(EFFECTS)
    # every place that starts or looks for a construction asks it: the construction itself, the business sites, the
    # farm sites (a busy one must not use up a try), and the logistics and improvement groups before they look
    assert "pp_cplan_site_free = yes" in _effect(_read(TRIGGERS), "pp_cplan_business_site")
    food = _effect(effects, "pp_cplan_food_province")
    sites = food[food.index("ordered_location_in_province"):food.index("order_by = pp_cplan_farm_best_roi")]
    assert "pp_cplan_farm_ok = yes" in sites and "pp_cplan_site_free = yes" in sites
    for group, build in (("logistics", "pp_cplan_try_logistics_here"), ("improve", "pp_cplan_try_improve_here")):
        assert f"limit = {{ pp_cplan_site_free = yes }}\n\t\t\t\t{build} = yes" in _effect(effects, f"pp_cplan_group_{group}"), group


# ---- Baseline rules (Jan 2026-11-08) ----


def test_baseline_defaults() -> None:
    config = cp.load_config(PROJECT)
    assert config.access_threshold == 97 and config.hungry_months == 6
    assert (config.granary_capacity_months, config.granary_fill_pct) == (24, 85)
    assert (config.grange_surplus_pct, config.famine_months, config.yard_payback_years) == (5, 3, 10)
    assert config.granges == ("grange",) and config.yards == ("victualling_yard",)
    assert config.access_blacklist == ("staple_port_commercial_stagnation_modifier",)


def test_nothing_is_kept_between_passes() -> None:
    """Jan: no history. The baseline rules read the game as it stands; no counter variables, no watch effects; the
    pass's own budget and business marks go at its end."""
    for path in (EFFECTS, TRIGGERS, VALUES, SCRIPTED_GUIS):
        text = _read(path)
        for gone in ("pp_cplan_gw", "pp_cplan_fw", "pp_cplan_al", "pp_cplan_mm", "pp_cplan_mkt",
                     "pp_cplan_count_up", "pp_cplan_reset_watch", "_watch = yes"):
            assert gone not in text, f"{path.name}: {gone}"
    run = _effect(_read(EFFECTS), "pp_cplan_run")
    assert "remove_variable = pp_cplan_pot" in run and "remove_variable = pp_cplan_cap" in run


def test_food_pass_order() -> None:
    """One food construction a province a month: famine Tavern, farm, Granary (while due), kitchen, Tavern, Grange, Yard."""
    body = _effect(_read(EFFECTS), "pp_cplan_food_province")
    steps = ["# 1.", "# 2.", "# 3.", "# 4.", "# 5.", "# 6.", "# 7."]
    places = [body.index(step) for step in steps] + [len(body)]
    assert places == sorted(places)
    part = {n: body[places[n - 1]:places[n]] for n in range(1, 8)}
    assert "pp_cplan_famine = yes" in part[1] and "pp_cplan_try_tavern_here" in part[1]
    assert "pp_cplan_hungry = yes" in part[2] and "pp_cplan_try_farm_here" in part[2]
    assert "order_by = pp_cplan_farm_best_roi" in part[2]
    assert "scope:pp_cplan_gd > 0.5" in part[3] and "pp_cplan_try_granary_here" in part[3]
    assert "pp_cplan_hungry" not in part[4] and "pp_cplan_try_kitchen_here" in part[4]
    assert "pp_cplan_hungry = yes" in part[5] and "pp_cplan_try_tavern_here" in part[5]
    assert "scope:pp_cplan_rd > 0.5" in part[6] and "pp_cplan_try_grange_here" in part[6]
    # the Granary and Grange checks and the store a year from now are read once a province, before the steps
    head = body[:places[0]]
    assert "limit = { pp_cplan_granary_due = yes }\n\t\t\tsave_temporary_scope_value_as = { name = pp_cplan_gd value = 1 }" in head
    assert "limit = { pp_cplan_grange_due = yes }\n\t\t\tsave_temporary_scope_value_as = { name = pp_cplan_rd value = 1 }" in head
    assert "save_temporary_scope_value_as = { name = pp_cplan_fy value = pp_cplan_food_in_a_year }" in head
    assert "pp_cplan_try_yard_here" in part[7]
    # Taverns only where the market holds victuals; every step after the first asks whether the province built already
    assert "pp_cplan_victuals_here = yes" in part[1] and "pp_cplan_victuals_here = yes" in part[5]
    for n in range(2, 8):
        assert "pp_cplan_may_try = yes" in part[n], n


def test_hunger_reads_a_normal_year() -> None:
    triggers = _read(TRIGGERS)
    # read once a province (pp_cplan_food_province saves scope:pp_cplan_fy = pp_cplan_food_in_a_year)
    assert "scope:pp_cplan_fy < pp_cplan_hungry_months" in _effect(triggers, "pp_cplan_hungry")
    assert "scope:pp_cplan_fy < pp_cplan_famine_months" in _effect(triggers, "pp_cplan_famine")
    values = _read(VALUES)
    gain = _effect(values, "pp_cplan_normal_gain")
    assert "add = pp_cplan_harvest_food" in gain and "pp_cplan_spoil_rate" in gain
    assert "subtract = pp_cplan_harvest_food" in _effect(values, "pp_cplan_normal_consumption")
    granary = _effect(triggers, "pp_cplan_granary_due")
    for part in ("pp_cplan_capacity_months < pp_cplan_granary_cap", "pp_cplan_fill_pct >= pp_cplan_granary_fill",
                 "pp_cplan_normal_gain > 0"):
        assert part in granary
    assert "pp_cplan_normal_gain_pct >= pp_cplan_grange_surplus" in _effect(triggers, "pp_cplan_grange_due")
    generated = _read(MOD / cp.VALUES)
    assert "pp_cplan_hungry_months = { value = 6 }" in generated


def test_harvest_blacklist_covers_every_harvest_modifier() -> None:
    rates = cp.harvest_rates(MOD)
    assert len(rates) >= 15
    names = re.findall(r"^(pp_harvest_\w+) = \{", _read(MOD / cp.HARVEST_MODIFIERS), re.MULTILINE)
    block = _effect(_read(MOD / cp.VALUES), "pp_cplan_harvest_rate")
    for name in names:
        assert f"has_location_modifier = {name} }}" in block, name
    # bad years make the peasants eat more, good years less
    assert rates["western_europe"]["abysmal"] > 0 > rates["western_europe"]["bountiful"]
    assert all(set(found) == set(cp.HARVEST_SEVERITIES) for found in rates.values()), rates
    outputs = cp.harvest_outputs(MOD)
    assert outputs["western_europe"]["abysmal"]["wheat"] == -0.26


def test_logistics_reads_access_without_events() -> None:
    wanted = _effect(_read(TRIGGERS), "pp_cplan_logistics_wanted")
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
        assert "location_and_owner_can_build" in block
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


def test_hunger_bucket_holds_every_staple_food_maker() -> None:
    """Farms, orchards, fisheries, herds and forest villages compete in one bucket by payback (Jan 2026-11-08)."""
    result = _result()
    buildings = {b for tiers in result.food_lines.values() for b in tiers}
    for name in ("wheat_farm", "fruit_orchard", "fishing_village", "ocean_fishery", "forest_village", "sheep_farms"):
        assert name in buildings, name
    assert "cookshop" not in buildings and "tavern" not in buildings
    assert result.food_lines["forest_village"][0] == "forest_village"


def test_improvements_cheap_and_much_first() -> None:
    """Jan 2026-11-08: where population over capacity reaches the line, the improvement with the most capacity per
    gold; the fullest locations first."""
    result = _result()
    assert {"land_clearance", "field_management", "irrigation_systems", "polders"} <= set(result.improvements)
    generated = _read(MOD / cp.VALUES)
    picker = _effect(_read(MOD / cp.EFFECTS), "pp_cplan_try_improve_here")
    for key in result.improvements:
        assert f"pp_cplan_imp_{key} > var:pp_cplan_best" in picker, key
        assert f"location_and_owner_can_build = {{ building_type = {key} }}" in picker, key
        value = _effect(generated, f"pp_cplan_imp_{key}")
        assert f"building_type:{key}.building_base_cost_in_gold" in value
    run = _effect(_read(EFFECTS), "pp_cplan_group_improve")
    block = run[run.index("pp_cplan_improve_w > 0"):run.index("pp_cplan_try_improve_here")]
    assert "location_population_percentage >= scope:pp_cplan_country.pp_cplan_improve_line" in block
    assert "order_by = pp_cplan_fill_here" in block


def test_construction_goods_cover_months_of_draw() -> None:
    """Test world 2026-11-08: four River Boatmen's Yards started on 0.65 naval supplies and stood still for a year.
    A construction starts only where its market holds construction_goods_months of its draw."""
    config = cp.load_config(PROJECT)
    assert config.construction_goods_months == 12
    yard = _effect(_read(MOD / cp.TRIGGERS), "pp_cplan_goods_here_pp_river_boatmen_yard_construction")
    assert '"stockpile_in_market(goods:naval_supplies)" >= 2.4' in yard  # 0.2 a month x 12


def test_profile_pass_gives_every_location_a_turn() -> None:
    """Test world 2026-11-08: in the list's own order the profile assigned last built nothing in ten years."""
    run = _effect(_read(PROFILE_EFFECTS), "pp_lprof_run")
    assert "ordered_in_list = {" in run and "order_by = pp_lprof_turn" in run
    assert "every_in_list" not in run.split("ordered_in_list")[1]
    assert "subtract = total_building_levels" in _effect(_read(VALUES), "pp_lprof_turn")


def test_granary_before_kitchen_while_due() -> None:
    """AI test run 2026-11-09: with the kitchen first, Cookshops took the province capital year after year (one
    construction at a time per location) and 15 years built no Granary where one was due. A full, capped store spoils
    what a kitchen adds, so the Granary goes first while it is due."""
    food = _effect(_read(EFFECTS), "pp_cplan_food_province")
    assert food.index("pp_cplan_try_granary_here = yes") < food.index("pp_cplan_try_kitchen_here = yes")
    granary = food[food.index("# 3. a Granary"):food.index("pp_cplan_try_granary_here = yes")]
    assert "scope:pp_cplan_gd > 0.5" in granary


def test_no_name_is_defined_twice() -> None:
    """A script value, effect or trigger defined twice silently takes the last body (the weight part pp_cplan_improve_pct
    once shadowed the improvement line of the same name)."""
    for kind in ("script_values", "scripted_effects", "scripted_triggers"):
        seen: dict[str, str] = {}
        for path in sorted((MOD / "in_game/common" / kind).glob("pp_*.txt")):
            for name in re.findall(r"^([A-Za-z_][A-Za-z0-9_]*) = \{", _read(path), re.MULTILINE):
                assert name not in seen, f"{kind}: {name} in {seen.get(name)} and {path.name}"
                seen[name] = path.name


def test_groups_count_what_waits_for_gold() -> None:
    """Jan 2026-11-09: the window shows how much gold the rules wanted, calculated from the last pass. Every group goes
    through all it wants even after the gold is used up; the construction itself checks the gold and counts what the
    gold does not reach (cost and number) once per decision: a province of the food rule, a location otherwise."""
    effects = _read(EFFECTS)
    # (the business group alone asks once, before it looks at all: test_business_group_does_not_look_without_gold)
    for group in ("food", "logistics", "improve"):
        assert "pp_cplan_budget_left" not in _effect(effects, f"pp_cplan_group_{group}"), group
    assert "pp_cplan_budget_left" not in _effect(effects, "pp_cplan_food_province")
    assert "pp_cplan_budget_left" not in _effect(_read(TRIGGERS), "pp_cplan_may_try")
    note = _effect(effects, "pp_cplan_note_wait")
    assert "save_temporary_scope_value_as = { name = pp_cplan_wc value = pp_cplan_est_cost }" in note
    assert "limit = { NOT = { has_variable = pp_cplan_noted } }" in note
    assert "change_variable = { name = pp_cplan_dwait_$why$ add = scope:pp_cplan_wc }" in note
    assert "change_variable = { name = pp_cplan_dwn_$why$ add = 1 }" in note
    # the decision units clear the mark: each food province, each profile location, each location of the other groups
    assert _effect(effects, "pp_cplan_food_province").count("remove_variable = pp_cplan_noted") == 2
    for group in ("logistics", "improve", "business"):
        assert "remove_variable = pp_cplan_noted" in _effect(effects, f"pp_cplan_group_{group}"), group
    profiles = _effect(_read(PROFILE_EFFECTS), "pp_lprof_run")
    assert profiles.index("remove_variable = pp_cplan_noted") < profiles.index("pp_lprof_location_rules = yes")


def test_detail_numbers_per_group() -> None:
    """What each rule group did last month, for the window: gold it could spend, gold spent, constructions started,
    the list of where, what each cost and why, its situation and twelve months of gold wanted and spent. They start
    afresh every pass, the rules never read them, switching the plan on clears the chart."""
    effects = _read(EFFECTS)
    generated = _read(MOD / cp.EFFECTS)
    values = _read(MOD / cp.VALUES)
    start = _effect(effects, "pp_cplan_group_start")
    assert "set_variable = { name = pp_cplan_dran_$why$ value = yes }" in start
    assert ("name = pp_cplan_dhad_$why$ value = { value = pp_cplan_cap_n subtract = pp_cplan_spent_n min = 0 add = 100 }"
            in start)
    now = _effect(effects, "pp_cplan_construct_now")
    for line in ("change_variable = { name = pp_cplan_dspent_$why$ add = scope:pp_cplan_paid }",
                 "change_variable = { name = pp_cplan_dn_$why$ add = 1 }",
                 "add_to_variable_list = { name = pp_cplan_log_$why$ target = scope:pp_cplan_site }",
                 "set_variable = { name = pp_cplan_log_cost value = scope:pp_cplan_paid }",
                 "set_variable = { name = pp_cplan_log_val value = scope:pp_cplan_rv }",
                 "set_variable = { name = pp_cplan_log_step value = scope:pp_cplan_rs }"):
        assert line in now, line
    run = _effect(effects, "pp_cplan_run")
    assert run.index("pp_cplan_stats_reset = yes") < run.index("pp_cplan_group_profiles = yes")
    assert run.rindex("pp_cplan_group_improve = yes") < run.index("pp_cplan_history_push = yes")
    for name in ("pp_cplan_log_cost", "pp_cplan_log_val", "pp_cplan_log_step"):
        assert f"remove_variable = {name}" in run, name
    reset = _effect(generated, "pp_cplan_stats_reset")
    push = _effect(generated, "pp_cplan_history_push")
    clear = _effect(generated, "pp_cplan_history_clear")
    months = cp.HISTORY_MONTHS
    for group in cp.GROUPS:
        why = cp.GROUP_WHY[group]
        assert f"clear_variable_list = pp_cplan_log_{why}" in reset and f"remove_variable = pp_cplan_dran_{why}" in reset
        for var in cp.GROUP_NUMBERS.values():
            assert f"set_variable = {{ name = pp_cplan_{var}_{why} value = 100 }}" in reset, (group, var)
        for name, start_value in cp.SITUATION[group]:
            assert f"set_variable = {{ name = pp_cplan_ds_{group}_{name} value = {start_value} }}" in reset
            assert f"pp_cplan_d_{group}_{name} = {{" in values
        assert f"from = pp_cplan_hn_{why}_{months - 1} to = pp_cplan_hn_{why}_{months} " in push
        # the oldest month moves first, so nothing is copied twice
        assert push.index(f"to = pp_cplan_hn_{why}_{months} ") < push.index(f"to = pp_cplan_hn_{why}_2 ")
        assert (f"name = pp_cplan_hn_{why}_1 value = {{ value = var:pp_cplan_dspent_{why} add = var:pp_cplan_dwait_{why} "
                f"subtract = 100 }}") in push
        assert f"remove_variable = pp_cplan_hs_{why}_{months}" in clear
        for number in (*cp.GROUP_NUMBERS, "need", "ran"):
            assert f"pp_cplan_d_{group}_{number} = {{" in values, (group, number)
        assert _effect(values, f"pp_cplan_h_{group}_max").count("\tmin = pp_cplan_h_") == months
        assert f"divide = pp_cplan_h_{group}_max" in _effect(values, f"pp_cplan_h_{group}_needp_1")
    # every group gives its constructions a reason: food the store a year from now and the step, logistics the
    # access, improvements the fill, businesses the payback, profiles the rule
    food = _effect(effects, "pp_cplan_food_province")
    assert "save_temporary_scope_value_as = { name = pp_cplan_rv value = { value = scope:pp_cplan_fy add = 100 } }" in food
    for step in range(1, 8):
        assert f"save_temporary_scope_value_as = {{ name = pp_cplan_rs value = {step} }}" in food, step
    for group, value, build in (("logistics", "pp_cplan_access_normal multiply = 100", "pp_cplan_try_logistics_here"),
                                ("improve", "location_population_percentage multiply = 100", "pp_cplan_try_improve_here"),
                                ("business", "value = 100 divide = var:pp_cplan_bz_roi", "pp_cplan_construct_scoped")):
        body = _effect(effects, f"pp_cplan_group_{group}")
        assert value in body and body.index("name = pp_cplan_rv") < body.index(build), group
    assert "save_temporary_scope_value_as = { name = pp_cplan_rs value = $r$ }" in _effect(_read(PROFILE_EFFECTS), "pp_lprof_rule")
    assert "pp_cplan_history_clear = yes" in _effect(_read(SCRIPTED_GUIS), "pp_cplan_toggle_on")
    # the rules never decide on these numbers (only the window reads them; the running minimums compare in place)
    readers = [path for path in _plan_script_files() if "script_values" not in str(path)] + [PROFILE_EFFECTS]
    window_only = re.compile(r"limit = \{[^{}]*?\b(pp_cplan_(?:d_\w+|h_\w+|dhad_\d+|dspent_\d+|dwait_\d+|dwn_\d+|dn_\d+|hn_\w+|hs_\w+))")
    for path in readers:
        found = window_only.search(_read(path))
        assert not found, f"{path.name}: a rule reads {found.group(1) if found else ''}"
