"""The sync's World Builder fingerprint ignores what the stage never reads (2026-10-04, Jan: a Tavern weight edit
reran the whole start setup, about two minutes, before the sync could deploy)."""

from __future__ import annotations

import re
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


TRIGGERS = "in_game/common/scripted_triggers"


def test_definitions_count_only_when_an_input_reaches_them(tmp_path: Path) -> None:
    """2026-10-15: a one-line edit to the enclave triggers reran the start setup (73 s); no stage input names them."""
    from prosper_or_perish_constructor.cli import _DefinitionReach

    folder = tmp_path / TRIGGERS
    folder.mkdir(parents=True)
    path = folder / "pp_x.txt"
    path.write_bytes(
        b'\xef\xbb\xbf# a "quoted" comment\npp_used = {\n\tpp_inner = yes # inner\n}\npp_inner = { always = yes }\n'
        b"pp_unused = { always = no }\nREPLACE:vanilla_thing = { always = no }\npp_param_wheat = { always = yes }\n"
        b"@limit = 5\n"
    )
    reach = _DefinitionReach()
    reach.add_root(Path("tavern.yml"), b"allow = { pp_used = yes pp_param_$good$ = yes }")
    reach.index({folder: TRIGGERS})
    out = reach.view(path, path.read_bytes())
    for kept in (b"pp_used = {\n\tpp_inner = yes\n}", b"pp_inner = { always = yes }", b"pp_param_wheat", b"@limit = 5"):
        assert kept in out, kept
    # an unreached override keeps only its name (compat.mod_overrides reads it); unreached bodies drop out
    assert b"REPLACE:vanilla_thing" in out and b"pp_unused" not in out and b"always = no" not in out
    assert reach.view(path, path.read_bytes().replace(b"always = no", b"always = yes")) == out


def test_named_files_count_whole_and_generic_actions_only_by_override_name(tmp_path: Path) -> None:
    from prosper_or_perish_constructor.cli import _DefinitionReach

    triggers, actions = tmp_path / TRIGGERS, tmp_path / "in_game/common/generic_actions"
    triggers.mkdir(parents=True)
    actions.mkdir(parents=True)
    named = triggers / "pp_named.txt"
    named.write_bytes(b"pp_nobody_uses = { always = no }\n")
    action = actions / "pp_action.txt"
    action.write_bytes(b"pp_used = { effect = { } }\nREPLACE:vanilla_action = { effect = { } }\n")
    plain = actions / "pp_plain.txt"
    plain.write_bytes(b"pp_used = { effect = { } }\n")
    reach = _DefinitionReach()
    reach.add_root(Path("stage.py"), b'PATH = Path("in_game/common/scripted_triggers/pp_named.txt")  # pp_used')
    reach.index({triggers: TRIGGERS, actions: "in_game/common/generic_actions"})
    assert b"pp_nobody_uses" in reach.view(named, named.read_bytes())
    assert reach.view(action, action.read_bytes()) == b"REPLACE:vanilla_action"
    assert reach.view(plain, plain.read_bytes()) is None


def test_mod_definition_views() -> None:
    """On the mod: the enclave scripts never count, and every definition a building or blueprint names (outside its AI
    weights, which the stage never reads) does."""
    from prosper_or_perish_constructor.cli import WB_DEFINITION_FOLDERS, _DefinitionReach, _worldbuilder_parts

    repo = Path(__file__).resolve().parents[1]
    reach = _DefinitionReach()
    _worldbuilder_parts(repo, repo / "constructor.toml", reach)
    mod = _mod_root()
    for rel in (f"{TRIGGERS}/pp_enclave_triggers.txt", "in_game/common/generic_actions/pp_release_enclave_independence.txt"):
        assert reach.view(mod / rel, (mod / rel).read_bytes()) is None, rel
    named = b" ".join(view(p.read_bytes(), str(p)) for p in (*(mod / "in_game/common/building_types").glob("*.txt"),
                                               *(repo / "blueprints/accepted").rglob("*.yml")))
    words = set(re.findall(rb"[A-Za-z0-9_]+", named))
    for folder, bodies in WB_DEFINITION_FOLDERS.items():
        for path in (mod / folder).glob("*.txt") if bodies else ():
            for _, name, _ in reach._entries(path, path.read_bytes()) or ():
                assert name not in words or name in reach.kept, (path.name, name)


# Stage code that names a definition folder without a file. Each reads definitions only by name (or is not stage
# code); a new one may read a whole file another way, and then its files must count whole (WB_DEFINITION_FOLDERS).
# Rerun tools/trace_worldbuilder_inputs.py after adding one: it flags reads of narrowed files.
FOLDER_READERS = {
    "src/prosper_or_perish_constructor/worldbuilder/start_rules.py": 3,         # Rules: evaluated by name
    "src/prosper_or_perish_constructor/vanilla_food_productivity.py": 4,        # plain-number values by name; finalize
    "src/prosper_or_perish_constructor/building_footprint.py": 2,               # finalize only
    "src/prosper_or_perish_constructor/worldbuilder/start_simulation.py": 1,    # a comment
    "scripts/generate_rural_capacity_values.py": 1,                             # writes its own files
}


def test_stage_code_reads_definition_folders_only_by_name() -> None:
    from prosper_or_perish_constructor.cli import WORLDBUILDER_CODE_AND_DATA

    repo = Path(__file__).resolve().parents[1]
    mention = re.compile(r"[\"'/](?:scripted_triggers|script_values|generic_actions)(?!/[\w.-]+\.txt)[\"'/]")
    found = {}
    for rel in WORLDBUILDER_CODE_AND_DATA:
        root = repo / rel
        for path in [root] if root.is_file() else sorted(root.rglob("*.py")):
            if path.suffix == ".py" and (n := len(mention.findall(path.read_text(encoding="utf-8")))):
                found[str(path.relative_to(repo))] = n
    assert found == FOLDER_READERS
