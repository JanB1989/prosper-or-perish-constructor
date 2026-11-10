"""Location Profiles, script side (src/prosper_or_perish_constructor/location_profiles.py,
mod/pp/.../pp_location_profiles*; contract docs/location_profiles.md)."""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest

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
    calls = re.findall(r"pp_lprof_(?:expand|start|try) = \{ type = (\w+) demand = (\w+) cat = (\w+) ipl = ([0-9.]+) "
                       r"pt = (\w+) sz = ([0-9.]+) \}", effects)
    assert len(calls) > 300
    staff = cp.staffing(cp._database(MOD, vanilla_root(ROOT, PROJECT), cp.BUILDING_TYPES),
                        cp.script_value_numbers(MOD, vanilla_root(ROOT, PROJECT)))
    for name, demand, category, _, pop_type, size in calls:
        assert name in known, name
        # the workers one level needs (Jan 2026-11-09: no building where nobody can work in it)
        assert (pop_type, float(size)) == staff.get(name, ("peasants", 0.0)), name
        assert f"pp_cplan_goods_here_{demand} = {{" in plan_triggers, demand
        assert f"pp_cplan_cd_{demand} = {{" in plan_values, demand
        assert f"pp_cplan_eff_{category} = {{" in plan_values, category
    hand = _code(MOD / lpf.HAND_EFFECTS)
    for name in ("pp_lprof_expand", "pp_lprof_start", "pp_lprof_try"):
        body = _block(hand, name)
        assert "location_and_owner_can_build = { building_type = $type$ }" in body, name
        assert "pp_cplan_goods_here_$demand$ = yes" in body, name
        assert "pp_cplan_staff = { type = $pt$ size = $sz$ }" in body, name
    # every construction goes through the plan's budget check and its construct (ledger, never twice while queued)
    build = _block(hand, "pp_lprof_build")
    assert f"pp_cplan_construct_scoped = {{ why = {lpf.WHY_PROFILE} }}" in build
    # the plan's construct checks the group's purse; a level it does not start for gold is the gold state (107 -> 7),
    # one the market limit stops its own (106 -> 10)
    assert "limit = { scope:pp_cplan_country = { has_variable = pp_cplan_wait } }\n\t\tpp_lprof_fail = { r = 107 }" in build
    assert "limit = { scope:pp_cplan_country = { has_variable = pp_cplan_mlim } }\n\t\tpp_lprof_fail = { r = 106 }" in build
    assert build.index("has_variable = pp_cplan_wait") < build.index("has_variable = pp_cplan_mlim")
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
    assert len(rows) == 11  # + pp_lprof_global, pp_lprof_examples (2026-11-09)
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
    expected = {f"s{k}" for k in range(1, config.slots + 1)} | {"none", "icon", "up", "down", lpf.EDITED, lpf.NEXT}
    expected |= {f"r{r}" for r in range(1, config.rules + 1)} | {f"c{n}" for n in range(1, len(config.colors) + 1)}
    expected |= {item.key for item in result.items} | {symbol.key for symbol in config.symbols}
    assert expected <= declared
    for path in (MOD / lpf.EFFECTS, MOD / lpf.HAND_EFFECTS):
        for flag in re.findall(r"flag:(\w+)", _code(path)):
            assert flag in declared, flag
    run = _block(_code(PLAN_EFFECTS), "pp_cplan_run")
    never = run[run.index("always = no"):]
    for scope in ("pp_slot", "pp_key", "pp_dir", "pp_field", "pp_col"):
        assert f"save_scope_as = {scope}" in never, scope
    assert "pp_lprof_declare_flags = yes" in never


def test_global_rules_read_the_profile() -> None:
    """A profile takes from the global rules only what it sets (Jan 2026-11-09): its rules' targets and the groups it
    switches off; the rest build there too. The plan's group checks read the location's copy: every switch and every
    target trigger reaches them. The profile group takes its part of the month's budget, and the first rule that starts
    a construction ends the location's month."""
    config = lpf.load_config(PROJECT)
    plan = _code(PLAN_TRIGGERS) + _code(PLAN_EFFECTS) + _code(MOD / cp.EFFECTS)
    # the Towns and Buildings group has its own files (construction_plan_country.py)
    for folder in ("scripted_triggers", "scripted_effects"):
        plan += "".join(_code(path) for path in sorted((COMMON / folder).glob("pp_construction_plan_country*.txt")))
    fields = lpf.profile_fields(config)
    for name, _, _ in lpf.GLOBAL_GROUPS:
        assert name in fields, name  # the location copy carries the switch
        assert f"has_variable = pp_lprof_{name}" in plan, f"no global group reads pp_lprof_{name}"
    for trigger in ("pp_lprof_food_target = yes", "pp_lprof_has_good = { g = ", "pp_lprof_has_category = { c = "):
        assert trigger in plan, f"no global group reads {trigger}"
    assert "pp_lprof_group_n" in _code(PLAN_VALUES) + _code(MOD / cp.VALUES), "the profile group counts as a rule group"
    # the triggers read the rules' targets in the location's copy (a category is a flag, compared as vanilla does)
    generated = _code(MOD / lpf.TRIGGERS)
    has_good, has_category = _block(generated, "pp_lprof_has_good"), _block(generated, "pp_lprof_has_category")
    for r in range(1, config.rules + 1):
        assert f"AND = {{ has_variable = pp_lprof_r{r}_g var:pp_lprof_r{r}_g = goods:$g$ }}" in has_good, r
        assert f"AND = {{ has_variable = pp_lprof_r{r}_c var:pp_lprof_r{r}_c = flag:$c$ }}" in has_category, r
        assert f"r{r}_c" in fields, r
    for name in ("pp_lprof_has_good", "pp_lprof_has_category", "pp_lprof_food_target"):
        assert _block(generated, name).startswith("\n\thas_variable = pp_lprof\n"), name
    assert "goods:wheat" in _block(generated, "pp_lprof_food_target")
    hand = _code(MOD / lpf.HAND_EFFECTS)
    group = _block(hand, "pp_lprof_run")
    assert "pp_cplan_group_start = { why = 105 }" in group
    assert "pp_cplan_profiles_w > 0" in group  # the profiles' weight bar at 0 switches them off
    assert "save_temporary_scope_value_as = { name = pp_cplan_free_peasants value = pp_cplan_free_peasants_here }" in group
    assert "pp_lprof_location_rules = yes" in group
    assert "owner ?= scope:pp_cplan_country" in _block(hand, "pp_lprof_gather")  # only the country's own locations
    # the first rule or mark that starts a construction ends the location for the month: the mark is cleared once a
    # location (by the run, not between the profile's rules and the location's marks), every later one waits (109)
    walk = group[group.index("ordered_in_list"):]
    assert walk.index("remove_variable = pp_cplan_hit") < walk.index("pp_lprof_location_rules = yes")
    opened = _block(hand, "pp_lprof_open")
    assert "has_variable = pp_cplan_hit" in opened and "value = 109" in opened
    assert "pp_lprof_open = yes" in _block(hand, "pp_lprof_rule")
    assert "pp_cplan_hit" not in _block(_code(MOD / lpf.EFFECTS), "pp_lprof_location_rules")
    assert "pp_cplan_hit" not in _block(_code(MOD / lpf.EFFECTS), "pp_lplan_location_marks")
    # a profile and the Location Plan's marks are all a location carries: no other per-location plan setting
    for path in OWN_FILES:
        text = _code(path)
        assert "pp_cplan_mode" not in text and "pp_cplan_own" not in text, path.name


def test_only_the_player() -> None:
    """The pass runs only inside the plan's monthly pass (human countries with the plan on); no on_action of its own."""
    for path in (COMMON / "on_action").glob("*.txt"):
        assert "pp_lprof" not in _read(path), path.name
    callers = [path.name for path in (COMMON / "scripted_effects").glob("*.txt") if "pp_lprof_run = yes" in _code(path)]
    assert callers == ["pp_construction_plan.txt"]


PER_SLOT = ("pp_lprof_resolve", "pp_lprof_resolve_free", "pp_lprof_read", "pp_lprof_write", "pp_lprof_declare_flags")


def test_slot_and_rule_counts_follow_the_config() -> None:
    """Only the slot resolve and the slot read / write are written per slot (once each); a rule count shows in the
    location's rule list and the copies."""
    config = lpf.load_config(PROJECT)
    slots = [str(k) for k in range(1, config.slots + 1)]
    effects = _code(MOD / lpf.EFFECTS)
    rules = _block(effects, "pp_lprof_location_rules")
    assert re.findall(r"pp_lprof_rule = \{ r = (\d+) \}", rules) == [str(r) for r in range(1, config.rules + 1)]
    resolve = _block(effects, "pp_lprof_resolve")
    assert re.findall(r"flag:s(\d+) = \{ set_variable = \{ name = pp_lprof_k value = (\d+) \} \}", resolve) == [
        (k, str(100 + int(k))) for k in slots]
    assert "scope:pp_slot = flag:e" in resolve and "from = pp_lprof_e_k to = pp_lprof_k" in resolve
    free = _block(effects, "pp_lprof_resolve_free")
    assert re.findall(r"has_variable = pp_lprof_(\d+)_on \} \} set_variable = \{ name = pp_lprof_k value = (\d+) \}", free) == [
        (k, str(100 + int(k))) for k in slots]
    for name, callee in (("pp_lprof_read", "pp_lprof_read_slot"), ("pp_lprof_write", "pp_lprof_write_slot")):
        chain = re.findall(rf"var:pp_lprof_k < ([0-9.]+) \}} {callee} = \{{ k = (\d+) \}}", _block(effects, name))
        assert [k for _, k in chain] == slots, name
        assert all(float(bound) == 100 + int(k) + 0.5 for bound, k in chain), name
    # no other generated or hand-written effect names a slot
    hand = _code(MOD / lpf.HAND_EFFECTS)
    for text in (effects, hand):
        for match in re.finditer(r"^([a-z_][a-z0-9_]*) = \{", text, re.MULTILINE):
            body = _block(text, match.group(1))
            if match.group(1) not in PER_SLOT:
                assert not re.search(r"pp_lprof_\d+_|flag:s\d", body), f"{match.group(1)} names a slot"
    colors = re.findall(r"flag:c(\d+) = ", _block(effects, "pp_lprof_color_staged"))
    assert colors == [str(n) for n in range(1, len(config.colors) + 1)]
    assert "value = goods:lumber" in _block(hand, "pp_lprof_stage_new")
    assert lpf.DEFAULT_ICON == "lumber"
    values = _code(MOD / lpf.VALUES)
    new_color = _block(values, "pp_lprof_new_color")
    subtract = int(re.search(r"subtract = (\d+)", new_color).group(1))
    modulo = int(re.search(r"modulo = (\d+)", new_color).group(1))
    add = int(re.search(r"add = (\d+)", new_color).group(1))
    for k in range(1, config.slots + 1):
        assert (100 + k - subtract) % modulo + add == lpf.color_value(config, k), k
    free_value = _block(values, "pp_lprof_first_free")
    assert re.findall(r"has_variable = pp_lprof_(\d+)_on", free_value) == slots
    assert re.findall(r"has_variable = pp_lprof_(\d+)_on", _block(values, "pp_lprof_used_n")) == slots
    for r in range(1, config.rules + 1):
        assert f"pp_lprof_r{r}_st_n = {{" in values


def test_flag_frames_follow_one_order() -> None:
    """A flag's frame number (pp_lprof_key_frame, stored beside icon flags and category rule targets) is its place in
    lpf.frame_flags, the order of the GUI's flag strip: the building categories, then the symbols."""
    config = lpf.load_config(PROJECT)
    chain = re.findall(r"scope:pp_key = flag:(\w+) \} value = (\d+) \}", _block(_code(MOD / lpf.VALUES), "pp_lprof_key_frame"))
    expected = lpf.frame_flags(lp.load_config(PROJECT).categories, config)
    assert [flag for flag, _ in chain] == expected
    assert [int(number) for _, number in chain] == list(range(101, 101 + len(expected)))
    assert expected[:len(lp.load_config(PROJECT).categories)] == list(lp.load_config(PROJECT).categories)


def test_pass_reads_the_location_copies() -> None:
    """The monthly pass reads only the location's copy of its profile: no slot, no country variable of a profile."""
    hand = _code(MOD / lpf.HAND_EFFECTS)
    effects = _code(MOD / lpf.EFFECTS)
    rule = _block(hand, "pp_lprof_rule")
    for part in ("has_variable = pp_lprof_r$r$_g", "has_variable = pp_lprof_r$r$_c", "value = var:pp_lprof_r$r$_pb",
                 "pp_lprof_goods_target = { v = pp_lprof_r$r$_g }", "pp_lprof_category_target = { v = pp_lprof_r$r$_c }"):
        assert part in rule, part
    for name in ("pp_lprof_goods_target", "pp_lprof_category_target"):
        assert "trigger = var:$v$" in _block(effects, name), name
    for text in (rule, _block(effects, "pp_lprof_location_rules"), _block(hand, "pp_lprof_run")):
        assert "$k$" not in text and not re.search(r"pp_lprof_\d", text)
        assert "scope:pp_cplan_country.var:pp_lprof" not in text


def test_every_edit_passes_the_profile_on() -> None:
    """Copy on edit: every button that changes a slot writes it back and gives the edit buffer and every location with
    the slot the new data; assign gives the location the copy, and every way a profile leaves a location takes the copy
    away."""
    config = lpf.load_config(PROJECT)
    hand = _code(MOD / lpf.HAND_EFFECTS)
    effects = _code(MOD / lpf.EFFECTS)
    guis = _read(MOD / lpf.SCRIPTED_GUIS)
    staged = {"pp_lprof_set_do": "pp_lprof_set_staged", "pp_lprof_color_do": "pp_lprof_color_staged",
              "pp_lprof_payback_do": "pp_lprof_payback_staged", "pp_lprof_rule_clear_do": "pp_lprof_rule_clear_staged",
              "pp_lprof_rule_move_do": "pp_lprof_rule_move_staged"}
    for do, op in staged.items():
        assert f"pp_lprof_edit = {{ do = {op} }}" in _block(hand, do), do
        body = _block(effects, op)
        assert not re.search(r"pp_lprof_(?:\d+|e)_", body), f"{op} edits only the staged copy"
    edit = _block(hand, "pp_lprof_edit")
    order = [edit.index(part) for part in ("pp_lprof_resolve = yes", "pp_lprof_read = yes", "$do$ = yes",
                                           "pp_lprof_commit = yes", "pp_lprof_unstage = yes")]
    assert order == sorted(order)
    commit = _block(hand, "pp_lprof_commit")
    assert commit.index("pp_lprof_write = yes") < commit.index("pp_lprof_publish = yes")
    publish = _block(hand, "pp_lprof_publish")
    assert "pp_lprof_copy_profile = { from = pp_lprof_s to = pp_lprof_e }" in publish
    assert "set_variable = { name = pp_lprof_e_k value = var:pp_lprof_k }" in publish
    loop = publish[publish.index("every_in_list"):]
    assert "var:pp_lprof > scope:pp_lprof_lo" in loop and "pp_lprof_copy_profile = { from = pp_lprof_s to = pp_lprof }" in loop
    assert "pp_lprof_commit = yes" in _block(hand, "pp_lprof_new_do")
    assert "pp_lprof_publish = yes" in _block(hand, "pp_lprof_select_do")
    assert "pp_lprof_copy_profile = { from = pp_lprof_s to = pp_lprof }" in _block(hand, "pp_lprof_assign_staged")
    delete = _block(hand, "pp_lprof_delete_staged")
    assert "pp_lprof_write = yes" in delete and "pp_lprof_drop_gone = yes" in delete
    assert "pp_lprof_clear_copies = { p = pp_lprof_e }" in delete
    clear = _block(hand, "pp_lprof_clear_location")
    assert "remove_variable = pp_lprof" in clear and "pp_lprof_clear_copies = { p = pp_lprof }" in clear
    for name in ("pp_lprof_unassign", "pp_lprof_drop_gone", "pp_lprof_cleanup"):
        assert "pp_lprof_clear_location = yes" in _block(hand, name), name
    # a copy carries every field of a slot, and clearing one removes the same fields
    fields = lpf.profile_fields(config)
    copy = _block(effects, "pp_lprof_copy_profile")
    pulled = re.findall(r"pp_lprof_pull_(\w+) = \{ from = \$from\$_(\w+) to = \$to\$_(\w+) \}", copy)
    assert [source for _, source, _ in pulled] == fields and all(source == target for _, source, target in pulled)
    assert {kind for kind, source, _ in pulled if source.endswith("_c")} == {"cat"}
    kinds = dict((source, kind) for kind, source, _ in pulled)
    assert kinds["ic"] == "icon" and kinds["in"] == "n" and kinds["col"] == "n"
    frames = re.findall(r"pp_lprof_pull_n = \{ from = \$from\$_(\w+) to = \$to\$_\1 \}", _block(effects, "pp_lprof_copy_frames"))
    assert frames == lpf.frame_fields(config) == [f"r{r}_cn" for r in range(1, config.rules + 1)]
    assert re.findall(r"remove_variable = \$p\$_(\w+)", _block(effects, "pp_lprof_clear_copies")) == fields
    assert re.findall(r"remove_variable = \$p\$_(\w+)", _block(effects, "pp_lprof_clear_frames")) == frames
    assert "pp_lprof_clear_frames = { p = pp_lprof }" not in _code(MOD / lpf.HAND_EFFECTS), "a location copy has no frame numbers"
    for name in ("pp_lprof_read_slot", "pp_lprof_write_slot"):
        assert "pp_lprof_copy_profile = { from = " in _block(hand, name), name
        assert "pp_lprof_copy_frames = { from = " in _block(hand, name), name
    assert "pp_lprof_copy_frames = { from = pp_lprof_s to = pp_lprof_e }" in publish
    # the GUI draws a flag only by its frame number: every place that sets a flag sets its number beside it
    for name, flags in (("pp_lprof_set_icon", "OR = {"), ("pp_lprof_set_target", "pp_lprof_category_key = yes")):
        body = _block(hand, name)
        assert flags in body and "set_variable = { name = $n$ value = pp_lprof_key_frame }" in body, name
        assert "remove_variable = $n$" in body, name
    staged_set = _block(effects, "pp_lprof_set_staged")
    assert "n = pp_lprof_s_in }" in staged_set
    for r in range(1, config.rules + 1):
        assert f"n = pp_lprof_s_r{r}_cn }}" in staged_set
        assert f"remove_variable = pp_lprof_s_r{r}_cn" in _block(effects, "pp_lprof_rule_clear_staged")
    swap = _block(hand, "pp_lprof_swap_rules")
    assert "from = pp_lprof_s_r$a$_cn" in swap and "to = pp_lprof_s_r$b$_cn" in swap
    # flags are compared (switch), never copied as a value; every icon flag and category reaches its copy
    icon = _block(effects, "pp_lprof_pull_icon")
    for flag in list(lp.load_config(PROJECT).categories) + [symbol.key for symbol in config.symbols]:
        assert f"flag:{flag} = {{ set_variable = {{ name = $to$ value = flag:{flag} }} }}" in icon, flag
    for category in lp.load_config(PROJECT).categories:
        assert f"flag:{category} = {{ set_variable" in _block(effects, "pp_lprof_pull_cat"), category
    # the edit buffer is what the editor's buttons pass (e) and new profiles use the first free slot (next)
    assert "pp_lprof_select = {" in guis and "pp_lprof_select_do = yes" in _block(guis, "pp_lprof_select")
    assert "pp_lprof_resolve_free = yes" in _block(hand, "pp_lprof_new_do")


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
    # a symbol is only an icon: it is a symbol key (pp_lprof_set_icon takes it), never a category or a good
    symbols = _block(_code(MOD / lpf.TRIGGERS), "pp_lprof_symbol_key")
    config = lpf.load_config(PROJECT)
    assert config.symbols
    for symbol in config.symbols:
        assert symbol.key == lpf.SYMBOL_PREFIX + symbol.name
        assert f"scope:pp_key = flag:{symbol.key}" in symbols, symbol.key
        assert f"flag:{symbol.key}" not in category_key + keys + categories, symbol.key
    assert {symbol.key for symbol in config.symbols}.isdisjoint(item.key for item in result.items)
    hand = _code(MOD / lpf.HAND_EFFECTS)
    assert "pp_lprof_symbol_key = yes" in _block(hand, "pp_lprof_set_icon")
    assert "pp_lprof_symbol_key" not in _block(hand, "pp_lprof_set_target")


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
    for n in range(0, len(lpf.STATES) + 1):
        assert f"PP_LPROF_ST_{n}" in keys, n
        assert not re.search(r"\d", keys[f"PP_LPROF_ST_{n}"]), "no numbers in player text"
    assert "PP_CPLAN_WHY_PROFILE" in (MOD / "main_menu/localization/english/pp_construction_plan_l_english.yml").read_text(encoding="utf-8-sig")
    finish = _block(_code(MOD / lpf.HAND_EFFECTS), "pp_lprof_finish")
    for rank, state in lpf.FAIL_STATE.items():
        if rank == 101:
            assert re.search(rf"else = \{{\s*set_variable = \{{ name = \$st\$ value = {100 + state} \}}", finish), rank
        else:
            assert re.search(rf"var:pp_lprof_fail > {rank - 0.5:g} \}}\n\t\tset_variable = \{{ name = \$st\$ value = {100 + state} \}}", finish), rank
    states = {int(n) - 100 for n in re.findall(r"name = (?:pp_lprof_st|\$st\$) value = (1\d\d)", _code(MOD / lpf.HAND_EFFECTS) + _code(MOD / lpf.EFFECTS))}
    assert states == set(lpf.STATES), "every state is written somewhere, and no other"


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
    assert "set_variable = { name = $est$ value = var:pp_lprof_best }" in finish
    assert "pp_lprof_finish = { st = pp_lprof_r$r$_st est = pp_lprof_r$r$_est }" in _block(code, "pp_lprof_rule")
    assert "remove_variable = pp_lprof_best" in _block(code, "pp_lprof_open")  # a rule starts without an old payback
    loc = (MOD / "main_menu/localization/english/pp_location_profiles_gui_l_english.yml").read_text(encoding="utf-8-sig")
    for r in range(1, lpf.load_config(PROJECT).rules + 1):
        assert f"'PP_LPROF_UI_EST_{r}'" in loc and f"pp_lprof_r{r}_est" in loc


def test_example_profiles_use_the_buttons_effects() -> None:
    """Jan 2026-11-09: ready profiles to look at. Each example is made in the next free slot with the buttons own
    effects; the editor offers them while the country has no profile."""
    config = lpf.load_config(PROJECT)
    assert len(config.examples) >= 5
    body = _block(_code(MOD / lpf.EFFECTS), "pp_lprof_examples_do")
    assert body.count("pp_lprof_new_do = yes") == len(config.examples)
    assert body.count("limit = { pp_lprof_first_free > 0 }") == len(config.examples)
    # a payback of 20 years from "any": down to 50, 40, 30, 20
    steps = config.payback_steps
    assert len(steps) - steps.index(20) == 4
    hands_off = [example for example in config.examples if not example.rules]
    assert hands_off and set(hands_off[0].off) == {group for _, _, group in lpf.GLOBAL_GROUPS}
    for _, flag, _ in lpf.GLOBAL_GROUPS:
        assert f"value = flag:{flag} }}" in body
    # off names a plan group; the old goods group is the businesses group now (2026-11-09)
    assert "businesses" in {group for _, _, group in lpf.GLOBAL_GROUPS}
    wrong = dataclasses.replace(config, examples=(lpf.Example(lpf.DEFAULT_ICON, 1, off=("goods",)),))
    with pytest.raises(ValueError, match="unknown global group goods"):
        lpf.render_examples(lpf.profile_items(ROOT, PROJECT), wrong)
    editor = _code(MOD / "in_game/gui/pp_location_profiles.gui")
    editor = editor[editor.index("type pp_lprof_editor_tab = vbox"):editor.index('name = "pp_location_profiles_palette"')]
    assert "GetScriptedGui(\x27pp_lprof_examples\x27)" in editor


# ---------------------------------------------------------------------------------------------------------------------
# the location's marks (Jan 2026-11-10: "in this location, also expand wheat"): the Location Plan's items as build picks

PLAN_HAND_EFFECTS = COMMON / "scripted_effects/pp_location_plan.txt"
PLAN_GENERATED_EFFECTS = MOD / lp.EFFECTS
PLAN_SCRIPTED_GUIS = COMMON / "scripted_guis/pp_location_plan.txt"


def test_marks_run_the_targets_of_the_profile_rules() -> None:
    """A marked item builds exactly what a profile rule with that target builds: its mark calls the same generated
    pp_lprof_t_<target> the rule dispatch calls, through the same start (pp_lprof_open) and end (pp_lprof_finish); no
    second copy of the target machinery. The marks run in the picker's order, after the profile's rules."""
    result, _ = _build()
    effects = _code(MOD / lpf.EFFECTS)
    hand = _code(MOD / lpf.HAND_EFFECTS)
    marks = _block(effects, "pp_lplan_location_marks")
    goods_dispatch = _block(effects, "pp_lprof_goods_target")
    category_dispatch = _block(effects, "pp_lprof_category_target")
    plan_items = lp.plan_items(ROOT, lp.load_config(PROJECT))
    assert [item.key for item in lpf.mark_items(result.items)] == [item.key for item in plan_items], "the picker's items"
    lines = re.findall(r"^\t(pp_lplan_mark(?:_none)? = \{ [^\n]* \})$", marks, re.MULTILINE)
    expected = []
    for item in plan_items:
        if result.targets.get(item.key):
            expected.append(f"pp_lplan_mark = {{ v = {item.suffix} do = pp_lprof_t_{item.key} }}")
            dispatch, scope = (goods_dispatch, "goods") if item.kind == "good" else (category_dispatch, "flag")
            assert f"{scope}:{item.key} = {{ pp_lprof_t_{item.key} = yes }}" in dispatch, item.key  # the rule's target
            assert re.search(rf"^pp_lprof_t_{item.key} = \{{", effects, re.MULTILINE), item.key
        else:
            expected.append(f"pp_lplan_mark_none = {{ v = {item.suffix} }}")
    assert lines == expected, "one line per item, in the picker's order"
    assert sum(1 for line in expected if "_none" in line) <= 2, "nearly every item has buildings"
    # the mark: only when set; start, the target, end; its own state variables
    mark = _block(hand, "pp_lplan_mark")
    assert "limit = { has_variable = pp_lplan_$v$ }" in mark
    assert mark.index("pp_lprof_open = yes") < mark.index("$do$ = yes") < mark.index("pp_lprof_finish = {")
    assert "limit = { NOT = { has_variable = pp_lprof_st } }" in mark  # nothing is tried while it waits
    assert "pp_lprof_finish = { st = pp_lplan_st_$v$ est = pp_lplan_est_$v$ }" in mark
    none = _block(hand, "pp_lplan_mark_none")
    assert "pp_lprof_finish = { st = pp_lplan_st_$v$ est = pp_lplan_est_$v$ }" in none and "$do$" not in none
    # no second copy of what a target does: the candidates' effects are called by the generated targets only
    for name in ("pp_lprof_expand", "pp_lprof_start", "pp_lprof_try", "pp_lprof_build", "pp_cplan_construct_scoped"):
        assert f"{name} = " not in mark + none + marks, name
    # the profile's rules first, then the marks, one construction a month between them
    run = _block(hand, "pp_lprof_run")
    assert run.index("pp_lprof_location_rules = yes") < run.index("pp_lplan_location_marks = yes")
    assert "limit = { has_variable = pp_lplan_n }" in run and "limit = { has_variable = pp_lprof }" in run
    # the item variables of the two modules agree
    wheat = next(item for item in plan_items if item.key == "wheat")
    assert (wheat.var, wheat.state, wheat.est) == ("pp_lplan_g_wheat", "pp_lplan_st_g_wheat", "pp_lplan_est_g_wheat")
    trade = next(item for item in plan_items if item.key == "trade_category")
    assert trade.var == "pp_lplan_c_trade_category" and trade.state == "pp_lplan_st_c_trade_category"


def test_marks_use_the_business_line() -> None:
    """A mark's payback limit is the player's global Businesses line ("payback within N years"), read in the pass."""
    marks = _block(_code(MOD / lpf.EFFECTS), "pp_lplan_location_marks")
    assert lpf.MARK_LIMIT == "pp_cplan_business_years"
    saved = re.search(r"scope:pp_cplan_country = \{\s*save_temporary_scope_value_as = \{ name = pp_lprof_pb value = \{ value = (\w+) add = 100 \} \}\s*\}", marks)
    assert saved and saved.group(1) == lpf.MARK_LIMIT, "the limit is read on the country, + 100 like a rule's"
    assert marks.index("name = pp_lprof_pb") < marks.index("pp_lplan_mark = {")
    line = _block(_code(MOD / cp.VALUES), lpf.MARK_LIMIT)
    assert "has_variable = pp_cplan_biz" in line and "value = var:pp_cplan_biz" in line, "the Businesses line's setting"
    # the targets compare the payback with that limit, and a mark has no limit of its own
    assert "pp_lprof_payback100 > scope:pp_lprof_pb" in _block(_code(MOD / lpf.HAND_EFFECTS), "pp_lprof_expand")
    for path in (MOD / lpf.EFFECTS, MOD / lpf.HAND_EFFECTS, PLAN_HAND_EFFECTS, PLAN_GENERATED_EFFECTS):
        assert not re.search(r"pp_lplan_\w*_pb\b", _code(path)), path.name
    # the ledger: a mark's construction is the profile group's (why 105), step 0
    assert f"save_temporary_scope_value_as = {{ name = pp_cplan_rs value = {lpf.WHY_MARK_STEP} }}" in marks
    assert "pp_cplan_construct_scoped = { why = 105 }" in _block(_code(MOD / lpf.HAND_EFFECTS), "pp_lprof_build")


def test_marked_locations_get_their_turn() -> None:
    """The pass finds the locations with marks: the country's list pp_lplan_locs (kept by every toggle) joins the
    profile locations for the pass, each location once; a location with marks and no profile is processed too. The
    list is cleaned like the profile list, and an own location keeps no marks the country did not set."""
    hand = _code(MOD / lpf.HAND_EFFECTS)
    run = _block(hand, "pp_lprof_run")
    gather = _block(hand, "pp_lprof_gather")
    assert run.index("pp_lplan_cleanup = yes") < run.index("pp_lprof_gather = yes") < run.index("ordered_in_list")
    assert "variable = pp_lprof_turns" in run and "clear_variable_list = pp_lprof_turns" in run
    assert gather.index("variable = pp_lprof_locs") < gather.index("variable = pp_lplan_locs")
    second = gather[gather.index("variable = pp_lplan_locs"):]
    for part in ("owner ?= scope:pp_cplan_country", "has_variable = pp_lplan_n", "NOT = { has_variable = pp_lprof }"):
        assert part in second, part  # a location with a profile and marks is taken once, from the profile list
    assert "add_to_variable_list = { name = pp_lprof_turns target = scope:pp_lprof_this }" in _block(hand, "pp_lprof_take_turn")
    # the group runs (and takes its part of the gold) while a location has a profile or a mark
    has = _block(_code(MOD / lpf.TRIGGERS), "pp_lprof_has_locations")
    assert "variable = pp_lprof_locs" in has and "variable = pp_lplan_locs" in has and "has_variable = pp_lplan_n" in has
    # the list follows the marks: every toggle and Clear keep it
    plan = _code(PLAN_HAND_EFFECTS)
    assert "pp_lplan_keep_list = yes" in _block(plan, "pp_lplan_flip")
    assert "pp_lplan_keep_list = yes" in _block(plan, "pp_lplan_clear_do")
    keep = _block(plan, "pp_lplan_keep_list")
    assert "add_to_variable_list = { name = pp_lplan_locs target = scope:pp_lplan_this }" in keep
    assert "remove_list_variable = { name = pp_lplan_locs target = scope:pp_lplan_this }" in keep
    assert "pp_lplan_clear_do = yes" in _code(PLAN_SCRIPTED_GUIS)
    # cleanup: entries without marks leave the list; an own location that is not on it loses its marks (and states)
    cleanup = _block(hand, "pp_lplan_cleanup")
    assert "limit = { NOT = { has_variable = pp_lplan_n } }" in cleanup
    assert "remove_list_variable = { name = pp_lplan_locs target = scope:pp_lprof_this }" in cleanup
    assert "every_owned_location" in cleanup and "pp_lplan_clear_all = yes" in cleanup
    clear = _block(_code(PLAN_GENERATED_EFFECTS), "pp_lplan_clear_all")
    flip = _block(plan, "pp_lplan_flip")
    for item in lp.plan_items(ROOT, lp.load_config(PROJECT)):
        for name in (item.var, item.state, item.est):
            assert f"remove_variable = {name}\n" in clear, name
    for name in ("pp_lplan_$v$", "pp_lplan_st_$v$", "pp_lplan_est_$v$"):
        assert f"remove_variable = {name}\n" in flip, name  # a mark removed takes its state along
    # every state variable that is removed is also set (the engine logs a variable that is only ever removed): each
    # item's mark line expands pp_lprof_finish with its own names
    finish = _block(hand, "pp_lprof_finish")
    assert "set_variable = { name = $st$ value" in finish and "set_variable = { name = $est$ value" in finish


def test_one_check_for_a_free_construction_site() -> None:
    """A rule or a mark waits while a construction is under way in the location; the check is the plan's own trigger,
    never a copy of it."""
    opened = _block(_code(MOD / lpf.HAND_EFFECTS), "pp_lprof_open")
    assert "limit = { NOT = { pp_cplan_site_free = yes } }" in opened and "value = 103" in opened
    assert re.search(r"^pp_cplan_site_free = \{", _read(PLAN_TRIGGERS), re.MULTILINE)
    for path in OWN_FILES + (PLAN_HAND_EFFECTS, PLAN_GENERATED_EFFECTS):
        assert "num_civil_constructions" not in _code(path), path.name
    # the workers check is the plan's too
    for name in ("pp_lprof_expand", "pp_lprof_start", "pp_lprof_try"):
        assert "pp_cplan_staff = { type = $pt$ size = $sz$ }" in _block(_code(MOD / lpf.HAND_EFFECTS), name), name


def test_towns_and_buildings_switch() -> None:
    """The fifth "Global rules here" switch: the Towns and Buildings group (pp_lprof_xc on the location, read by that
    group's own triggers); the example "hands off" switches it off too."""
    config = lpf.load_config(PROJECT)
    assert ("xc", "global_country", "country") in lpf.GLOBAL_GROUPS and len(lpf.GLOBAL_GROUPS) == 5
    effects = _code(MOD / lpf.EFFECTS)
    staged = _block(effects, "pp_lprof_global_staged")
    assert "flag:global_country = {" in staged and "set_variable = { name = pp_lprof_s_xc value = 101 }" in staged
    assert "pp_lprof_pull_n = { from = $from$_xc to = $to$_xc }" in _block(effects, "pp_lprof_copy_profile")
    assert "remove_variable = $p$_xc" in _block(effects, "pp_lprof_clear_copies")
    assert "xc" in lpf.profile_fields(config) and "global_country" in lpf.declared_flags(lpf.profile_items(ROOT, PROJECT), config)
    assert "pp_lprof_xc" in lpf.gui_only_variables(config)
    hands_off = [example for example in config.examples if not example.rules]
    assert hands_off and "country" in hands_off[0].off


def test_quick_candidates_follow_the_targets() -> None:
    """The location window's row offers, unmarked, the goods a standing building makes: per good a value that is 1
    while one of the buildings its mark would expand stands here and the good is not marked."""
    result, _ = _build()
    values = _code(MOD / lpf.VALUES)
    quick = lpf.quick_goods(result.items, result.targets)
    assert {"wheat", "lumber", "tools"} <= {item.key for item in quick}
    assert all(item.kind == "good" and item.key != lpf.LOGISTICS for item in quick)
    for item in quick:
        body = _block(values, f"pp_lplan_quick_{item.key}")
        assert f"NOT = {{ has_variable = {item.var} }}" in body, item.key
        assert re.findall(r"has_building = building_type:(\w+)", body) == [c.name for c in result.targets[item.key]], item.key
    assert len(re.findall(r"^pp_lplan_quick_(?!room_)\w+ = \{", values, re.MULTILINE)) == len(quick)


def _quick_row(values: str, chunks: list[list[lp.Item]], marked: int, standing: set[str]) -> int:
    """Tiles the row shows for a location with ``marked`` marks whose buildings make the unmarked goods ``standing``,
    by the generated room values."""
    shown, room = marked, None
    for number, chunk in enumerate(chunks, 1):
        body = _block(values, f"pp_lplan_quick_room_{number}")
        if number == 1:
            match = re.fullmatch(r"\s*value = (\d+)\s+subtract = pp_lplan_planned_n\s*", body)
            assert match, body
            room = int(match.group(1)) - marked
        else:
            assert f"value = pp_lplan_quick_room_{number - 1}\n" in body
            before = re.findall(r"subtract = pp_lplan_quick_(\w+)", body)
            assert before == [item.key for item in chunks[number - 2]], number
            room -= sum(1 for key in before if key in standing)
        if room > 0:
            shown += sum(1 for item in chunk if item.key in standing)
    return shown


def test_quick_candidates_never_overflow_the_row() -> None:
    """The row holds QUICK_ROW tiles: the marks, then the candidates chunk by chunk while a whole chunk still fits."""
    import random

    result, _ = _build()
    values = _code(MOD / lpf.VALUES)
    chunks = lpf.quick_chunks(result.items, result.targets)
    assert all(len(chunk) <= lpf.QUICK_CHUNK for chunk in chunks) and lpf.QUICK_CHUNK < lpf.QUICK_ROW
    keys = [item.key for chunk in chunks for item in chunk]
    assert _quick_row(values, chunks, 0, set()) == 0
    assert _quick_row(values, chunks, 0, set(keys[-3:])) == 3, "a few candidates show wherever they sit in the list"
    assert _quick_row(values, chunks, 2, {keys[0], keys[40]}) == 4
    rng = random.Random(7)
    for _ in range(300):
        marked = rng.randint(0, lpf.QUICK_ROW)
        standing = set(rng.sample(keys, rng.randint(0, len(keys))))
        shown = _quick_row(values, chunks, marked, standing)
        assert shown <= max(marked, lpf.QUICK_ROW), (marked, len(standing))
        if marked + len(standing) <= lpf.QUICK_ROW - lpf.QUICK_CHUNK + 1:
            assert shown == marked + len(standing), "nothing is hidden while the row has room"
        elif marked <= lpf.QUICK_ROW - lpf.QUICK_CHUNK:
            assert shown > lpf.QUICK_ROW - 2 * lpf.QUICK_CHUNK, "a cut row is still well filled"
