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
    assert "change_variable = { name = pp_cplan_cap add = pp_cplan_group_share }" in group
    assert "owner ?= scope:pp_cplan_country" in group and "pp_lprof_location_rules = yes" in group
    # the first rule that starts a construction ends the location for the month
    rule = _block(hand, "pp_lprof_rule")
    assert "has_variable = pp_cplan_hit" in rule and "value = 109" in rule
    rules = _block(_code(MOD / lpf.EFFECTS), "pp_lprof_location_rules")
    assert rules.count("remove_variable = pp_cplan_hit") == 2
    # a profile is all a location carries: the profile side knows no other per-location plan setting
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
