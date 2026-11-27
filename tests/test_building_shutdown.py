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


def test_a_producer_gets_can_close_no_only_and_its_own_line_is_replaced() -> None:
    """2026-11-27 (Jan: nobody closes a production building): can_close = no alone, so the AI still subsidises."""
    body = "\n\tcan_close = yes\n\tai_forbid_shutdown = no\n\tmodifier = { can_close = yes }\n"
    locked = bs.set_flags(body, False, producer=True)
    assert locked.count("can_close = no # building_shutdown") == 1
    assert "\tcan_close = yes\n" not in locked and "modifier = { can_close = yes }" in locked
    assert "ai_forbid_shutdown = yes" not in locked and "ai_forbid_shutdown = no" in locked
    assert bs.set_flags(locked, False, producer=True) == locked


def test_no_production_building_can_be_closed() -> None:
    """Every blueprint building with a goods output carries can_close = no in the compiled mod, and none of them is
    taken out of the AI's subsidy pass by this step (ai_forbid_shutdown only where the blueprint sets it itself)."""
    from prosper_or_perish_constructor import building_footprint as bf
    from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

    project = ROOT / "constructor.toml"
    mod = ROOT / "mod" / "pp"
    vanilla = vanilla_root(ROOT, project)
    assert bs.check(ROOT, mod, project, vanilla) == []
    producers = bs.producers(ROOT, mod, vanilla)
    assert len(producers) > 200
    owners = bf.owner_blocks(mod, vanilla)
    for key in producers:
        block = owners[key]
        tops = bf._depth_zero_text(bf._read(block.path)[block.open + 1: block.close])
        assert bs._ANY_FLAG_RE["can_close"].search(tops).group("value") == "no", key
        assert "ai_forbid_shutdown = yes # building_shutdown" not in tops, key
    for key in ("glass_guild", "mason", "tannery", "charcoal_maker", "wheat_farm", "cookshop", "tavern"):
        assert key in producers, key


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
