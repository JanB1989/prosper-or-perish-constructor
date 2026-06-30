from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.syntax import CList, Value
from eu5gameparser.load_order import load_merged_directory, load_profile
from prosper_or_perish_constructor.rgo_cost_redirects import (
    RGO_BUILDING_COST_GROUPS,
    RGO_COST_MODIFIERS,
    RGO_COST_REDIRECT_COLLECTIONS,
    RGO_COST_REDIRECT_FILE,
    RGO_METHODS,
    RGO_REDIRECT_OBJECTIVE,
    classify_pop_rgo_building_cost_targets,
    collect_active_rgo_cost_assignments,
)


ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
LOAD_ORDER = ROOT / "constructor.load_order.toml"


def test_pop_rgo_building_cost_classification_uses_raw_material_methods() -> None:
    profile = load_profile("constructor", LOAD_ORDER)

    classification = classify_pop_rgo_building_cost_targets(profile, MOD_ROOT)
    modifiers_by_method = classification.modifiers_by_method()

    assert RGO_BUILDING_COST_GROUPS == {
        "farming": "pp_rgo_farming_building_cost_group",
        "mining": "pp_rgo_mining_building_cost_group",
        "hunting": "pp_rgo_hunting_building_cost_group",
        "gathering": "pp_rgo_gathering_building_cost_group",
        "forestry": "pp_rgo_forestry_building_cost_group",
    }
    assert set(modifiers_by_method) == set(RGO_METHODS)
    assert all(not modifiers for modifiers in modifiers_by_method.values())

    # Objective: classify PoP raw-material buildings even when they are not
    # price-modifier targets yet, so a future price pass can wire them in.
    assert {method for methods in classification.unpriced_buildings.values() for method in methods} == set(
        RGO_METHODS
    )
    assert classification.unpriced_buildings["alum_works"] == ("gathering", "mining")
    assert classification.unpriced_buildings["cocoa_grove"] == ("farming",)
    assert classification.unpriced_buildings["ivory_hunting_camp"] == ("hunting",)
    assert classification.unpriced_buildings["lumber_mill"] == ("forestry",)
    assert classification.unpriced_buildings["clay_pit"] == ("gathering",)
    assert classification.unclassified_price_buildings == {
        "bund": "pp_bund_price",
        "irrigation_systems": "pp_irrigation_systems_price",
        "khmer_baray": "pp_khmer_baray_price",
        "macadam_works": "pp_macadam_works_price",
        "paviors_yard": "pp_paviors_yard_price",
        "permanent_way_depot": "pp_permanent_way_depot_price",
        "polders": "pp_polders_price",
        "road_wardens_yard": "pp_road_wardens_yard_price",
        "terraces": "pp_terraces_price",
        "victuals_market": "pp_victuals_market_price",
    }


def test_active_rgo_cost_assignments_are_generated_redirect_dependencies() -> None:
    profile = load_profile("constructor", LOAD_ORDER)
    assignments = collect_active_rgo_cost_assignments(profile)
    classification = classify_pop_rgo_building_cost_targets(profile, MOD_ROOT)
    modifiers_by_method = classification.modifiers_by_method()
    generated = _generated_redirect_blocks()

    assert len(assignments) == 58
    assert Counter(assignment.method for assignment in assignments) == {
        "farming": 26,
        "mining": 18,
        "forestry": 6,
        "hunting": 5,
        "gathering": 3,
    }

    for patch, expected_values in _expected_patch_values(assignments, modifiers_by_method).items():
        scope, collection, top_key, nested_path = patch
        leaf = _generated_leaf(generated, scope, collection, top_key, nested_path)
        actual_values = _numeric_values(leaf)
        for key, expected_value in expected_values.items():
            assert abs(actual_values[key] - expected_value) < 1e-9, (
                f"{scope}/{collection}/{top_key}/{'/'.join(nested_path)} {key}"
            )


def test_generated_rgo_cost_redirects_net_vanilla_rgo_expansion_cost_to_zero() -> None:
    profile = load_profile("constructor", LOAD_ORDER)
    assignments = collect_active_rgo_cost_assignments(profile)
    expected_expand_keys = {
        (assignment.scope, assignment.collection, assignment.path[0], assignment.path[1:-1], assignment.modifier)
        for assignment in assignments
    }

    for scope, collection, top_key, nested_path, modifier in sorted(expected_expand_keys):
        merged_entry = _merged_entry(profile, scope, collection, top_key)
        assert isinstance(merged_entry.value, CList)
        leaf = _nested_block(merged_entry.value, nested_path)
        assert leaf is not None, f"missing merged path {scope}/{collection}/{top_key}/{nested_path}"
        assert abs(_numeric_values(leaf)[modifier]) < 1e-9, (
            f"{scope}/{collection}/{top_key}/{'/'.join(nested_path)} {modifier}"
        )


def test_generated_rgo_cost_redirect_files_state_objective_and_do_not_define_fake_groups() -> None:
    redirect_files = _generated_redirect_files()
    assert redirect_files
    fake_group_keys = set(RGO_BUILDING_COST_GROUPS.values())

    for path in redirect_files:
        text = path.read_text(encoding="utf-8-sig")
        assert f"# Objective: {RGO_REDIRECT_OBJECTIVE}." in text
        assert "TRY_INJECT:" in text or "TRY_REPLACE:" in text
        assert fake_group_keys.isdisjoint(set(_top_level_patch_keys(path)))
        for fake_group_key in fake_group_keys:
            assert fake_group_key not in text


def test_generated_law_rgo_cost_redirects_replace_law_groups_instead_of_injecting_options() -> None:
    path = MOD_ROOT / "in_game" / "common" / "laws" / RGO_COST_REDIRECT_FILE
    text = path.read_text(encoding="utf-8-sig")

    assert "TRY_INJECT:" not in text
    assert {entry.key for entry in parse_file(path).entries} == {
        "TRY_REPLACE:legal_code_law",
        "TRY_REPLACE:mesta_council_law",
        "TRY_REPLACE:mining_law",
    }
    assert "german_mining_law" in text
    assert "novo_brdo_mining_law" in text
    assert "burghers_mining_law" in text
    assert "zimbabwe_mining_law" in text
    assert "expand_rgo_mining_cost_modifier" not in text
    assert "expand_rgo_farming_cost_modifier" not in text


def _expected_patch_values(
    assignments,
    modifiers_by_method: dict[str, tuple[str, ...]],
) -> dict[tuple[str, str, str, tuple[str, ...]], dict[str, float]]:
    expected: dict[tuple[str, str, str, tuple[str, ...]], dict[str, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    for assignment in assignments:
        patch = (
            assignment.scope,
            assignment.collection,
            assignment.path[0],
            assignment.path[1:-1],
        )
        if assignment.collection != "laws":
            expected[patch][RGO_COST_MODIFIERS[assignment.method]] += -assignment.value
        for modifier_key in modifiers_by_method[assignment.method]:
            expected[patch][modifier_key] += assignment.value
    return {patch: dict(values) for patch, values in expected.items()}


def _generated_redirect_blocks() -> dict[tuple[str, str], dict[str, CList]]:
    generated: dict[tuple[str, str], dict[str, CList]] = {}
    for scope, collection in RGO_COST_REDIRECT_COLLECTIONS:
        path = MOD_ROOT / scope / "common" / collection / RGO_COST_REDIRECT_FILE
        if not path.is_file():
            continue
        blocks: dict[str, CList] = {}
        for entry in parse_file(path).entries:
            top_key = _top_level_key(entry.key)
            assert isinstance(entry.value, CList)
            blocks[top_key] = entry.value
        generated[(scope, collection)] = blocks
    return generated


def _generated_redirect_files() -> list[Path]:
    return [
        MOD_ROOT / scope / "common" / collection / RGO_COST_REDIRECT_FILE
        for scope, collection in RGO_COST_REDIRECT_COLLECTIONS
        if (MOD_ROOT / scope / "common" / collection / RGO_COST_REDIRECT_FILE).is_file()
    ]


def _generated_leaf(
    generated: dict[tuple[str, str], dict[str, CList]],
    scope: str,
    collection: str,
    top_key: str,
    nested_path: tuple[str, ...],
) -> CList:
    try:
        top = generated[(scope, collection)][top_key]
    except KeyError as error:
        raise AssertionError(f"missing generated patch for {scope}/{collection}/{top_key}") from error
    leaf = _nested_block(top, nested_path)
    if leaf is None:
        raise AssertionError(f"missing generated nested path {scope}/{collection}/{top_key}/{nested_path}")
    return leaf


def _merged_entry(profile, scope: str, collection: str, top_key: str):
    for entry in load_merged_directory(profile, collection, scope=scope).entries:
        if entry.key == top_key:
            return entry
    raise AssertionError(f"missing merged entry {scope}/{collection}/{top_key}")


def _nested_block(block: CList, nested_path: tuple[str, ...]) -> CList | None:
    current = block
    for key in nested_path:
        next_value = None
        for entry in current.entries:
            if entry.key == key and isinstance(entry.value, CList):
                next_value = entry.value
        if next_value is None:
            return None
        current = next_value
    return current


def _numeric_values(block: CList) -> defaultdict[str, float]:
    values: defaultdict[str, float] = defaultdict(float)
    for entry in block.entries:
        value = _scalar_float(entry.value)
        if value is not None:
            values[entry.key] += value
    return values


def _scalar_float(value: Value | None) -> float | None:
    if isinstance(value, bool) or isinstance(value, CList) or value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _top_level_patch_keys(path: Path) -> list[str]:
    return [_top_level_key(entry.key) for entry in parse_file(path).entries]


def _top_level_key(raw_key: str) -> str:
    if ":" not in raw_key:
        return raw_key
    return raw_key.split(":", 1)[1]
