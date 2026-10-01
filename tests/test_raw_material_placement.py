"""Raw-material placement is the mod's (EU5 1.4): no good carries vanilla's location_potential, the Columbian exchange
actions test the mod's placement rules, and nothing is left of the setup-RGO keepers."""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import pytest
from eu5gameparser.domain.goods import load_goods_data
from eu5gameparser.load_order import load_merged_directory, load_profile

from prosper_or_perish_constructor.worldbuilder import modifiers as wb_modifiers
from prosper_or_perish_constructor.worldbuilder import raw_material_placement as rmp
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
LOAD_ORDER = ROOT / "constructor.load_order.toml"
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"


@cache
def _vanilla() -> Path:
    return vanilla_root(ROOT, PROJECT)


@cache
def _merged(folder: str) -> dict[str, object]:
    profile = load_profile("constructor", LOAD_ORDER)
    return {entry.key: entry for entry in load_merged_directory(profile, folder).entries}


def _actions_text() -> str:
    return (MOD_ROOT / rmp.ACTIONS_PATH).read_text(encoding="utf-8-sig")


def _triggers_text() -> str:
    return (MOD_ROOT / rmp.PLACEMENT_TRIGGERS_PATH).read_text(encoding="utf-8-sig")


def _vanilla_potential_goods() -> set[str]:
    goods: set[str] = set()
    for path in sorted((_vanilla() / "game" / rmp.GOODS_DIR).glob("*.txt")):
        goods |= set(rmp.goods_potentials(path.read_text(encoding="utf-8-sig")))
    return goods


# ------------------------------------------------------------------------------------------------------------ unit


def test_strip_removes_only_the_goods_own_potential(tmp_path: Path) -> None:
    goods = ("lumber = {\n\tmethod = forestry\n\tlocation_potential = {\n\t\tOR = {\n\t\t\tvegetation = forest\n\t\t}\n\t}\n"
             "\tdemand_add = { location_potential = 1 }\n}\n\nsalt = {\n\tmethod = gathering\n}\n")
    text, stripped = rmp.strip_goods_potentials(goods)
    assert stripped == ["lumber"]
    assert text == "lumber = {\n\tmethod = forestry\n\tdemand_add = { location_potential = 1 }\n}\n\nsalt = {\n\tmethod = gathering\n}\n"

    vanilla = tmp_path / "vanilla"
    (vanilla / "game" / rmp.GOODS_DIR).mkdir(parents=True)
    (vanilla / "game" / rmp.GOODS_DIR / "00_raw_materials.txt").write_text(goods, encoding="utf-8-sig")
    (vanilla / "game" / rmp.GOODS_DIR / "02_produced_goods.txt").write_text("tools = {\n\tmethod = x\n}\n", encoding="utf-8-sig")
    mod = tmp_path / "mod"
    stale = mod / rmp.GOODS_DIR / "02_produced_goods.txt"   # a generated copy an earlier build left behind
    stale.parent.mkdir(parents=True)
    stale.write_text("﻿" + rmp.GOODS_HEADER + "\ntools = {}\n", encoding="utf-8")
    assert rmp.write_goods_without_placement_rules(mod, vanilla) == {"00_raw_materials.txt": ["lumber"]}
    assert (mod / rmp.GOODS_DIR / "00_raw_materials.txt").read_text(encoding="utf-8-sig") == rmp.GOODS_HEADER + "\n" + text
    assert not stale.exists()
    # a hand-written mod file of a vanilla goods file's name would be replaced: refused
    (mod / rmp.GOODS_DIR / "00_raw_materials.txt").write_text("lumber = {}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hand-written"):
        rmp.write_goods_without_placement_rules(mod, vanilla)


def test_render_action_replaces_the_goods_test_and_adds_refresh_and_advances() -> None:
    body = ("move_nw_good_to_new_location = {\n\tvisible = {\n\t\tNOT = { raw_material ?= scope:target_good }\n"
            f"\t\t{rmp.VALIDITY_TEST}\n\t}}\n\teffect = {{\n\t\tscope:target_location ?= {{\n\t\t\t{rmp.CHANGE_LINE}\n\t\t}}\n\t}}\n}}")
    crops = [rmp.GatedCrop("maize", "pp_maize_native_country", "pp_maize_farm_advance_general")]
    out = rmp.render_action("move_nw_good_to_new_location", body, ["maize"], crops)
    assert out.startswith("TRY_REPLACE:move_nw_good_to_new_location = {")
    assert "is_goods_valid_for_location" not in out
    assert "\t\ttrigger_if = {\n\t\t\tlimit = { scope:target_good ?= goods:maize }\n\t\t\tpp_maize_placement_location = yes\n\t\t}" in out
    assert f"\t\t\t{rmp.CHANGE_LINE}\n\t\t\tpp_refresh_rgo_static_bonus = yes\n\t\t\tpp_refresh_fruit_orchard_eligibility = yes\n" in out
    assert "research_advance = advance_type:pp_maize_farm_advance_general" in out and out.endswith("\t\t}\n\t}\n}")
    with pytest.raises(ValueError, match="expected one"):
        rmp.render_action("x", body.replace(rmp.VALIDITY_TEST, ""), [], [])


# ------------------------------------------------------------------------------------------------- the mod as built


def test_goods_carry_no_location_potential_in_the_merged_result() -> None:
    vanilla_goods = _vanilla_potential_goods()
    assert len(vanilla_goods) >= 21 and {"lumber", "wheat", "maize", "wool"} <= vanilla_goods   # EU5 1.4 has 21
    goods = {row["name"]: row for row in load_goods_data(profile="constructor", load_order_path=LOAD_ORDER).goods.to_dicts()}
    carrying = sorted(name for name, row in goods.items() if '"location_potential"' in (row["data"] or ""))
    assert carrying == []
    for name in vanilla_goods:   # each comes from the mod's same-name copy, which replaced vanilla's file
        assert goods[name]["source_mod"] is not None, name


def test_goods_copies_are_current_with_vanilla() -> None:
    for path in sorted((_vanilla() / "game" / rmp.GOODS_DIR).glob("*.txt")):
        text, stripped = rmp.strip_goods_potentials(path.read_text(encoding="utf-8-sig"))
        copy = MOD_ROOT / rmp.GOODS_DIR / path.name
        if not stripped:
            assert not copy.exists() or not copy.read_text(encoding="utf-8-sig").startswith(rmp.GOODS_HEADER), path.name
            continue
        assert copy.read_text(encoding="utf-8-sig") == rmp.GOODS_HEADER + "\n" + text, f"{path.name}: rerun ppc build"


def test_no_setup_rgo_keeper_is_left() -> None:
    goods = set(_merged("goods"))
    assert not hasattr(wb_modifiers, "write_setup_rgo_keepers") and not hasattr(wb_modifiers, "SETUP_RGO_TRIGGERS_PATH")
    assert not (MOD_ROOT / "in_game/common/scripted_triggers/pp_wb_setup_rgos.txt").exists()
    for path in (MOD_ROOT / "in_game").rglob("*.txt"):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for name in re.findall(r"\bpp_wb_setup_([a-z_]+?)_location\b", text):
            assert name not in goods, f"{path.relative_to(MOD_ROOT)}: setup-RGO keeper pp_wb_setup_{name}_location"
        assert "# pp_wb_setup_" not in text, path.relative_to(MOD_ROOT)
    assert [f for f in _compat_files() if "/goods/" in f] == []   # the goods copies are raw_material_placement.py's


def _compat_files() -> list[str]:
    import tomllib

    return tomllib.loads(PROJECT.read_text(encoding="utf-8"))["worldbuilder"]["compat"]["vanilla_files"]


def test_move_good_actions_are_vanilla_with_our_placement_rules() -> None:
    assert _actions_text() == rmp.render_actions(_vanilla(), ROOT, _triggers_text()), "rerun ppc build (vanilla changed?)"
    actions = _merged("generic_actions")
    for name in rmp.ACTIONS:
        assert actions[name].source_mod is not None and actions[name].source_mode == "TRY_REPLACE", name
    # every vanilla object that asks for the goods' own potential is replaced by the mod, and the mod never asks
    from prosper_or_perish_constructor.worldbuilder.compat import top_level_objects

    users: dict[str, list[str]] = {}
    for path in sorted((_vanilla() / "game" / "in_game").rglob("*.txt")):
        if "trigger_localization" in path.parts:
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        if "is_goods_valid_for_location" in text:
            users[path.parent.name] = [n for n, a, b in top_level_objects(text) if "is_goods_valid_for_location" in text[a:b]]
    assert users == {"generic_actions": sorted(rmp.ACTIONS, key=list(rmp.ACTIONS).index)}, users
    for path in (MOD_ROOT / "in_game").rglob("*.txt"):
        code = "\n".join(line.split("#", 1)[0] for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines())
        assert "is_goods_valid_for_location" not in code, path


def test_every_good_vanilla_restricts_and_an_action_moves_has_our_rule() -> None:
    origins = rmp.goods_origins(_vanilla())
    rules = set(rmp.placement_goods(_triggers_text()))
    moved = {good for good, flags in origins.items() if flags}
    # lumber has no origin: no action moves it, so its vanilla potential only judged the setup RGOs
    assert _vanilla_potential_goods() & moved <= rules
    assert rules <= moved
    text = _actions_text()
    nw, ow = text.split("TRY_REPLACE:move_ow_good_to_new_location")
    for good in rules:
        block = nw if "origin_in_new_world" in origins[good] else ow
        assert f"limit = {{ scope:target_good ?= goods:{good} }}\n\t\t\t\tpp_{good}_placement_location = yes" in block, good


def test_every_trigger_effect_and_advance_the_actions_use_exists() -> None:
    triggers = set(_merged("scripted_triggers"))
    effects = set(_merged("scripted_effects"))
    advances = set(_merged("advances"))
    text = _actions_text() + "\n" + _triggers_text()
    code = "\n".join(line.split("#", 1)[0] for line in text.splitlines())
    used = set(re.findall(r"\b((?:pp|is_candidate_for)_[A-Za-z0-9_]+)\s*=\s*yes\b", code))
    assert used, "no scripted triggers found"
    missing = sorted(name for name in used if name not in triggers and name not in effects)
    assert missing == []
    assert {"pp_refresh_rgo_static_bonus", "pp_refresh_fruit_orchard_eligibility"} <= effects
    for advance in set(re.findall(r"advance_type:([A-Za-z0-9_]+)", code)) | set(re.findall(r"has_advance\s*=\s*([A-Za-z0-9_]+)", code)):
        assert advance in advances, advance
