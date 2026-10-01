"""Game-start development: vanilla's rules as the EU5 1.4 engine applies them, evaluated on the mod's map."""

from pathlib import Path

import numpy as np
import polars as pl
import pytest
from eu5gameparser.load_order import DataProfile, GameLayer, LoadOrderConfig
from PIL import Image

from prosper_or_perish_constructor.free_building_levels import (
    enrich_locations_with_game_start_data,
    extract_development_river_sizes,
    load_development_weights,
)
from prosper_or_perish_constructor.setup_layout import SETUP_DIR
from prosper_or_perish_constructor.worldbuilder import development as dev

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
WEIGHTS = {"base": -2.0, "coastal": 5.0, "river": 0.5, "road": 2.0, "town": 2.0, "hills": -2.0, "sparse": -1.0,
           "arctic": -5.0, "flatland": 1.0, "forest": -2.0, "north_region": 5.0}


def _locations(rows: list[dict]) -> pl.DataFrame:
    defaults = {"location_id": 1, "province": "p", "region": "north_region", "area": "a", "named_location_hex": "000000",
                "is_coastal": False, "topography": "flatland", "vegetation": "forest", "climate": "arctic",
                "natural_harbor_suitability": 0.0, "has_river": False}
    return pl.DataFrame([{**defaults, "location_id": i + 1, **row} for i, row in enumerate(rows)])


def _develop(rows: list[dict], sizes: dict[str, float], weights=WEIGHTS, roads=()) -> dict[str, float]:
    frame = enrich_locations_with_game_start_data(
        _locations(rows), ranks={}, market_centers=(), road_locations=roads, capitals=(), ports=(), river_levels={},
        development_weights=weights, development_river_sizes=sizes)
    return dict(frame.select("location_tag", "development").iter_rows())


def test_own_terms_are_floored_before_base_coast_and_river() -> None:
    rows = [
        # Vopnafjordur (vanilla 1.4 start: 1.75): hills -2, sparse -1, arctic -5, region +5 -> own -3 floored to 0
        {"location_tag": "fjord", "topography": "hills", "vegetation": "sparse", "natural_harbor_suitability": 0.75},
        # Surgut-like: own -6 -> 0, base -2, river 0.5 x 6 -> 1
        {"location_tag": "river", "topography": "hills", "vegetation": "forest", "region": "x"},
        # everything negative stays 0
        {"location_tag": "waste", "topography": "hills", "vegetation": "forest", "region": "x"},
        # positive own terms simply add up; a road adds nothing at game start
        {"location_tag": "plain", "climate": "none", "vegetation": "none"},
    ]
    got = _develop(rows, {"river": 6.0}, roads=("plain",))
    assert got == {"fjord": 1.75, "river": 1.0, "waste": 0.0, "plain": 4.0}


def test_river_sizes_follow_the_width_level_and_junctions(tmp_path: Path) -> None:
    colours = {"a": (255, 0, 0), "b": (0, 255, 0), "c": (0, 0, 255), "d": (255, 255, 0), "e": (0, 255, 255)}
    locations = pl.DataFrame([{"location_tag": t, "named_location_hex": "%02x%02x%02x" % c} for t, c in colours.items()])
    grid = [["a", "a", "b", "b", "c"], ["c", "d", "d", "e", "e"]]
    Image.fromarray(np.array([[colours[t] for t in row] for row in grid], dtype=np.uint8), "RGB").save(tmp_path / "loc.png")
    # a: widths 4 + 5 (level 1 -> size 2); b: width 11 (level 3) beside a merge marker (1) -> junction 6;
    # c: width 15 (level 5) -> 6 and a source pixel (0, no size); d: width 12 (level 4) -> 5; e: no river
    rivers = Image.fromarray(np.array([[4, 5, 11, 1, 15], [0, 12, 255, 254, 255]], dtype=np.uint8), "P")
    rivers.putpalette([0] * 768)
    rivers.save(tmp_path / "riv.png")
    sizes = extract_development_river_sizes(locations, locations_png_path=tmp_path / "loc.png", rivers_png_path=tmp_path / "riv.png", chunk_rows=1)
    assert dict(sizes.iter_rows()) == {"a": 2.0, "b": 6.0, "c": 6.0, "d": 5.0, "e": 0.0}


def test_duplicate_rule_keys_add_up_and_a_later_file_replaces_the_earlier(tmp_path: Path) -> None:
    vanilla, mod = tmp_path / "vanilla", tmp_path / "mod"
    (vanilla / "game" / SETUP_DIR).mkdir(parents=True)
    (vanilla / "game" / SETUP_DIR / "14_development.txt").write_text(
        "development = { base = -2 wexford_province = 2 wexford_province = 2 }", encoding="utf-8")
    profile = DataProfile(name="v", layers=(GameLayer(id="vanilla", name="Vanilla", root=vanilla, kind="vanilla"),))
    assert load_development_weights(profile) == {"base": -2.0, "wexford_province": 4.0}
    (mod / SETUP_DIR).mkdir(parents=True)
    (mod / SETUP_DIR / "14_development.txt").write_text("development = { base = 0 alpha = 3.5 }", encoding="utf-8")
    both = DataProfile(name="m", layers=(*profile.layers, GameLayer(id="mod", name="Mod", root=mod, kind="mod")))
    assert load_development_weights(both) == {"base": 0.0, "alpha": 3.5}


def test_world_builder_classes_score_like_their_vanilla_parent() -> None:
    families = {"vegetation": {"forest": ["ha1300_veg_mixed_forest", "ha1300_veg_swamp"]},
                "topography": {"flatland": ["ha1300_topo_floodplains"]}, "climate": {"tropical": ["ha1300_climate_savanna"]}}
    rules = dev.rules_with_families({"forest": -2.0, "flatland": 1.0}, families)
    assert rules == {"forest": -2.0, "flatland": 1.0, "ha1300_veg_mixed_forest": -2.0, "ha1300_veg_swamp": -2.0,
                     "ha1300_topo_floodplains": 1.0}
    # a key vanilla lists itself keeps vanilla's value
    assert dev.rules_with_families({"forest": -2.0, "ha1300_veg_swamp": -4.0}, families)["ha1300_veg_swamp"] == -4.0


def test_reference_comparison_reports_both_error_sides() -> None:
    evaluated = pl.DataFrame({"location_tag": ["a", "b", "c", "d"], "development": [1.0, 2.5, 3.0, 9.0],
                              "development_river_size": [0.0, 6.0, 2.0, 0.0]})
    reference = pl.DataFrame({"location_tag": ["a", "b", "c", "e"], "development": [1.0, 3.5, 2.0, 4.0]})
    summary, mismatches = dev.compare_with_reference(evaluated, reference)
    assert summary["locations"] == 3 and summary["exact"] == 1 and summary["missing_from_evaluation"] == 1
    assert summary["evaluator_too_high"] == 1 and summary["evaluator_too_low"] == 1
    assert summary["river_locations"] == 2 and summary["river_exact"] == 0
    assert mismatches["location_tag"].to_list() == ["b", "c"]


def test_the_mod_ships_evaluated_development_not_save_values() -> None:
    text = (MOD_ROOT / dev.SETUP_RELATIVE_PATH).read_text(encoding="utf-8-sig")
    assert text.startswith(dev.GENERATED_MARKER)
    assert not (ROOT / "config" / "start_development.csv").exists(), "save development is validation data (config/validation/)"
    assert dev.load_reference(ROOT) is not None


def _vanilla_game_present() -> bool:
    try:
        root = LoadOrderConfig.load(ROOT / "constructor.load_order.toml").vanilla_root
    except Exception:
        return False
    return (root / "game" / "in_game" / "map_data" / "rivers.png").is_file()


@pytest.mark.skipif(not _vanilla_game_present(), reason="needs the EU5 game files")
def test_the_evaluator_reproduces_the_vanilla_start_save() -> None:
    # vanilla's rules on the vanilla map against the engine's own placement (vanilla 1.4 start save)
    summary, _ = dev.compare_with_reference(dev.evaluate_development(ROOT, ROOT / "constructor.toml", "vanilla"), dev.load_reference(ROOT))
    assert summary["missing_from_evaluation"] == 0
    assert summary["match_rate"] >= 0.999, summary
