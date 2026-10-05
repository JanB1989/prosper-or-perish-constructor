from __future__ import annotations

from pathlib import Path

from prosper_or_perish_constructor import building_shutdown as bs

ROOT = Path(__file__).resolve().parents[1]


def test_set_flags_adds_both_lines_once_and_removes_them_again() -> None:
    body = "\n\tprice = x\n\tmodifier = { can_close = no }\n"
    locked = bs.set_flags(body, True)
    assert locked.count("can_close = no # building_shutdown") == 1
    assert locked.count("ai_forbid_shutdown = yes # building_shutdown") == 1
    assert bs.set_flags(locked, True) == locked
    assert bs.set_flags(locked, False) == body


def test_set_flags_does_not_repeat_a_flag_the_definition_or_vanilla_sets() -> None:
    body = "\n\tai_forbid_shutdown = yes\n"
    locked = bs.set_flags(body, True)
    assert "ai_forbid_shutdown = yes # building_shutdown" not in locked
    assert "can_close = no # building_shutdown" in locked
    injected = bs.set_flags("\n\t# inject\n", True, inherited="\n\tcan_close = no\n")
    assert "can_close" not in injected and "ai_forbid_shutdown = yes # building_shutdown" in injected


def test_has_output_reads_unique_and_shared_methods() -> None:
    shared = {"shared_upkeep": False, "shared_goods": True}
    assert not bs.has_output("unique_production_methods = { m = { paper = 1 category = building_maintenance } }", shared)
    assert bs.has_output("unique_production_methods = { m = { paper = 1 produced = books output = 1 } }", shared)
    assert not bs.has_output("possible_production_methods = { shared_upkeep }", shared)
    assert bs.has_output("possible_production_methods = { shared_upkeep shared_goods }", shared)


def test_every_footprint_class_has_a_shutdown_rule() -> None:
    config = bs.load_config(ROOT / "constructor.toml")
    assert bs.validate(ROOT, config) == []
    used = {footprint for footprint, override, _ in bs.blueprint_rules(ROOT).values() if footprint and not override}
    assert used <= set(config.classes)
    # only military buildings stay closable (2026-10-05, Jan)
    assert {name for name, value in config.classes.items() if value == bs.KEEP} == {
        "farm_land", "technical", "barracks", "fortification", "military_grounds"}
