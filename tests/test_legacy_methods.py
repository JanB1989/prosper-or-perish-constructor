from __future__ import annotations

from pathlib import Path

import pytest

from prosper_or_perish_constructor import legacy_methods as lm
from prosper_or_perish_constructor import production_gate as pg
from prosper_or_perish_constructor import production_labour

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"


@pytest.fixture(scope="module")
def prices() -> dict[str, float]:
    return lm.load_prices(ROOT, PROJECT)


@pytest.fixture(scope="module")
def config() -> lm.LegacyConfig:
    return lm.load_config(PROJECT)


# ---------------------------------------------------------------- the planning rules


def method(name: str, goods: dict[str, float], output: float, produced: str = "tools") -> lm.MethodData:
    return lm.MethodData(name, produced, output, goods, {"category": "x_input"}, ())


def tier(building: str, *slots: list[lm.MethodData], unlocks: dict[str, frozenset[str]] | None = None) -> lm.Tier:
    return lm.Tier(building, Path(f"{building}.yml"), {"building": {"body": f"obsolete = x"}}, list(slots), unlocks or {})


PRICES = {"stone": 1.0, "iron": 3.5, "coal": 2.0, "copper": 3.0, "tin": 2.0, "tools": 3.25, "manual_labor": 1.0}


def test_a_recipe_the_next_tier_runs_on_fewer_goods_is_not_carried() -> None:
    guild = tier("guild", [method("pp_guild_iron", {"iron": 0.7, "coal": 0.2}, 1.0)])
    workshop = tier("workshop", [method("pp_workshop_iron", {"iron": 0.8}, 1.1)])
    recipes = lm.own_recipes(guild, 0, PRICES)
    assert lm.carry(list(recipes.values()), workshop, 0, 0.75) == []


def test_a_recipe_that_needs_other_goods_up_the_line_is_carried_with_the_decay() -> None:
    guild = tier("guild", [method("pp_guild_stone", {"stone": 0.6}, 0.25), method("pp_guild_iron", {"iron": 0.7}, 1.0)])
    workshop = tier("workshop", [method("pp_workshop_iron", {"iron": 0.8, "coal": 0.1}, 1.1)])
    carried = lm.carry(list(lm.own_recipes(guild, 0, PRICES).values()), workshop, 0, 0.75)
    by_method = {r.method: r for r in carried}
    assert set(by_method) == {"pp_guild_stone", "pp_guild_iron"}
    assert by_method["pp_guild_stone"].share_at(0.75) == pytest.approx(0.25 * 0.75)
    assert by_method["pp_guild_iron"].share_at(0.75) == pytest.approx(0.75)
    mill = tier("mill", [method("pp_mill_steel", {"coal": 1.0, "iron": 1.0}, 4.0)])
    again = lm.carry(carried, mill, 0, 0.75)
    assert {r.method: round(r.share_at(0.75), 6) for r in again} == {"pp_guild_stone": round(0.25 * 0.75**2, 6), "pp_guild_iron": 0.5625}


def test_an_own_method_behind_an_advance_does_not_cover_an_open_recipe() -> None:
    guild = tier("guild", [method("pp_guild_copper", {"copper": 0.5}, 0.55)])
    workshop = tier("workshop", [method("pp_workshop_copper", {"copper": 0.5}, 0.6)], unlocks={"pp_workshop_copper": frozenset({"metallurgy"})})
    carried = lm.carry(list(lm.own_recipes(guild, 0, PRICES).values()), workshop, 0, 0.75)
    assert [r.method for r in carried] == ["pp_guild_copper"]


def test_a_carried_recipe_dominated_by_a_cheaper_one_is_dropped() -> None:
    guild = tier(
        "guild",
        [method("pp_guild_copper", {"copper": 0.5}, 0.6), method("pp_guild_bronze", {"copper": 0.5, "tin": 0.05}, 0.6)],
    )
    workshop = tier("workshop", [method("pp_workshop_iron", {"iron": 0.8}, 1.1)])
    carried = lm.carry(list(lm.own_recipes(guild, 0, PRICES).values()), workshop, 0, 0.75)
    assert [r.method for r in carried] == ["pp_guild_copper"]  # bronze needs tin on top and makes no more


def test_the_legacy_method_keeps_the_references_margin_at_its_share_of_the_output() -> None:
    guild = tier("guild", [method("pp_guild_stone", {"stone": 0.6, "manual_labor": 0.1}, 0.25), method("pp_guild_iron", {"iron": 0.7}, 1.0)])
    reference = method("pp_workshop_iron", {"iron": 0.8, "manual_labor": 0.3}, 1.1)
    workshop = tier("workshop", [reference])
    recipe = lm.Recipe(frozenset({"stone"}), "guild", "pp_guild_stone", 0.25, 1, frozenset())
    config = lm.LegacyConfig(0.75, "(Old Ways)", "kept from the {origin}", {"tools": ("guild", "workshop")})
    legacy = lm.legacy_method(workshop, 0, recipe, reference, guild, config, PRICES, lm.Names({}, {}))
    assert legacy.name == "pp_workshop_legacy_stone"  # the origin method without its pp_<building>_ prefix
    assert legacy.value(PRICES) == pytest.approx(0.1875 * reference.value(PRICES), rel=0.03)
    ref_margin = reference.value(PRICES) / reference.cost(PRICES)
    assert legacy.value(PRICES) / legacy.cost(PRICES) == pytest.approx(ref_margin, rel=0.05)
    assert set(legacy.amounts) == {"stone", "manual_labor"}
    assert legacy.scalars == {"category": "x_input"}
    assert legacy.desc == "kept from the $guild$"


# ---------------------------------------------------------------- the repo


def test_every_line_is_an_obsolete_chain_and_the_blueprints_carry_their_legacy_methods() -> None:
    result = lm.apply(ROOT, PROJECT, write=False)
    assert result.problems == []
    assert [p.tier.path.name for p in result.changed] == [], "run uv run ppc legacy apply"
    assert len(result.methods) > 50


def test_no_upgrade_loses_a_recipe(config: lm.LegacyConfig, prices: dict[str, float]) -> None:
    assert lm.lost_recipes(ROOT, config, prices) == []


def test_legacy_methods_make_less_than_the_contemporary_method_at_its_margin(config: lm.LegacyConfig, prices: dict[str, float]) -> None:
    ratios = lm.method_ratio(ROOT, config, prices)
    assert ratios
    for building, name, value_ratio, margin_ratio in ratios:
        assert value_ratio <= config.decay + 0.02, (building, name, value_ratio)
        assert margin_ratio == pytest.approx(1.0, abs=0.06), (building, name, margin_ratio)


def test_legacy_methods_come_after_the_buildings_own_methods(config: lm.LegacyConfig) -> None:
    """A slot's first method is what new buildings run: it must never be an old recipe."""
    for buildings in config.lines.values():
        for building in buildings:
            for slot in lm.load_tier(ROOT, building).slots:
                kinds = [pg.is_legacy(m.name) for m in slot]
                assert kinds == sorted(kinds), (building, [m.name for m in slot])


def test_the_labour_pass_leaves_legacy_methods_to_their_origin() -> None:
    result = production_labour.apply(ROOT, PROJECT, write=False)
    assert not any(pg.is_legacy(plan.method.name) for plan in result.plans)


def test_old_recipes_keep_their_advance(config: lm.LegacyConfig) -> None:
    workshop = lm.load_tier(ROOT, "tools_workshop")
    assert workshop.unlocks["pp_tools_workshop_legacy_copper_tools_guild_maintenance"] == frozenset({"copperworking"})
    assert "pp_tools_workshop_legacy_stone_tools_guild_maintenance" not in workshop.unlocks


def test_the_combined_top_tiers_keep_the_two_slots_of_their_line() -> None:
    """Cannons, firearms and fine cloth: the workshops run barrels and shot (weaving and dyeing) in two slots, so the
    foundries, manufactories, factories and mills do too, and the old recipes carry slot by slot."""
    for building, side in (
        ("cannon_foundry", "pp_cannon_foundry_ammunition_maintenance"),
        ("cannons_factory", "pp_cannons_factory_ammunition_maintenance"),
        ("firearms_manufactory", "pp_firearms_manufactory_ammunition_maintenance"),
        ("firearms_factory", "pp_firearms_factory_ammunition_maintenance"),
        ("fine_cloth_mill", "pp_fine_cloth_mill_dyeing_maintenance"),
    ):
        t = lm.load_tier(ROOT, building)
        slots = [[m.name for m in t.slots[s]] for s in t.real_slots()]
        assert len(slots) == 2 and any(side in names for names in slots), (building, slots)


def test_the_leather_line_keeps_tar_in_every_tier() -> None:
    for building in ("tannery", "tanning_workshop", "tannery_manufactory", "tannery_mill"):
        t = lm.load_tier(ROOT, building)
        for s in t.real_slots():
            for m in t.own(s):
                assert "tar" in m.inputs, (building, m.name)
