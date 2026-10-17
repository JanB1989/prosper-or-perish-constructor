from __future__ import annotations

import re

import scripts.generate_noble_investment as gen
from scripts.generate_noble_investment import (
    BUILDING_TYPES,
    EFFECTS_PATH,
    MOD_ROOT,
    VALUES_PATH,
    Candidate,
    Method,
    building_definitions,
    candidates,
    field,
    render,
    render_values,
)

ON_ACTION_PATH = MOD_ROOT / "in_game" / "common" / "on_action" / "pp_noble_investment.txt"
CANDIDATE_LINE = re.compile(r"^\t# (\d+): (\w+) \((\w+), (\w+)\)$", re.M)
BUILD_BRANCH = re.compile(
    r"best_index = (\d+) \}\n\t\tconstruct_estate_building = \{ building_type = building_type:(\w+) "
    r"estate_type = estate_type:nobles_estate \}"
)


def braces_balance(text: str) -> bool:
    depth = 0
    for char in text:
        depth += (char == "{") - (char == "}")
        if depth < 0:
            return False
    return depth == 0


def generated_candidates() -> list[tuple[int, str, str, str]]:
    text = EFFECTS_PATH.read_text(encoding="utf-8-sig")
    return [(int(i), b, pop, good) for i, b, pop, good in CANDIDATE_LINE.findall(text)]


def test_generated_candidates_are_buildable_peasant_or_labourer_buildings() -> None:
    definitions = building_definitions(BUILDING_TYPES)
    found = generated_candidates()
    assert found, "no candidates generated"
    for _, building, pop_type, good in found:
        body = definitions[building]
        assert field(body, "pop_type") == pop_type in ("peasants", "laborers")
        assert field(body, "forbidden_for_estates") != "yes", building
        assert field(body, "is_special") != "yes", building
        assert good, building


def test_every_candidate_has_its_build_branch() -> None:
    text = EFFECTS_PATH.read_text(encoding="utf-8-sig")
    found = {index: building for index, building, _, _ in generated_candidates()}
    branches = {int(index): building for index, building in BUILD_BRANCH.findall(text)}
    assert sorted(found) == list(range(1, len(found) + 1))
    assert branches == found


def test_generated_scripts_are_balanced_and_wired() -> None:
    effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
    on_action = ON_ACTION_PATH.read_text(encoding="utf-8-sig")
    assert braces_balance(effects)
    assert braces_balance(on_action)
    assert "pp_noble_investment_monthly = {" in effects
    assert "pp_noble_investment_monthly = yes" in on_action
    # has_estate is a character trigger; in country scope the game errors and reads it as false (2026-10-16 test).
    assert "country_has_estate = estate_type:nobles_estate" in effects
    assert not re.search(r"(?<!country_)has_estate\s*=", effects)
    for value in re.findall(r"\b(pp_noble_investment_(?:reserve|price_multiplier|min_margin|min_unemployed))\b", effects):
        assert f"{value} = " in VALUES_PATH.read_text(encoding="utf-8-sig")


def candidate_blocks() -> dict[str, str]:
    text = EFFECTS_PATH.read_text(encoding="utf-8-sig")
    find = text[text.index("pp_noble_investment_find_best = {") : text.index("pp_noble_investment_build_best = {")]
    parts = re.split(r"^\t# \d+: (\w+) \(.*\)$", find, flags=re.M)
    return dict(zip(parts[1::2], parts[2::2]))


def test_buildings_unlocked_by_mod_advances_need_the_advance() -> None:
    # In game, can_build_building let the nobles start buildings the country had not researched (2026-10-16).
    blocks = candidate_blocks()
    unlocks: dict[str, set[str]] = {}
    for path in (MOD_ROOT / "in_game" / "common" / "advances").glob("*.txt"):
        for advance, body in gen.top_level_blocks(path.read_text(encoding="utf-8-sig")):
            for building in re.findall(r"\bunlock_building\s*=\s*(\w+)", body):
                unlocks.setdefault(building, set()).add(advance.split(":")[-1])
    gated = {b for b in blocks if b in unlocks}
    assert gated, "no mod-unlocked candidates found; the check is broken"
    for building in gated:
        checks = set(re.findall(r"has_advance = (\w+)", blocks[building]))
        assert checks & unlocks[building], building


def test_advance_unlocks_follow_load_order(tmp_path) -> None:
    game, mod = tmp_path / "game", tmp_path / "mod"
    (game / "in_game/common/advances").mkdir(parents=True)
    (game / "dlc/d1/in_game/common/advances").mkdir(parents=True)
    (mod / "in_game/common/advances").mkdir(parents=True)
    (game / "in_game/common/advances/a.txt").write_text(
        "adv_a = { unlock_building = mill }\nadv_b = { unlock_building = mine }\n", encoding="utf-8"
    )
    (game / "dlc/d1/in_game/common/advances/d.txt").write_text("adv_d = { unlock_building = mill }\n", encoding="utf-8")
    (mod / "in_game/common/advances/m.txt").write_text(
        "REPLACE:adv_b = { }\nTRY_INJECT:adv_a = { unlock_building = farm }\n", encoding="utf-8"
    )
    assert gen.advance_unlocks(game, mod) == {"mill": ("adv_a", "adv_d"), "farm": ("adv_a",)}
    gated = Candidate("mill", "laborers", "tools", advances=("adv_a", "adv_d"))
    assert gen.researched(gated).strip() == "OR = { has_advance = adv_a has_advance = adv_d }"
    assert gen.researched(Candidate("mine", "laborers", "iron")) == ""


def test_values_file_matches_generator_constants() -> None:
    assert VALUES_PATH.read_text(encoding="utf-8") == render_values()


def test_debug_render_stays_balanced(monkeypatch) -> None:
    monkeypatch.setattr(gen, "DEBUG", True)
    method = Method("pp_iron_mine_base", "iron", 0.5, (("manual_labor", 0.1),))
    text = render([Candidate("iron_mine", "laborers", "iron", ((method,),))], {"local_iron_output_modifier"})
    assert braces_balance(text)
    assert "change_global_variable = { name = pp_noble_investment_builds add = 1 }" in text


def test_masons_are_ranked_by_profit_after_inputs() -> None:
    # The first version ranked by the masonry price alone; nobles kept building loss-making masons (2026-10-16).
    block = candidate_blocks()["mason"]
    assert '"market.market_price(goods:masonry)" multiply = 0.5' in block
    assert '"market.market_price(goods:stone)" multiply = 0.32' in block
    assert '"market.market_price(goods:clay)" multiply = 0.64' in block
    assert '"market.market_price(goods:manual_labor)" multiply = 0.11' in block
    assert "pp_noble_investment_keep_better_location = { index = " in block
    effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
    assert "multiply = pp_noble_investment_min_margin" in effects
    assert "set_local_variable = { name = pp_noble_investment_best_score value = 0 }" in effects


def test_mason_shortage_starts_at_80_percent_of_supply() -> None:
    # User rule (2026-10-16): masons only when masonry demand is more than 80 % of supply; other goods need demand > supply.
    block = candidate_blocks()["mason"]
    rule = '"goods_demand_in_market(goods:masonry)" > { value = "goods_supply_in_market(goods:masonry)" multiply = 0.8 }'
    assert block.count(rule) == 2
    assert '"goods_demand_in_market(goods:lumber)" > "goods_supply_in_market(goods:lumber)"' in candidate_blocks()["lumber_mill"]


def test_mines_are_built_regardless_of_shortage() -> None:
    # User rule (2026-10-17): mines (blueprint footprint "mining") need no shortage; profit and the rest still apply.
    blocks = candidate_blocks()
    footprints = gen.blueprint_footprints()
    mines = [b for b in blocks if footprints.get(b) in gen.NO_SHORTAGE_FOOTPRINTS or b in gen.NO_SHORTAGE_BUILDINGS]
    assert {"iron_mine", "coal_mine", "salt_mine", "silver_mine", "gold_diggings", "gold_stamp_mill"} <= set(mines)
    for mine in mines:
        assert "goods_demand_in_market" not in blocks[mine], mine
        assert blocks[mine].count("# built regardless of shortage") == 2, mine
        assert "pp_noble_investment_keep_better_location" in blocks[mine], mine
        assert "can_build_building" in blocks[mine], mine
    assert '"goods_demand_in_market(goods:stone)"' in blocks["stone_quarry"]


def test_farms_are_built_regardless_of_shortage() -> None:
    # User rule (2026-10-17): farms feed the store and population growth; every Province Food maker skips the shortage.
    blocks = candidate_blocks()
    for farm in ("wheat_farm", "cattle_farm", "millet_farmstead", "ocean_fishery", "potato_farm"):
        assert blocks[farm].count("# built regardless of shortage") == 2, farm
        assert "goods_demand_in_market" not in blocks[farm], farm
    for other in ("mason", "lumber_mill", "stone_quarry"):
        assert "goods_demand_in_market" in blocks[other], other


def test_country_potential_is_checked() -> None:
    # can_build_building skips country_potential: nobles built potato farms before the potato arrived (2026-10-17).
    blocks = candidate_blocks()
    gate = "AND = { OR = { pp_potato_native_country = yes has_advance = pp_potato_farm_advance_general } }"
    for tier in ("potato_farm", "potato_farmstead", "potato_model_farm", "potato_rotations"):
        assert gate in blocks[tier], tier
    assert "AND = { produced_in_country:elephants > 0 }" in blocks["elephant_hunting_grounds"]
    assert "# country_potential" not in blocks["wheat_farm"]


def test_excluded_buildings_are_never_candidates() -> None:
    # User rule (2026-10-17): nobles do not build market villages.
    assert "market_village" in gen.EXCLUDED_BUILDINGS
    blocks = candidate_blocks()
    assert not set(gen.EXCLUDED_BUILDINGS) & set(blocks)
    assert "building_type:market_village" not in EFFECTS_PATH.read_text(encoding="utf-8-sig")


def test_peasant_buildings_are_preferred() -> None:
    # User rule (2026-10-16): nobles favoured labourer buildings; the score is profit x the pop type's priority.
    assert gen.POP_PRIORITY["peasants"] > gen.POP_PRIORITY["laborers"]
    blocks = candidate_blocks()
    for building, pop_type in {"wheat_farm": "peasants", "iron_mine": "laborers", "mason": "laborers"}.items():
        priority = gen.number(gen.POP_PRIORITY[pop_type])
        assert f"priority = {priority} }}" in blocks[building], building
    effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
    assert "value = { value = local_var:pp_noble_investment_profit multiply = $priority$ }" in effects
    assert "local_var:pp_noble_investment_profit > 0" in effects


def test_no_stacking_in_one_location() -> None:
    # Nobles stacked the same building 3-4 times in one location while the first was still being built (2026-10-16).
    blocks = candidate_blocks()
    assert all("num_civil_constructions < 1" in block for block in blocks.values())
    assert all("NOT = { has_variable = pp_noble_investment_recent }" in block for block in blocks.values())
    effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
    build = effects[effects.index("pp_noble_investment_build_best = {") :]
    assert f"set_variable = {{ name = pp_noble_investment_recent value = 1 days = {gen.LOCATION_COOLDOWN_DAYS} }}" in build


def test_candidate_rules(tmp_path) -> None:
    (tmp_path / "a.txt").write_text(
        """
REPLACE:mine = {
    pop_type = laborers
    unique_production_methods = {
        pp_mine_base = {
            produced = iron
            output = 0.5
            manual_labor = 0.1
            tools = 0.05
            debug_max_profit = rural_profit_margin
        }
        pp_mine_deep = {
            produced = iron
            output = 0.8
            manual_labor = 0.1
        }
        pp_mine_royal = {
            allow = { always = yes }
            produced = iron
            output = 9
        }
    }
    unique_production_methods = {
        pp_mine_market_sales = {
            offset = 0.01
            produced = iron
            output = 0.004
        }
    }
}
farm = {
    pop_type = peasants
    ai_construct_weight = { value = "market.market_price(goods:wheat)" }
    unique_production_methods = {
        pp_farm_base = {
            produced = wheat
            output = 1
        }
    }
}
forbidden = {
    pop_type = peasants
    forbidden_for_estates = yes
    unique_production_methods = {
        pp_forbidden_market_sales = {
            produced = fish
            output = 1
        }
    }
}
special = {
    pop_type = laborers
    is_special = yes
    unique_production_methods = {
        pp_special_market_sales = {
            produced = silver
            output = 1
        }
    }
}
burgher_shop = {
    pop_type = burghers
    unique_production_methods = {
        pp_burgher_shop_market_sales = {
            produced = cloth
            output = 1
        }
    }
}
no_good = {
    pop_type = peasants
}
""",
        encoding="utf-8",
    )
    goods = {"iron", "wheat", "fish", "silver", "cloth", "manual_labor", "tools", "offset"}
    found = candidates(building_definitions(tmp_path), goods, {"mine": ("adv_mine",)}, {"pp_mine_deep": ("adv_deep",)})
    base = Method("pp_mine_base", "iron", 0.5, (("manual_labor", 0.1), ("tools", 0.05)))
    deep = Method("pp_mine_deep", "iron", 0.8, (("manual_labor", 0.1),), ("adv_deep",))
    sales = Method("pp_mine_market_sales", "iron", 0.004, (("offset", 0.01),))
    assert found == [
        Candidate("farm", "peasants", "wheat", ((Method("pp_farm_base", "wheat", 1.0, ()),),)),
        Candidate("mine", "laborers", "iron", ((base, deep), (sales,)), ("adv_mine",)),
    ]
    lines = " ".join(gen.method_lines(deep, {"local_iron_output_modifier"}, ""))
    assert "limit = { owner = { has_advance = adv_deep } }" in lines
    assert "multiply = { value = 1 add = modifier:local_iron_output_modifier }" in lines
