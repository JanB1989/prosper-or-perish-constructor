"""The sync's World Builder fingerprint ignores what the stage never reads (2026-10-04, Jan: a Tavern weight edit
reran the whole start setup, about two minutes, before the sync could deploy)."""

from __future__ import annotations

from pathlib import Path

from prosper_or_perish_constructor.cli import _worldbuilder_view

BLUEPRINT = b"""version: 2
tag: tavern
building:
  body: |2-
    max_levels = tavern_max_level   # cap
    ai_construct_weight = {
      value = -60
      add = { value = 6 subtract = pp_location_stored_months divide = 6 min = 0 max = 1 multiply = 120 }
    }
    unique_production_methods = {
      pp_tavern_serve_victuals = {
        victuals = 0.8
        output = 25.5
      }
    }
localization:
  entries:
    tavern: Tavern
icon:
  size: 512
evaluation:
  allow_rules:
    profit_percent: why
"""


def view(text: bytes, name: str = "tavern.yml") -> bytes:
    return _worldbuilder_view(Path(name), text)


def test_weights_comments_and_texts_are_ignored() -> None:
    base = view(BLUEPRINT)
    assert view(BLUEPRINT.replace(b"value = -60", b"value = -61")) == base
    assert view(BLUEPRINT.replace(b"# cap", b"# the cap, edited")) == base
    assert view(BLUEPRINT.replace(b"tavern: Tavern", b"tavern: Inn")) == base
    assert view(BLUEPRINT.replace(b"size: 512", b"size: 256")) == base
    assert view(BLUEPRINT.replace(b"profit_percent: why", b"profit_percent: because")) == base


def test_what_the_stage_reads_still_counts() -> None:
    base = view(BLUEPRINT)
    assert view(BLUEPRINT.replace(b"output = 25.5", b"output = 25.6")) != base
    assert view(BLUEPRINT.replace(b"tavern_max_level", b"other_max_level")) != base


def test_script_files_drop_comments_and_weights_only() -> None:
    script = b'building = {\n\tmax_levels = 3 # three\n\tai_construct_weight = { value = 5 }\n\tname = "a # b"\n}\n'
    out = view(script, "zz_pp_x.txt")
    assert b"three" not in out and b"ai_construct_weight" not in out
    assert b'"a # b"' in out and b"max_levels = 3" in out
    assert view(script.replace(b"value = 5", b"value = 9"), "zz_pp_x.txt") == out
    assert view(b"\x89PNG binary # data", "map.png") == b"\x89PNG binary # data"


def test_stage_blind_static_keys_are_ignored_in_static_modifiers_only() -> None:
    block = b"market_center = {\n\tfree_building_levels = 5\n\tlocal_market_access = 10\n}\n"
    name = "main_menu/common/static_modifiers/pp_x.txt"
    out = view(block, name)
    assert view(block.replace(b"= 10", b"= 0.5"), name) == out
    assert view(block.replace(b"\tlocal_market_access = 10\n", b""), name) == out
    assert view(block.replace(b"= 5", b"= 6"), name) != out
    # a building's market access is not a static modifier line: it still counts
    assert view(block.replace(b"= 10", b"= 0.5"), "in_game/common/building_types/x.txt") != view(block, "in_game/common/building_types/x.txt")


def test_nothing_the_stage_runs_reads_the_blind_keys() -> None:
    import re

    from prosper_or_perish_constructor.cli import WB_BLIND_STATIC_KEYS, WORLDBUILDER_CODE_AND_DATA

    repo = Path(__file__).resolve().parents[1]
    # save-side market tools (not imported by the stage) and the logistics writer (writes the buildings' raw line)
    writers = {"market_access.py", "markets.py", "logistics.py"}
    code = [p for rel in WORLDBUILDER_CODE_AND_DATA if (root := repo / rel).exists()
            for p in ([root] if root.is_file() else root.rglob("*.py")) if p.suffix == ".py" and p.name not in writers]
    mod = next((repo / "mod").glob("Prosper or Perish (Population*"))
    scripts = [p for sub in ("in_game/common", "main_menu/common") for p in (mod / sub).rglob("*.txt")
               if "static_modifiers" not in p.parts]
    for key in WB_BLIND_STATIC_KEYS:
        assert not [p.name for p in code if key in p.read_text(encoding="utf-8")], key
        read = re.compile(rf"modifier:{key}\b")
        assert not [p.name for p in scripts if read.search(p.read_text(encoding="utf-8-sig", errors="replace"))], key


def _mod_root() -> Path:
    return next((Path(__file__).resolve().parents[1] / "mod").glob("Prosper or Perish (Population*"))


def test_worldbuilder_mod_inputs_exist() -> None:
    """Every traced input is still there (a renamed file would silently drop out of the fingerprint)."""
    from prosper_or_perish_constructor.cli import WORLDBUILDER_MOD_INPUTS

    mod = _mod_root()
    assert not [rel for rel in WORLDBUILDER_MOD_INPUTS if not (mod / rel).exists()]


def test_unread_script_files_do_not_rerun_the_start_setup() -> None:
    """2026-10-07: edits to an advance file and an on_action file reran the start setup (78 s, 115 s); the stage reads
    neither (tools/trace_worldbuilder_inputs.py)."""
    from prosper_or_perish_constructor.cli import WORLDBUILDER_MOD_INPUTS

    mod = _mod_root()
    inputs = [mod / rel for rel in WORLDBUILDER_MOD_INPUTS]

    def counted(rel: str) -> bool:
        path = mod / rel
        return any(path == root or root in path.parents for root in inputs)

    for rel in (
        "in_game/common/on_action/pp_country_finetunes.txt",
        "in_game/common/area_preferences/pp_colonizer_preferences.txt",
        "in_game/common/advances/pp_institution_advances_adjustments.txt",
        "in_game/common/ai_scripted_expansion_score/pp_reconquista.txt",
        "main_menu/localization/english/pp_area_preferences_l_english.yml",
    ):
        assert not counted(rel), rel
    for rel in (
        "in_game/common/building_types/rural_buildings.txt",
        "in_game/common/scripted_effects/on_action_effects.txt",
        "main_menu/setup/1337",
        "in_game/map_data/default.map",
    ):
        assert counted(rel), rel
