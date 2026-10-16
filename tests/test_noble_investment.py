from __future__ import annotations

import re

import scripts.generate_noble_investment as gen
from scripts.generate_noble_investment import (
    BUILDING_TYPES,
    EFFECTS_PATH,
    MOD_ROOT,
    VALUES_PATH,
    Candidate,
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


def test_values_file_matches_generator_constants() -> None:
    assert VALUES_PATH.read_text(encoding="utf-8") == render_values()


def test_debug_render_stays_balanced(monkeypatch) -> None:
    monkeypatch.setattr(gen, "DEBUG", True)
    text = render([Candidate("iron_mine", "laborers", "iron", "local_iron_output_modifier")])
    assert braces_balance(text)
    assert "change_global_variable = { name = pp_noble_investment_builds add = 1 }" in text


def test_candidate_rules(tmp_path) -> None:
    (tmp_path / "a.txt").write_text(
        """
REPLACE:mine = {
    pop_type = laborers
    unique_production_methods = { m = { pp_mine_market_sales = { produced = iron output = 0.004 } } }
}
farm = {
    pop_type = peasants
    ai_construct_weight = { value = "market.market_price(goods:wheat)" }
}
forbidden = {
    pop_type = peasants
    forbidden_for_estates = yes
    unique_production_methods = { m = { pp_forbidden_market_sales = { produced = fish } } }
}
special = {
    pop_type = laborers
    is_special = yes
    unique_production_methods = { m = { pp_special_market_sales = { produced = silver } } }
}
burgher_shop = {
    pop_type = burghers
    unique_production_methods = { m = { pp_burgher_shop_market_sales = { produced = cloth } } }
}
no_good = {
    pop_type = peasants
}
""",
        encoding="utf-8",
    )
    found = candidates(building_definitions(tmp_path), {"local_iron_output_modifier"})
    assert found == [
        Candidate("farm", "peasants", "wheat", None),
        Candidate("mine", "laborers", "iron", "local_iron_output_modifier"),
    ]
