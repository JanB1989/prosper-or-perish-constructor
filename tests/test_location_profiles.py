"""Location Profiles, script side (src/prosper_or_perish_constructor/location_profiles.py,
mod/pp/.../pp_location_profiles*; contract docs/location_profiles.md)."""

from __future__ import annotations

import re
from pathlib import Path

from prosper_or_perish_constructor import construction_plan as cp
from prosper_or_perish_constructor import location_plan as lp
from prosper_or_perish_constructor import location_profiles as lpf
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
MOD = ROOT / "mod" / "pp"
COMMON = MOD / "in_game/common"
CONTRACT = ROOT / "docs/location_profiles.md"
PLAN_EFFECTS = COMMON / "scripted_effects/pp_construction_plan.txt"
PLAN_TRIGGERS = COMMON / "scripted_triggers/pp_construction_plan.txt"
PLAN_VALUES = COMMON / "script_values/pp_construction_plan.txt"
OWN_FILES = (MOD / lpf.EFFECTS, MOD / lpf.HAND_EFFECTS, MOD / lpf.VALUES, MOD / lpf.TRIGGERS, MOD / lpf.SCRIPTED_GUIS)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _code(path: Path) -> str:
    return re.sub(r"#[^\n]*", "", _read(path))


def _defined(folder: str) -> set[str]:
    keys: set[str] = set()
    for path in (COMMON / folder).glob("*.txt"):
        keys |= set(re.findall(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{", _read(path), re.MULTILINE))
    return keys


def _block(text: str, name: str) -> str:
    match = re.search(rf"^{name} = \{{(.*?)^\}}", text, re.MULTILINE | re.DOTALL)
    assert match, f"{name} missing"
    return match.group(1)


def _build():
    return lpf.build(ROOT, PROJECT, MOD, vanilla_root(ROOT, PROJECT))


def test_built_mod_is_in_step() -> None:
    assert lpf.apply(ROOT, PROJECT, MOD, vanilla_root(ROOT, PROJECT), write=False) == 0, "run ppc finalize"
    result, _ = _build()
    keys = [item.key for item in result.items]
    assert {"lumber", "furniture", "trade_category", lpf.LOGISTICS} <= set(keys)
    assert len(keys) == len(set(keys))
    # market access = the plan's logistics buildings in its order
    assert [c.name for c in result.targets[lpf.LOGISTICS]] == list(cp.load_config(PROJECT).logistics_order)
    # a standing producer grows highest tier first
    assert [c.name for c in result.targets["furniture"]][:2] == ["furniture_mill", "furniture_manufactory"]
    for category in lp.load_config(PROJECT).categories:
        assert result.targets[category], category


def test_category_lists_hold_only_player_buildings() -> None:
    result, _ = _build()
    database = cp._database(MOD, vanilla_root(ROOT, PROJECT), cp.BUILDING_TYPES)
    for category, names in result.categories.items():
        for name in names:
            keys, body = database[name]
            assert keys["category"] == category, name
            assert keys.get("is_foreign") != "yes" and keys.get("is_special") != "yes", name
            assert "estate" not in keys and "international_organization_link" not in keys, name
            assert not re.search(r"\ballow\s*=\s*\{\s*always\s*=\s*no\s*\}", body), name
    assert "marketplace" in result.categories["trade_category"]
    assert "trade_office" not in result.categories["trade_category"]  # a foreign building
    assert "temple" in result.categories["religious_category"]


def test_every_candidate_has_cost_data_and_guards() -> None:
    """Each building a rule can start has the plan's cost data (price factor, efficiency term) and the market check of
    its construction goods; every start or expand of the hand-written effects runs the game's can-build check."""
    effects = _read(MOD / lpf.EFFECTS)
    plan_triggers = _read(MOD / cp.TRIGGERS)
    plan_values = _read(MOD / cp.VALUES) + _read(PLAN_VALUES)
    known = cp.defined_buildings(MOD, vanilla_root(ROOT, PROJECT))
    calls = re.findall(r"pp_lprof_(?:expand|start|try) = \{ type = (\w+) demand = (\w+) cat = (\w+) ipl = ([0-9.]+) \}", effects)
    assert len(calls) > 300
    for name, demand, category, _ in calls:
        assert name in known, name
        assert f"pp_cplan_goods_here_{demand} = {{" in plan_triggers, demand
        assert f"pp_cplan_cd_{demand} = {{" in plan_values, demand
        assert f"pp_cplan_eff_{category} = {{" in plan_values, category
    hand = _code(MOD / lpf.HAND_EFFECTS)
    for name in ("pp_lprof_expand", "pp_lprof_start", "pp_lprof_try"):
        body = _block(hand, name)
        assert "location_and_owner_can_build = { building_type = $type$ }" in body, name
        assert "pp_cplan_goods_here_$demand$ = yes" in body, name
    # every construction goes through the plan's budget check and its construct (ledger, never twice while queued)
    build = _block(hand, "pp_lprof_build")
    assert "pp_cplan_budget_left = yes" in build and f"pp_cplan_construct_scoped = {{ why = {lpf.WHY_PROFILE} }}" in build
    assert "construct_building" not in hand
    assert "pp_lprof_payback100 > scope:pp_lprof_pb" in _block(hand, "pp_lprof_expand")


def test_targets_wait_for_their_constructions() -> None:
    """A rule never starts a second level while any building of its target has one under construction here."""
    effects = _read(MOD / lpf.EFFECTS)
    result, _ = _build()
    for key, candidates in result.targets.items():
        if not candidates:
            continue
        body = _block(effects, f"pp_lprof_t_{key}")
        first = body.split("\n\t}")[0]
        assert "building_levels_under_construction > 0" in first and "value = 103" in first, key
        for candidate in candidates:
            assert f"building_type = building_type:{candidate.name}" in first, (key, candidate.name)


def test_references_exist() -> None:
    effects = _defined("scripted_effects")
    triggers = _defined("scripted_triggers")
    values = _defined("script_values")
    text = "".join(_code(path) for path in OWN_FILES if path != MOD / lpf.VALUES) + _code(PLAN_EFFECTS) + _code(PLAN_TRIGGERS)
    for name in set(re.findall(r"(?<![\w:.$])(pp_[a-z0-9_]+) = yes\b", text)):
        assert name in effects | triggers, f"{name} missing"
    for name in set(re.findall(r"(?<![\w:.$])(pp_[a-z0-9_]+) = \{ [a-z]+ = ", text)):
        assert name in effects | triggers, f"{name} missing"
    for name in set(re.findall(r"\b(?:value|add|subtract|multiply|divide) = (pp_[a-z0-9_]+)(?![\w$])", text)):
        assert name in values, f"script value {name} missing"
    for name in set(re.findall(r"(?<![\w:.$])(pp_[a-z0-9_]+) [<>]=? ", text)):
        assert name in values, f"script value {name} missing"
    own_values = _code(MOD / lpf.VALUES)
    for name in set(re.findall(r"(?<![\w:.$])(pp_[a-z0-9_]+) = yes\b", own_values)):
        assert name in triggers, f"trigger {name} missing"
    for name in set(re.findall(r"\b(?:value|add|subtract) = (pp_[a-z0-9_]+)(?![\w$])", own_values)):
        assert name in values, f"script value {name} missing"


def test_scripted_guis_of_the_contract() -> None:
    guis = _read(MOD / lpf.SCRIPTED_GUIS)
    effects = _defined("scripted_effects")
    rows = re.findall(r"^\| `(pp_lprof_[a-z_]+)` \| (location|country)", _read(CONTRACT), re.MULTILINE)
    assert len(rows) == 8
    for name, scope in rows:
        block = _block(guis, name)
        assert f"scope = {scope}" in block, name
        for effect in re.findall(r"(pp_[a-z0-9_]+) = yes", block):
            assert effect in effects, effect


def test_flags_and_scopes_are_declared() -> None:
    """The GUI adds its parameters with AddScope and passes flags; the script check needs them set somewhere (the never-
    run block of pp_cplan_run)."""
    config = lpf.load_config(PROJECT)
    result, _ = _build()
    effects = _read(MOD / lpf.EFFECTS)
    declared = set(re.findall(r"value = flag:(\w+)", _block(effects, "pp_lprof_declare_flags")))
    expected = {f"s{k}" for k in range(1, config.slots + 1)} | {"none", "icon", "up", "down"}
    expected |= {f"r{r}" for r in range(1, config.rules + 1)} | {f"c{n}" for n in range(1, len(config.colors) + 1)}
    expected |= {item.key for item in result.items}
    assert expected <= declared
    for path in (MOD / lpf.EFFECTS, MOD / lpf.HAND_EFFECTS):
        for flag in re.findall(r"flag:(\w+)", _code(path)):
            assert flag in declared, flag
    run = _block(_code(PLAN_EFFECTS), "pp_cplan_run")
    never = run[run.index("always = no"):]
    for scope in ("pp_slot", "pp_key", "pp_dir", "pp_field", "pp_col"):
        assert f"save_scope_as = {scope}" in never, scope
    assert "pp_lprof_declare_flags = yes" in never


def test_monthly_pass_order_and_global_rules() -> None:
    """Profiles run first with their own share; every global rule leaves a profile location alone."""
    run = _block(_code(PLAN_EFFECTS), "pp_cplan_run")
    order = [run.index(marker) for marker in ("pp_lprof_run = yes", "pp_cplan_has_own_locations = yes",
                                               "pp_cplan_food_province = yes", "pp_cplan_try_logistics_here = yes",
                                               "pp_cplan_goods_run = yes")]
    assert order == sorted(order)
    assert run.index("set_variable = { name = pp_cplan_cap value = 100 }") < order[0]
    assert "NOT = { has_variable = pp_lprof }" in _block(_code(PLAN_TRIGGERS), "pp_cplan_location_ok")
    assert "add = pp_lprof_group_n" in _block(_code(PLAN_VALUES), "pp_cplan_groups_on")
    # the global groups pick their locations through pp_cplan_location_ok
    plan = _code(MOD / cp.EFFECTS)
    for limit in re.findall(r"ordered_owned_location = \{\n\t*limit = \{([^\n]*)", plan):
        assert "pp_cplan_location_ok = yes" in limit
    assert "pp_cplan_location_ok = yes" in run.split("ordered_owned_location")[1].split("order_by")[0]
    hand = _code(MOD / lpf.HAND_EFFECTS)
    group = _block(hand, "pp_lprof_run")
    assert "change_variable = { name = pp_cplan_cap add = pp_cplan_group_share }" in group
    assert "owner ?= scope:pp_cplan_country" in group and "pp_lprof_location_rules = yes" in group
    # the first rule that starts a construction ends the location for the month
    rule = _block(hand, "pp_lprof_rule")
    assert "has_variable = pp_cplan_hit" in rule and "value = 109" in rule
    rules = _block(_code(MOD / lpf.EFFECTS), "pp_lprof_location_rules")
    assert rules.count("remove_variable = pp_cplan_hit") == 2
    # one layer per location: a profile drops own rules, own rules drop a profile
    assert "remove_variable = pp_cplan_mode" in _block(hand, "pp_lprof_assign_to")
    assert "pp_lprof_unassign = yes" in _block(_code(PLAN_EFFECTS), "pp_cplan_own_sync")


def test_only_the_player() -> None:
    """The pass runs only inside the plan's monthly pass (human countries with the plan on); no on_action of its own."""
    for path in (COMMON / "on_action").glob("*.txt"):
        assert "pp_lprof" not in _read(path), path.name
    callers = [path.name for path in (COMMON / "scripted_effects").glob("*.txt") if "pp_lprof_run = yes" in _code(path)]
    assert callers == ["pp_construction_plan.txt"]


def test_slot_and_rule_counts_follow_the_config() -> None:
    config = lpf.load_config(PROJECT)
    effects = _code(MOD / lpf.EFFECTS)
    rules = _block(effects, "pp_lprof_location_rules")
    assert re.findall(r"pp_lprof_rules = \{ k = (\d+) \}", rules) == [str(k) for k in range(1, config.slots + 1)]
    assert re.findall(r"r = (\d+) \}", _block(effects, "pp_lprof_rules")) == [str(r) for r in range(1, config.rules + 1)]
    for name in ("pp_lprof_assign_do", "pp_lprof_new_do", "pp_lprof_set_do", "pp_lprof_color_do", "pp_lprof_payback_do",
                 "pp_lprof_rule_clear_do", "pp_lprof_rule_move_do", "pp_lprof_delete_do"):
        assert re.findall(r"flag:s(\d+) = ", _block(effects, name)) == [str(k) for k in range(1, config.slots + 1)], name
    new = _block(effects, "pp_lprof_new_do")
    for k in range(1, config.slots + 1):
        assert f"pp_lprof_new_slot = {{ k = {k} col = {lpf.color_value(config, k)} }}" in new
    assert "value = goods:lumber" in _block(_code(MOD / lpf.HAND_EFFECTS), "pp_lprof_new_slot")
    assert lpf.DEFAULT_ICON == "lumber"
    colors = re.findall(r"flag:c(\d+) = ", _block(effects, "pp_lprof_color_slot"))
    assert colors == [str(n) for n in range(1, len(config.colors) + 1)]
    values = _code(MOD / lpf.VALUES)
    free = _block(values, "pp_lprof_first_free")
    assert re.findall(r"has_variable = pp_lprof_(\d+)_on", free) == [str(k) for k in range(1, config.slots + 1)]
    for k in range(1, config.slots + 1):
        assert f"pp_lprof_{k}_locs_n = {{" in values and f"pp_lprof_{k}_col_n = {{" in values
        for r in range(1, config.rules + 1):
            assert f"pp_lprof_{k}_r{r}_pb_n = {{" in values
    for r in range(1, config.rules + 1):
        assert f"pp_lprof_r{r}_st_n = {{" in values


def test_items_reach_their_targets() -> None:
    result, _ = _build()
    effects = _code(MOD / lpf.EFFECTS)
    goods = _block(effects, "pp_lprof_goods_target")
    categories = _block(effects, "pp_lprof_category_target")
    keys = _block(effects, "pp_lprof_key_scope")
    category_key = _block(_code(MOD / lpf.TRIGGERS), "pp_lprof_category_key")
    for item in result.items:
        if item.kind == "good":
            assert f"flag:{item.key} = {{ goods:{item.key} = {{ save_scope_as = pp_lprof_val }} }}" in keys, item.key
            if result.targets[item.key]:
                assert f"goods:{item.key} = {{ pp_lprof_t_{item.key} = yes }}" in goods, item.key
        else:
            assert f"scope:pp_key = flag:{item.key}" in category_key, item.key
            assert f"flag:{item.key} = {{ pp_lprof_t_{item.key} = yes }}" in categories, item.key
    # nearly every good has a producer (the rest show "cannot be built here")
    assert sum(1 for item in result.items if item.kind == "good" and not result.targets[item.key]) <= 3


def _step(chain: list[tuple[str, float, int]], value: int | None, otherwise: int | None) -> int | None:
    for op, bound, new in chain:
        if (op == "<" and value < bound) or (op == ">" and value > bound):
            return new
    return otherwise


def test_payback_steps_follow_the_config() -> None:
    """Stepping the limit down from any walks every step down to the first; up walks back to any."""
    steps = lpf.load_config(PROJECT).payback_steps
    body = _block(_code(MOD / lpf.EFFECTS), "pp_lprof_pb_step")
    up_part, down_part = body.split("\telse = {\n\t\tif = {")
    chain_up = [(op, float(bound), int(new)) for op, bound, new in
                re.findall(r"var:\$var\$ (<) ([0-9.]+) \} set_variable = \{ name = \$var\$ value = (\d+)", up_part)]
    chain_down = [(op, float(bound), int(new)) for op, bound, new in
                  re.findall(r"var:\$var\$ (>) ([0-9.]+) \} set_variable = \{ name = \$var\$ value = (\d+)", down_part)]
    assert f"value = {steps[-1] + 100}" in down_part.split("else_if")[0]  # down from any = the last step
    seen = []
    value = steps[-1] + 100
    while True:
        seen.append(value - 100)
        lower = _step(chain_down, value, value)
        if lower == value:
            break
        value = lower
    assert seen == list(reversed(steps))
    seen = []
    value = steps[0] + 100
    while value is not None:
        seen.append(value - 100)
        value = _step(chain_up, value, None)
    assert seen == list(steps)
    # a value between steps snaps to the next step either way
    assert _step(chain_up, 106, None) == 107 and _step(chain_down, 106, 106) == 105


def test_states_and_texts() -> None:
    loc_path = MOD / lpf.LOC
    raw = loc_path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    assert text.splitlines()[0] == "l_english:"
    keys = dict(re.findall(r'^  ([A-Z0-9_]+): "(.*)"$', text, re.MULTILINE))
    for n in range(0, 10):
        assert f"PP_LPROF_ST_{n}" in keys, n
        assert not re.search(r"\d", keys[f"PP_LPROF_ST_{n}"]), "no numbers in player text"
    assert "PP_CPLAN_WHY_PROFILE" in (MOD / "main_menu/localization/english/pp_construction_plan_l_english.yml").read_text(encoding="utf-8-sig")
    finish = _block(_code(MOD / lpf.HAND_EFFECTS), "pp_lprof_finish")
    for rank, state in lpf.FAIL_STATE.items():
        if rank == 101:
            assert re.search(rf"else = \{{\s*set_variable = \{{ name = pp_lprof_r\$r\$_st value = {100 + state} \}}", finish), rank
        else:
            assert re.search(rf"var:pp_lprof_fail > {rank - 0.5:g} \}}\n\t\tset_variable = \{{ name = pp_lprof_r\$r\$_st value = {100 + state} \}}", finish), rank
    states = {int(n) - 100 for n in re.findall(r"name = pp_lprof_(?:st|r\$r\$_st) value = (1\d\d)", _code(MOD / lpf.HAND_EFFECTS) + _code(MOD / lpf.EFFECTS))}
    assert states <= set(lpf.STATES)


def test_no_not_with_several_conditions() -> None:
    """NOT = { a b } means neither a nor b in this script language (the v2 guard bug of 2026-11-06)."""
    for path in OWN_FILES + (PLAN_EFFECTS, PLAN_TRIGGERS):
        text = _code(path)
        for match in re.finditer(r"\bNOT = \{", text):
            depth, index = 1, match.end()
            while depth:
                depth += {"{": 1, "}": -1}.get(text[index], 0)
                index += 1
            body = text[match.end():index - 1]
            top, level = 0, 0
            for token in re.finditer(r"\{|\}|[A-Za-z_:.\"()0-9?$]+\s*(?:[<>=!?]+)", body):
                if token.group(0) == "{":
                    level += 1
                elif token.group(0) == "}":
                    level -= 1
                elif level == 0:
                    top += 1
            assert top <= 1, f"{path.name}: NOT with {top} conditions: {body.strip()[:80]}"


def test_effect_calls_pass_their_parameters() -> None:
    """Every call of a parametrized scripted effect or trigger passes each $param$ its body uses."""
    definitions: dict[str, set[str]] = {}
    for folder in ("scripted_effects", "scripted_triggers"):
        for path in (COMMON / folder).glob("pp_*.txt"):
            text = _code(path)
            for match in re.finditer(r"^([a-z_][a-z0-9_]*) = \{", text, re.MULTILINE):
                end = text.find("\n}", match.end())
                params = set(re.findall(r"\$([a-z]+)\$", text[match.end():end]))
                if params:
                    definitions[match.group(1)] = params
    assert {"pp_lprof_rule", "pp_lprof_expand", "pp_lprof_swap_rules"} <= set(definitions)
    calls = 0
    for path in OWN_FILES + (PLAN_EFFECTS,):
        for name, args in re.findall(r"\b([a-z_][a-z0-9_]*) = \{ ((?:[a-z]+ = [^\s{}]+ )+)\}", _code(path)):
            if name in definitions:
                calls += 1
                passed = set(re.findall(r"([a-z]+) = ", args))
                assert definitions[name] <= passed, f"{path.name}: {name} lacks {definitions[name] - passed}"
    assert calls > 300


def test_braces_balance() -> None:
    for path in OWN_FILES:
        text = _code(path)
        assert text.count("{") == text.count("}"), path.name
        depth = 0
        for char in text:
            depth += {"{": 1, "}": -1}.get(char, 0)
            assert depth >= 0, path.name


def test_rules_keep_the_payback_they_found() -> None:
    """A rule held back by its payback limit shows the shortest payback it found (Jan 2026-11-07: the number beside
    the limit): expand notes it, finish writes it into pp_lprof_r<r>_est, the badge text reads it."""
    code = _code(MOD / lpf.HAND_EFFECTS)
    expand = _block(code, "pp_lprof_expand")
    assert expand.index("pp_lprof_note_payback = yes") < expand.index("pp_lprof_payback100 > scope:pp_lprof_pb")
    finish = _block(code, "pp_lprof_finish")
    assert "set_variable = { name = pp_lprof_r$r$_est value = var:pp_lprof_best }" in finish
    assert "remove_variable = pp_lprof_best" in _block(code, "pp_lprof_rule")
    loc = (MOD / "main_menu/localization/english/pp_location_profiles_gui_l_english.yml").read_text(encoding="utf-8-sig")
    for r in range(1, lpf.load_config(PROJECT).rules + 1):
        assert f"'PP_LPROF_UI_EST_{r}'" in loc and f"pp_lprof_r{r}_est" in loc
