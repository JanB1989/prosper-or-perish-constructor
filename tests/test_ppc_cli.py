import json
import os
import re
from pathlib import Path
from types import SimpleNamespace

import polars as pl
import pytest

from prosper_or_perish_constructor import cli

ROOT = Path(__file__).resolve().parents[1]


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "constructor.toml").write_text('name = "test"\n')
    return tmp_path


def _write_minimal_europedia_sources(repo: Path) -> None:
    repo.joinpath("constructor.toml").write_text(
        '[project]\nmod_root = "mod/test-mod"\n',
        encoding="utf-8",
    )
    mod_root = repo / "mod" / "test-mod"
    gui = mod_root / "in_game" / "gui" / "encyclopedia_lateralview.gui"
    loc = mod_root / "main_menu" / "localization" / "english" / "pp_europedia_l_english.yml"
    concepts = mod_root / "main_menu" / "common" / "game_concepts"
    gui.parent.mkdir(parents=True)
    loc.parent.mkdir(parents=True)
    concepts.mkdir(parents=True)
    gui.write_text(
        """
button_regular = {
  raw_text = "All"
  onclick = "[GetVariableSystem.Set('pp_filter', 'all')]"
}
button_regular = {
  raw_text = "Food Production"
  onclick = "[GetVariableSystem.Set('pp_filter', 'food')]"
}
vbox = {
  visible = "[Or(GetVariableSystem.HasValue('pp_filter', 'all'), GetVariableSystem.HasValue('pp_filter', 'food'))]"
  icon = { texture = "gfx/interface/icons/flat_icons/trade_market/food_stockpile.dds" size = { 45 45 } }
  text_single = { text = "game_concept_pp_food" }
  text_multi = { text = "game_concept_pp_food_desc" }
}
""",
        encoding="utf-8",
    )
    title = json.dumps("P&P: Food Production")
    desc = json.dumps("#T Food#!\n$BULLET$ Build cookeries.")
    loc.write_text(
        "l_english:\n"
        f"  game_concept_pp_food: {title}\n"
        f"  game_concept_pp_food_desc: {desc}\n",
        encoding="utf-8-sig",
    )
    (concepts / "pp_food_production.txt").write_text(
        'pp_food = { family = food texture = "flat_icons/trade_market/food_stockpile" }\n',
        encoding="utf-8",
    )


def _write_savegame_manifest(repo: Path, save_path: Path | None = None) -> None:
    manifest = repo / "graphs" / "dataset" / "manifest.parquet"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(
        [
            {
                "snapshot_id": "s1",
                "playthrough_id": "aaa",
                "path": str(save_path or "/tmp/s1.eu5"),
                "year": 1337,
                "month": 1,
                "day": 1,
                "mtime_ns": 1,
                "size": 1,
            }
        ]
    ).write_parquet(manifest)


def test_test_command_disables_pytest_capture_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    calls: list[list[str]] = []

    def fake_run(command, cwd):
        calls.append([str(part) for part in command])
        assert cwd == repo
        return 0

    monkeypatch.setattr(cli, "_run", fake_run)

    assert cli.main(["--repo", str(repo), "test", "tests/test_project_config.py"]) == 0

    assert calls == [
        [
            cli.sys.executable,
            "-m",
            "pytest",
            "--capture=no",
            "tests/test_project_config.py",
        ]
    ]


def test_test_command_preserves_explicit_capture_args(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    calls: list[list[str]] = []

    def fake_run(command, cwd):
        calls.append([str(part) for part in command])
        assert cwd == repo
        return 0

    monkeypatch.setattr(cli, "_run", fake_run)

    assert cli.main(["--repo", str(repo), "test", "-s", "tests/test_project_config.py"]) == 0

    assert calls == [[cli.sys.executable, "-m", "pytest", "-s", "tests/test_project_config.py"]]


def test_blueprint_tag_routes_to_filtered_evaluation_workflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    calls: list[list[str]] = []

    def fake_run(command, cwd):
        calls.append([str(part) for part in command])
        assert cwd == repo
        return 0

    monkeypatch.setattr(cli, "_run", fake_run)

    assert cli.main(["--repo", str(repo), "blueprint", "tag", "farming_capacity"]) == 0

    assert calls == [
        [
            "eu5-orchestrator",
            "blueprint",
            "evaluate",
            "--project",
            str(repo / "constructor.toml"),
            "--building",
            "farming_capacity",
        ]
    ]


def test_setup_corrections_dry_run_invokes_generator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    script = repo / "scripts" / "generate_setup_building_corrections.py"
    script.parent.mkdir()
    script.write_text("", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(command, cwd):
        calls.append([str(part) for part in command])
        assert cwd == repo
        return 0

    monkeypatch.setattr(cli, "_run", fake_run)

    assert cli.main(["--repo", str(repo), "setup-corrections", "--log", "error.log"]) == 0

    assert calls == [
        [
            cli.sys.executable,
            str(script),
            "--repo",
            str(repo),
            "--project",
            str(repo / "constructor.toml"),
            "--load-order",
            str(repo / "constructor.load_order.toml"),
            "--log",
            "error.log",
        ]
    ]


def test_setup_corrections_write_passes_write_and_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    script = repo / "scripts" / "generate_setup_building_corrections.py"
    script.parent.mkdir()
    script.write_text("", encoding="utf-8")
    calls: list[list[str]] = []

    monkeypatch.setattr(
        cli,
        "_run",
        lambda command, cwd: calls.append([str(part) for part in command]) or 0,
    )

    assert (
        cli.main(
            [
                "--repo",
                str(repo),
                "setup-corrections",
                "--write",
                "--force",
                "--building",
                "fruit_orchard",
                "--direct-building-manager-only",
            ]
        )
        == 0
    )

    assert "--write" in calls[0]
    assert "--force" in calls[0]
    assert calls[0][-3:] == ["--building", "fruit_orchard", "--direct-building-manager-only"]


def test_food_startup_invokes_generator_with_compile_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    script = repo / "scripts" / "generate_food_building_startup.py"
    script.parent.mkdir()
    script.write_text("", encoding="utf-8")
    calls: list[list[str]] = []

    monkeypatch.setattr(
        cli,
        "_run",
        lambda command, cwd: calls.append([str(part) for part in command]) or 0,
    )

    assert cli.main(["--repo", str(repo), "food-startup", "--compile-script"]) == 0

    assert calls == [
        [
            cli.sys.executable,
            str(script),
            "--repo",
            str(repo),
            "--project",
            str(repo / "constructor.toml"),
            "--config",
            str(repo / "food_building_startup.toml"),
            "--compile-script",
        ]
    ]


def test_setup_corrections_disable_removes_generated_files(tmp_path: Path) -> None:
    repo = tmp_path
    mod_root = repo / "mod" / "test-mod"
    repo.joinpath("constructor.toml").write_text(
        '[project]\nmod_root = "mod/test-mod"\n',
        encoding="utf-8",
    )
    for relative in cli.SETUP_CORRECTION_OUTPUTS:
        path = mod_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(cli.SETUP_CORRECTION_GENERATED_MARKER + "\n", encoding="utf-8")

    assert cli.main(["--repo", str(repo), "setup-corrections", "--disable"]) == 0

    assert all(not (mod_root / relative).exists() for relative in cli.SETUP_CORRECTION_OUTPUTS)


def test_finalize_command_runs_constructor_finalizer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    calls: list[Path] = []

    monkeypatch.setattr(
        cli,
        "_finalize_constructor_mod",
        lambda repo_arg, project_arg: calls.append(project_arg),
    )

    assert cli.main(["--repo", str(repo), "finalize"]) == 0

    assert calls == [repo / "constructor.toml"]


def test_constructor_text_bom_finalizer_scans_game_loaded_files(tmp_path: Path) -> None:
    mod_root = tmp_path / "mod" / "test-mod"
    scripted_trigger = mod_root / "in_game" / "common" / "scripted_triggers" / "pp_test.txt"
    setup_start = mod_root / "main_menu" / "setup" / "start" / "07_test.txt"
    setup_country = mod_root / "main_menu" / "setup" / "countries" / "pp_test.txt"
    metadata = mod_root / ".metadata" / "metadata.json"
    scripted_trigger.parent.mkdir(parents=True)
    setup_start.parent.mkdir(parents=True)
    setup_country.parent.mkdir(parents=True)
    metadata.parent.mkdir(parents=True)
    scripted_trigger.write_bytes('pp_test = { name = "café" }\r\n'.encode("cp1252"))
    setup_start.write_text("locations={\n\tstockholm={ rank = town }\n}\n", encoding="utf-8-sig")
    setup_country.write_text("countries={ countries={ SWE={ capital = stockholm } } }\n", encoding="utf-8")
    metadata.write_text("{}", encoding="utf-8")

    cli._ensure_constructor_text_boms(mod_root)

    raw = scripted_trigger.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert raw.decode("utf-8-sig") == 'pp_test = { name = "café" }\r\n'
    assert not setup_start.read_bytes().startswith(b"\xef\xbb\xbf")
    assert setup_start.read_text(encoding="utf-8") == "locations={\n\tstockholm={ rank = town }\n}\n"
    assert setup_country.read_bytes().startswith(b"\xef\xbb\xbf")
    assert not metadata.read_bytes().startswith(b"\xef\xbb\xbf")


def test_clean_game_rule_presets_removes_mod_settings_only(tmp_path: Path) -> None:
    repo = tmp_path
    mod_root = repo / "mod" / "test-mod"
    game_rules = mod_root / "main_menu" / "common" / "game_rules" / "pp_rules.txt"
    preset = repo / "eu5-user" / "player" / "game_rules" / "presets.txt"
    repo.joinpath("constructor.toml").write_text(
        '[project]\nmod_root = "mod/test-mod"\n',
        encoding="utf-8",
    )
    game_rules.parent.mkdir(parents=True)
    game_rules.write_text(
        "pp_test_rule = {\n"
        "\tdefault = pp_test_normal\n"
        "\tpp_test_normal = { flag = general_rule }\n"
        "\tpp_test_hard = { flag = general_rule }\n"
        "}\n",
        encoding="utf-8-sig",
    )
    preset.parent.mkdir(parents=True)
    preset.write_text(
        'game_rules_preset={\n\tname="LastAppliedRules"\n'
        "\tsetting={ player_normal_difficulty pp_test_normal ai_normal_difficulty pp_test_hard pp_ai_building_maintenance_normal }\n"
        "\tironman=no\n}\n",
        encoding="utf-8-sig",
    )

    assert cli.main(["--repo", str(repo), "clean-game-rule-presets", "--preset", str(preset)]) == 0

    text = preset.read_text(encoding="utf-8-sig")
    assert "pp_test_normal" not in text
    assert "pp_test_hard" not in text
    assert "pp_ai_building_maintenance_normal" not in text
    assert "player_normal_difficulty" in text
    assert "ai_normal_difficulty" in text
    assert preset.read_bytes().startswith(b"\xef\xbb\xbf")


def test_sync_requires_explicit_confirmation(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    with pytest.raises(SystemExit, match="without explicit confirmation"):
        cli.main(["--repo", str(repo), "sync"])


def test_sync_smart_skips_unchanged_build_stages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    (repo / "constructor.local.toml").write_text("[deploy]\ntarget = 'live'\n", encoding="utf-8")
    state_path = repo / cli.SYNC_STATE_PATH
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps(
            {
                "labeling": "label",
                "blueprints": "blueprints",
                "population_capacity": "population",
                "validation": "validation",
            }
        ),
        encoding="utf-8",
    )
    calls: list[list[str]] = []
    finalized: list[Path] = []

    monkeypatch.setattr(
        cli,
        "_sync_stage_fingerprints",
        lambda repo_arg, project_arg: {
            "labeling": "label",
            "blueprints": "blueprints",
            "population_capacity": "population",
        },
    )
    monkeypatch.setattr(cli, "_validation_fingerprint", lambda repo_arg, project_arg: "validation")
    monkeypatch.setattr(
        cli,
        "_finalize_constructor_mod",
        lambda repo_arg, project_arg: finalized.append(project_arg),
    )

    def fake_run(command, cwd):
        calls.append([str(part) for part in command])
        assert cwd == repo
        return 0

    monkeypatch.setattr(cli, "_run", fake_run)

    assert cli.main(["--repo", str(repo), "sync", "--yes"]) == 0

    assert calls == [
        ["eu5-orchestrator", "deploy", "--project", str(repo / "constructor.toml"), "--clean"]
    ]
    assert finalized == [repo / "constructor.toml"]


def test_sync_smart_runs_changed_stages_and_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    (repo / "constructor.local.toml").write_text("[deploy]\ntarget = 'live'\n", encoding="utf-8")
    state_path = repo / cli.SYNC_STATE_PATH
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps(
            {
                "labeling": "old-label",
                "blueprints": "blueprints",
                "population_capacity": "old-population",
                "validation": "old-validation",
            }
        ),
        encoding="utf-8",
    )
    calls: list[list[str]] = []
    finalized: list[Path] = []

    monkeypatch.setattr(
        cli,
        "_sync_stage_fingerprints",
        lambda repo_arg, project_arg: {
            "labeling": "new-label",
            "blueprints": "blueprints",
            "population_capacity": "new-population",
        },
    )
    monkeypatch.setattr(cli, "_validation_fingerprint", lambda repo_arg, project_arg: "new-validation")
    monkeypatch.setattr(cli, "_finalize_constructor_mod", lambda repo_arg, project_arg: finalized.append(project_arg))

    def fake_run(command, cwd):
        calls.append([str(part) for part in command])
        assert cwd == repo
        return 0

    monkeypatch.setattr(cli, "_run", fake_run)

    assert cli.main(["--repo", str(repo), "sync", "--yes"]) == 0

    assert calls == [
        ["eu5-orchestrator", "label", "--project", str(repo / "constructor.toml")],
        ["eu5-orchestrator", "population-capacity", "render", "--project", str(repo / "constructor.toml")],
        ["eu5-orchestrator", "validate", "--project", str(repo / "constructor.toml")],
        ["eu5-orchestrator", "deploy", "--project", str(repo / "constructor.toml"), "--clean"],
    ]
    assert finalized == [repo / "constructor.toml"]
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved["labeling"] == "new-label"
    assert saved["blueprints"] == "blueprints"
    assert saved["population_capacity"] == "new-population"
    assert saved["validation"] == "new-validation"


def test_sync_force_build_runs_all_smart_stages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    (repo / "constructor.local.toml").write_text("[deploy]\ntarget = 'live'\n", encoding="utf-8")
    state_path = repo / cli.SYNC_STATE_PATH
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps(
            {
                "labeling": "label",
                "blueprints": "blueprints",
                "population_capacity": "population",
                "validation": "validation",
            }
        ),
        encoding="utf-8",
    )
    calls: list[list[str]] = []
    finalized: list[Path] = []

    monkeypatch.setattr(
        cli,
        "_sync_stage_fingerprints",
        lambda repo_arg, project_arg: {
            "labeling": "label",
            "blueprints": "blueprints",
            "population_capacity": "population",
        },
    )
    monkeypatch.setattr(cli, "_validation_fingerprint", lambda repo_arg, project_arg: "validation")
    monkeypatch.setattr(cli, "_finalize_constructor_mod", lambda repo_arg, project_arg: finalized.append(project_arg))

    def fake_run(command, cwd):
        calls.append([str(part) for part in command])
        assert cwd == repo
        return 0

    monkeypatch.setattr(cli, "_run", fake_run)

    assert cli.main(["--repo", str(repo), "sync", "--yes", "--force-build"]) == 0

    assert calls == [
        ["eu5-orchestrator", "label", "--project", str(repo / "constructor.toml")],
        ["eu5-orchestrator", "render", "--project", str(repo / "constructor.toml"), "--overwrite"],
        ["eu5-orchestrator", "population-capacity", "render", "--project", str(repo / "constructor.toml")],
        ["eu5-orchestrator", "validate", "--project", str(repo / "constructor.toml")],
        ["eu5-orchestrator", "deploy", "--project", str(repo / "constructor.toml"), "--clean"],
    ]
    assert finalized == [repo / "constructor.toml"]


def test_sync_full_build_and_force_deploy_use_recovery_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    (repo / "constructor.local.toml").write_text("[deploy]\ntarget = 'live'\n", encoding="utf-8")
    calls: list[list[str]] = []
    recorded: list[Path] = []

    monkeypatch.setattr(cli, "_finalize_constructor_mod", lambda repo_arg, project_arg: None)
    monkeypatch.setattr(cli, "_record_current_sync_state", lambda repo_arg, project_arg: recorded.append(project_arg))

    def fake_run(command, cwd):
        calls.append([str(part) for part in command])
        assert cwd == repo
        return 0

    monkeypatch.setattr(cli, "_run", fake_run)

    assert cli.main(["--repo", str(repo), "sync", "--yes", "--full-build", "--force-deploy"]) == 0

    assert calls == [
        ["eu5-orchestrator", "build", "--project", str(repo / "constructor.toml"), "--overwrite"],
        ["eu5-orchestrator", "deploy", "--project", str(repo / "constructor.toml"), "--clean", "--force"],
    ]
    assert recorded == [repo / "constructor.toml"]


def test_build_finalizes_location_potential_localization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    repo.joinpath("constructor.toml").write_text(
        '[project]\nmod_root = "mod/test-mod"\n',
        encoding="utf-8",
    )
    mod_root = repo / "mod" / "test-mod"
    static_modifiers = mod_root / "main_menu" / "common" / "static_modifiers"
    localization = mod_root / "main_menu" / "localization" / "english"
    modifier_localization_path = localization / "pp_location_modifiers_l_english.yml"
    europedia_localization_path = localization / "pp_europedia_l_english.yml"
    static_modifiers.mkdir(parents=True)
    localization.mkdir(parents=True)
    (static_modifiers / "pp_location_modifiers.txt").write_text(
        "pp_loc_slagelse = {\n"
        "\tgame_data = { category = location }\n"
        "\tlocal_fish_output_modifier = 0.1\n"
        "}\n"
        "pp_loc_washita = {\n"
        "\tlocal_grain_output_modifier = 0.15\n"
        "}\n"
        "pp_loc_sant_feliu = {\n"
        "\tlocal_medicaments_output_modifier = 0.2\n"
        "}\n",
        encoding="utf-8",
    )
    modifier_localization_path.write_text(
        '\ufeffl_english:\n'
        ' pp_location_modifiers_title: "Prosper or Perish per-location suitability"\n'
        ' pp_location_modifiers_title_desc: "stale"\n',
        encoding="utf-8",
    )
    europedia_localization_path.write_text("l_english:\n", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(command, cwd):
        calls.append([str(part) for part in command])
        assert cwd == repo
        return 0

    def fake_farming_capacity_bridge(build_repo, bridge_mod_root):
        assert build_repo == repo
        assert bridge_mod_root == mod_root

    monkeypatch.setattr(cli, "_run", fake_run)
    monkeypatch.setattr(
        cli,
        "_ensure_farming_capacity_raw_modifier_bridges",
        fake_farming_capacity_bridge,
    )

    assert cli.main(["--repo", str(repo), "build"]) == 0

    modifier_text = modifier_localization_path.read_text(encoding="utf-8-sig")
    europedia_text = europedia_localization_path.read_text(encoding="utf-8-sig")
    assert calls == [
        ["eu5-orchestrator", "build", "--project", str(repo / "constructor.toml"), "--overwrite"]
    ]
    static_text = (static_modifiers / "pp_location_modifiers.txt").read_text(encoding="utf-8-sig")
    assert "pp_loc_washita_pp = {" in static_text
    assert "pp_loc_washita = {" not in static_text
    assert 'pp_location_potential_modifier_name: "[pp_location_potential|e]"' in modifier_text
    assert 'STATIC_MODIFIER_NAME_pp_loc_slagelse: "$pp_location_potential_modifier_name$"' in modifier_text
    assert 'STATIC_MODIFIER_DESC_pp_loc_slagelse: "$pp_location_potential_modifier_desc$"' in modifier_text
    assert 'STATIC_MODIFIER_DESC_pp_loc_washita_pp: "$pp_location_potential_modifier_desc$"' in modifier_text
    assert 'STATIC_MODIFIER_DESC_pp_loc_washita: "$pp_location_potential_modifier_desc$"' not in modifier_text
    assert "pp_location_modifiers_title:" not in modifier_text
    assert 'game_concept_pp_location_potential: "Location Potential"' in europedia_text
    assert "\\n\\nThe values combine" in europedia_text
    fixed_time = 1_700_000_000_000_000_000
    os.utime(modifier_localization_path, ns=(fixed_time, fixed_time))
    os.utime(europedia_localization_path, ns=(fixed_time, fixed_time))

    cli._inject_location_potential_localization(mod_root)

    assert modifier_localization_path.stat().st_mtime_ns == fixed_time
    assert europedia_localization_path.stat().st_mtime_ns == fixed_time


def test_finalize_keeps_location_modifier_on_action_separate_and_preserves_newlines(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _repo(tmp_path)
    repo.joinpath("constructor.toml").write_text(
        '[project]\nmod_root = "mod/test-mod"\n',
        encoding="utf-8",
    )
    mod_root = repo / "mod" / "test-mod"
    static_modifiers = mod_root / "main_menu" / "common" / "static_modifiers"
    game_concepts = mod_root / "main_menu" / "common" / "game_concepts"
    on_action = mod_root / "in_game" / "common" / "on_action"
    building_types = mod_root / "in_game" / "common" / "building_types"
    script_values = mod_root / "in_game" / "common" / "script_values"
    scripted_effects = mod_root / "in_game" / "common" / "scripted_effects"
    localization = mod_root / "main_menu" / "localization" / "english"
    static_modifiers.mkdir(parents=True)
    game_concepts.mkdir(parents=True)
    on_action.mkdir(parents=True)
    building_types.mkdir(parents=True)
    script_values.mkdir(parents=True)
    scripted_effects.mkdir(parents=True)
    localization.mkdir(parents=True)

    location_modifiers = static_modifiers / "pp_location_modifiers.txt"
    location_modifiers.write_text(
        "pp_loc_washita = {\r\n"
        "\tgame_data = { category = location }\r\n"
        "\tlocal_grain_output_modifier = 0.15\r\n"
        "}\r\n",
        encoding="utf-8",
        newline="",
    )
    apply_location_modifiers = on_action / "pp_apply_location_modifiers.txt"
    apply_location_modifiers.write_text(
        "# generated\n\n"
        "on_game_start = {\n"
        "\teffect = {\n"
        "\t\tlocation:washita = {\n"
        "\t\t\tadd_location_modifier = { modifier = pp_loc_washita months = -1 mode = replace }\n"
        "\t\t}\n"
        "\t}\n"
        "}\n",
        encoding="utf-8",
        newline="",
    )
    game_start = on_action / "pp_game_start.txt"
    original_game_start = (
        "\ufeffon_game_start = {\r\n"
        "\ton_actions = {\r\n"
        "\t\t# pp_reset_rgo_max_workers\r\n"
        "\t\tpp_apply_location_modifiers\r\n"
        "\t\tpp_mod_welcome_situation_game_start\r\n"
        "\t}\r\n"
        "}\r\n"
    )
    game_start.write_text(original_game_start, encoding="utf-8", newline="")
    (localization / "pp_location_modifiers_l_english.yml").write_text("l_english:\n", encoding="utf-8")
    (localization / "pp_europedia_l_english.yml").write_text("l_english:\n", encoding="utf-8")
    capacity_bom_paths = (
        game_concepts / "pp_fish_capacity.txt",
        game_concepts / "pp_forest_capacity.txt",
        building_types / "pp_mercury_patio_adjustments.txt",
        script_values / "pp_building_capacity_values.txt",
        scripted_effects / "pp_capacity_precalc.txt",
        scripted_effects / "pp_capacity_culling_effects.txt",
        on_action / "pp_building_capacity_culling_v2.txt",
    )
    for path in capacity_bom_paths:
        path.write_text("# generated\n", encoding="utf-8")

    def fake_farming_capacity_bridge(build_repo, bridge_mod_root):
        assert build_repo == repo
        assert bridge_mod_root == mod_root

    monkeypatch.setattr(
        cli,
        "_ensure_farming_capacity_raw_modifier_bridges",
        fake_farming_capacity_bridge,
    )

    cli._finalize_constructor_mod(repo, repo / "constructor.toml")

    location_bytes = location_modifiers.read_bytes()
    apply_bytes = apply_location_modifiers.read_bytes()
    game_start_bytes = game_start.read_bytes()

    assert location_bytes.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" in location_bytes
    assert location_bytes.count(b"\n") == location_bytes.count(b"\r\n")
    assert apply_bytes.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in apply_bytes
    assert (
        b"on_game_start = {\n\ton_actions = {\n\t\tpp_apply_location_modifiers\n\t}\n}\n\n"
        b"pp_apply_location_modifiers = {\n\teffect = {"
    ) in apply_bytes
    assert b"pp_loc_washita_pp" in apply_bytes
    assert game_start_bytes == original_game_start.encode("utf-8")
    for path in capacity_bom_paths:
        assert path.read_bytes().startswith(b"\xef\xbb\xbf")


def test_build_does_not_finalize_after_failed_orchestrator_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    finalized = False

    def fake_run(command, cwd):
        assert cwd == repo
        return 7

    def fake_finalize(build_repo, project):
        nonlocal finalized
        finalized = True

    monkeypatch.setattr(cli, "_run", fake_run)
    monkeypatch.setattr(cli, "_finalize_constructor_mod", fake_finalize)

    assert cli.main(["--repo", str(repo), "build"]) == 7
    assert not finalized


def test_publish_docs_copies_generated_graphs_and_assets(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    graphs = repo / "graphs"
    graphs.mkdir()
    (graphs / "goods_flow_explorer.html").write_text(f"goods {repo.as_posix()}/mod/file.txt\n")
    (graphs / "savegame_explorer.html").write_text("savegame\n")
    (graphs / "europedia.html").write_text("europedia\n")
    (graphs / "europedia_entries.json").write_text("{}\n")
    (graphs / "assets").mkdir()
    (graphs / "assets" / "icon.svg").write_text("<svg />\n")

    assert cli.main(["--repo", str(repo), "publish-docs"]) == 0

    assert (
        repo / "docs" / "examples" / "goods_flow_explorer.html"
    ).read_text() == "goods <constructor-repo>/mod/file.txt\n"
    assert (repo / "docs" / "examples" / "savegame_explorer.html").read_text() == "savegame\n"
    assert (repo / "docs" / "examples" / "europedia.html").read_text() == "europedia\n"
    assert (repo / "docs" / "examples" / "europedia_entries.json").read_text() == "{}\n"
    assert (repo / "docs" / "examples" / "assets" / "icon.svg").read_text() == "<svg />\n"


def test_europedia_generates_and_publishes_export(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _write_minimal_europedia_sources(repo)

    assert cli.main(["--repo", str(repo), "europedia"]) == 0

    graph_html = repo / "graphs" / "europedia.html"
    graph_json = repo / "graphs" / "europedia_entries.json"
    docs_html = repo / "docs" / "examples" / "europedia.html"
    docs_json = repo / "docs" / "examples" / "europedia_entries.json"
    assert graph_html.exists()
    assert graph_json.exists()
    assert docs_html.read_text(encoding="utf-8") == graph_html.read_text(encoding="utf-8")
    assert docs_json.read_text(encoding="utf-8") == graph_json.read_text(encoding="utf-8")

    payload = json.loads(graph_json.read_text(encoding="utf-8"))
    assert payload["metadata"]["entry_count"] == 1
    assert payload["entries"][0]["title"] == "P&P: Food Production"
    assert "const europediaPayload =" in graph_html.read_text(encoding="utf-8")


def test_analyze_runs_orchestrator_then_publishes_goods_flow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    calls: list[list[str]] = []

    def fake_run(command, cwd):
        calls.append([str(part) for part in command])
        assert cwd == repo
        (repo / "graphs").mkdir(exist_ok=True)
        (repo / "graphs" / "goods_flow_explorer.html").write_text("goods\n")
        return 0

    monkeypatch.setattr(cli, "_run", fake_run)

    assert cli.main(["--repo", str(repo), "analyze"]) == 0

    assert calls == [
        [
            "eu5-orchestrator",
            "analyze",
            "--project",
            str(repo / "constructor.toml"),
        ]
    ]
    assert (repo / "docs" / "examples" / "goods_flow_explorer.html").read_text() == "goods\n"


def test_output_modifiers_prints_cumulative_age_table_sorted_by_final_total(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _repo(tmp_path)

    def fake_inputs(*, profile: str, load_order_path: Path):
        assert profile == "constructor"
        assert load_order_path == repo / "constructor.load_order.toml"
        return (
            ["coal", "fish", "wheat"],
            [
                {"good": "wheat", "age": "age_1_traditions", "value": 0.1},
                {"good": "wheat", "age": "age_2_renaissance", "value": 0.05},
                {"good": "coal", "age": "age_2_renaissance", "value": 0.1},
                {"good": "fish", "age": "age_1_traditions", "value": 0.04},
                {
                    "good": "fish",
                    "age": "age_2_renaissance",
                    "value": 0.2,
                    "has_potential": True,
                },
            ],
            ["age_1_traditions", "age_2_renaissance"],
        )

    monkeypatch.setattr(cli, "_load_output_modifier_inputs", fake_inputs)

    assert cli.main(["--repo", str(repo), "output-modifiers"]) == 0

    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split() == ["good", "age_1_traditions", "age_2_renaissance"]
    assert [line.split()[0] for line in lines[2:]] == ["wheat", "coal", "fish"]
    assert lines[2].split() == ["wheat", "0.10", "0.15"]
    assert lines[3].split() == ["coal", "0.00", "0.10"]
    assert lines[4].split() == ["fish", "0.04", "0.04"]


def test_output_modifiers_can_include_specific_gated_modifiers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _repo(tmp_path)

    monkeypatch.setattr(
        cli,
        "_load_output_modifier_inputs",
        lambda *, profile, load_order_path: (
            ["fish", "wheat"],
            [
                {"good": "wheat", "age": "age_1_traditions", "value": 0.1},
                {
                    "good": "fish",
                    "age": "age_2_renaissance",
                    "value": 0.2,
                    "has_potential": True,
                },
            ],
            ["age_1_traditions", "age_2_renaissance"],
        ),
    )

    assert cli.main(["--repo", str(repo), "output-modifiers", "--include-specific"]) == 0

    lines = capsys.readouterr().out.splitlines()
    assert [line.split()[0] for line in lines[2:]] == ["fish", "wheat"]
    assert lines[2].split() == ["fish", "0.00", "0.20"]
    assert lines[3].split() == ["wheat", "0.10", "0.10"]


def test_food_revenue_check_prints_parsed_price_and_rank_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _repo(tmp_path)

    def fake_inputs(*, profile: str, load_order_path: Path, project: Path):
        assert profile == "constructor"
        assert load_order_path == repo / "constructor.load_order.toml"
        assert project == repo / "constructor.toml"
        return {
            "growth_cap": 2.0,
            "static": {
                "cheap_food_in_location": -1.124,
                "expensive_food_in_location": 0.310,
                "positive_province_food_growth": -0.054,
                "province_starving": 0.1,
            },
            "ranks": {
                "rural_settlement": 0.170,
                "town": 0.195,
                "city": 0.220,
                "megalopolis": 0.245,
            },
            "profitability_rows": [
                {
                    "scenario": "cheap_50",
                    "food_price": "50%",
                    "input_gold": 5.23,
                    "goods_input_gold": 5.0,
                    "worker_food_gold": 0.23,
                    "base_output_gold": 5.05,
                    "required_output_modifier": 5.23 / 5.05 - 1.0,
                    "actual_output_modifier": -0.281,
                    "modifier_margin": -0.281 - (5.23 / 5.05 - 1.0),
                    "output_gold": 3.630,
                    "profit_gold": -1.600,
                    "profitable": False,
                },
                {
                    "scenario": "base_100",
                    "food_price": "100%",
                    "input_gold": 5.36,
                    "goods_input_gold": 5.0,
                    "worker_food_gold": 0.36,
                    "base_output_gold": 5.05,
                    "required_output_modifier": 5.36 / 5.05 - 1.0,
                    "actual_output_modifier": 0.0,
                    "modifier_margin": -(5.36 / 5.05 - 1.0),
                    "output_gold": 5.05,
                    "profit_gold": -0.31,
                    "profitable": False,
                },
                {
                    "scenario": "expensive_150",
                    "food_price": "150%",
                    "input_gold": 5.52,
                    "goods_input_gold": 5.0,
                    "worker_food_gold": 0.52,
                    "base_output_gold": 5.05,
                    "required_output_modifier": 5.52 / 5.05 - 1.0,
                    "actual_output_modifier": 0.077,
                    "modifier_margin": 0.077 - (5.52 / 5.05 - 1.0),
                    "output_gold": 5.439,
                    "profit_gold": -0.081,
                    "profitable": False,
                },
            ],
            "warnings": [],
        }

    monkeypatch.setattr(cli, "_load_food_revenue_check_inputs", fake_inputs)

    assert cli.main(["--repo", str(repo), "food-revenue-check"]) == 0

    output = capsys.readouterr().out
    assert "cheap cap effect (food price 0x)" in output
    lines = output.splitlines()
    cheap_50_line = next(line for line in lines if line.startswith("cheap_50"))
    assert cheap_50_line.split() == ["cheap_50", "-0.281", "0.719"]
    rural_summary_line = next(line for line in lines if line.startswith("rural_settlement"))
    assert rural_summary_line.split()[:3] == ["rural_settlement", "+0.062", "-0.500"]
    threshold_start = lines.index("victuals market base-condition profitability:")
    threshold_rows = lines[threshold_start + 3 : threshold_start + 6]
    assert threshold_rows[0].split() == [
        "cheap_50",
        "50%",
        "5.230",
        "5.050",
        "+0.036",
        "-0.281",
        "-0.317",
        "3.630",
        "-1.600",
        "loss",
    ]
    assert threshold_rows[1].split() == [
        "base_100",
        "100%",
        "5.360",
        "5.050",
        "+0.061",
        "+0.000",
        "-0.061",
        "5.050",
        "-0.310",
        "loss",
    ]
    rank_threshold_start = lines.index(
        "victuals market base price + full storage profitability by rank:"
    )
    rank_threshold_rows = lines[rank_threshold_start + 3 : rank_threshold_start + 7]
    assert rank_threshold_rows[0].split() == [
        "rural_settlement",
        "+0.062",
        "5.363",
        "+0.003",
        "+0.363",
        "profit",
    ]
    assert [row.split()[0] for row in rank_threshold_rows] == [
        "rural_settlement",
        "town",
        "city",
        "megalopolis",
    ]
    assert [row.split()[-1] for row in rank_threshold_rows] == ["profit"] * 4
    matrix_start = lines.index("full edge matrix (48 rows):")
    matrix_rows = lines[matrix_start + 3 : matrix_start + 51]
    assert len(matrix_rows) == 48
    assert all(row.endswith("ok") for row in matrix_rows)
    assert matrix_rows[0].split() == [
        "rural_settlement",
        "cheap_cap_0x",
        "empty",
        "no",
        "+0.170",
        "-0.562",
        "+0.000",
        "+0.000",
        "-0.392",
        "0.608",
        "ok",
    ]
    assert matrix_rows[-1].split() == [
        "megalopolis",
        "expensive_cap_2x",
        "full",
        "yes",
        "+0.245",
        "+0.155",
        "-0.108",
        "+0.100",
        "+0.392",
        "1.392",
        "ok",
    ]
    assert "result=ok" in output


def test_food_revenue_storage_target_solver_uses_configured_edge() -> None:
    edge = ("rural_settlement", "cheap_cap_0x", "full", "no")

    full_target = cli._food_revenue_storage_full_target_for_edge(
        edge,
        matrix_targets={edge: -0.5},
        rank_targets={"rural_settlement": 0.170},
        price_targets={"cheap_cap_0x": -0.562},
        starving_targets={"no": 0.0},
    )
    raw_target = cli._food_revenue_storage_raw_target_for_edge(
        edge,
        growth_cap=2.0,
        matrix_targets={edge: -0.5},
        rank_targets={"rural_settlement": 0.170},
        price_targets={"cheap_cap_0x": -0.562},
        starving_targets={"no": 0.0},
    )

    assert full_target == pytest.approx(-0.108)
    assert raw_target == pytest.approx(-0.054)


def test_food_revenue_storage_target_solver_reacts_to_desired_floor() -> None:
    edge = ("rural_settlement", "cheap_cap_0x", "full", "no")

    raw_target = cli._food_revenue_storage_raw_target_for_edge(
        edge,
        growth_cap=2.0,
        matrix_targets={edge: -0.55},
        rank_targets={"rural_settlement": 0.170},
        price_targets={"cheap_cap_0x": -0.562},
        starving_targets={"no": 0.0},
    )

    assert raw_target == pytest.approx(-0.079)


def test_food_revenue_check_fails_when_matrix_total_leaves_band(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _repo(tmp_path)

    monkeypatch.setattr(
        cli,
        "_load_food_revenue_check_inputs",
        lambda *, profile, load_order_path, project: {
            "growth_cap": 2.0,
            "static": {
                "cheap_food_in_location": -1.4,
                "expensive_food_in_location": 1.4,
                "positive_province_food_growth": -0.15,
                "province_starving": 0.1,
            },
            "ranks": {
                "rural_settlement": 0.5,
                "town": 0.525,
                "city": 0.55,
                "megalopolis": 0.6,
            },
            "profitability_rows": [],
            "warnings": [],
        },
    )

    assert cli.main(["--repo", str(repo), "food-revenue-check"]) == 1

    output = capsys.readouterr().out
    assert "matrix band failures:" in output
    assert "megalopolis       expensive_cap_2x  empty    yes" in output
    assert "+1.400" in output
    assert "FAIL" in output
    assert "result=fail" in output


def test_food_revenue_profitability_threshold_uses_scenario_input_and_base_output() -> None:
    method = SimpleNamespace(
        food_cost_scenarios=[
            SimpleNamespace(
                scenario="cheap_50",
                input_gold=5.23,
                output_gold=4.14605,
                output_multiplier=0.821,
                output_modifier=-0.179,
                profit_gold=-1.08395,
                worker_food_gold=0.23,
            )
        ]
    )

    rows = cli._food_revenue_profitability_rows_from_method(method)

    assert rows[0]["base_output_gold"] == pytest.approx(5.05)
    assert rows[0]["required_output_modifier"] == pytest.approx(5.23 / 5.05 - 1.0)
    assert rows[0]["modifier_margin"] == pytest.approx(-0.179 - (5.23 / 5.05 - 1.0))
    assert rows[0]["goods_input_gold"] == pytest.approx(5.0)
    assert rows[0]["profitable"] is False


def test_food_revenue_output_modifier_values_use_three_decimal_precision() -> None:
    paths = [
        ROOT
        / "mod"
        / "Prosper or Perish (Population Growth & Food Rework)"
        / "main_menu"
        / "common"
        / "static_modifiers"
        / "pp_location_modifier_adjustments.txt",
        ROOT
        / "mod"
        / "Prosper or Perish (Population Growth & Food Rework)"
        / "in_game"
        / "common"
        / "location_ranks"
        / "pp_location_rank_adjustments.txt",
    ]
    pattern = re.compile(r"\blocal_food_revenue_output_modifier\s*=\s*(-?\d+\.(\d+))\b")
    matches = []

    for path in paths:
        for match in pattern.finditer(path.read_text(encoding="utf-8-sig")):
            matches.append(match.group(1))
            assert len(match.group(2)) <= 3, match.group(1)

    assert matches


def test_production_throughput_prints_best_available_building_slot_sums(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _repo(tmp_path)

    def fake_inputs(*, profile: str, load_order_path: Path, include_specific: bool):
        assert profile == "constructor"
        assert load_order_path == repo / "constructor.load_order.toml"
        assert include_specific is False
        return (
            ["berries", "tools", "victuals"],
            [
                {
                    "name": "cookery_slot_0_low",
                    "building": "cookery",
                    "production_method_group_index": 0,
                    "produced": "victuals",
                    "input_goods": ["grain"],
                    "input_amounts": [1.0],
                    "input_cost": 2.0,
                    "output_value": 3.0,
                    "effective_availability_kind": "available_by_default",
                },
                {
                    "name": "cookery_slot_0_high",
                    "building": "cookery",
                    "production_method_group_index": 0,
                    "produced": "victuals",
                    "input_goods": ["meat"],
                    "input_amounts": [1.0],
                    "input_cost": 4.0,
                    "output_value": 4.0,
                    "effective_availability_kind": "available_by_default",
                },
                {
                    "name": "cookery_slot_1",
                    "building": "cookery",
                    "production_method_group_index": 1,
                    "produced": "victuals",
                    "input_goods": ["wine"],
                    "input_amounts": [1.0],
                    "input_cost": 1.25,
                    "output_value": 1.25,
                    "effective_availability_kind": "available_by_default",
                },
                {
                    "name": "yard_slot_0",
                    "building": "victualling_yard",
                    "production_method_group_index": 0,
                    "produced": "victuals",
                    "input_goods": ["meat"],
                    "input_amounts": [2.0],
                    "input_cost": 6.0,
                    "output_value": 6.0,
                    "effective_availability_kind": "unlocked_by_advancement",
                    "effective_unlock_age": "age_2_renaissance",
                },
                {
                    "name": "yard_slot_1",
                    "building": "victualling_yard",
                    "production_method_group_index": 1,
                    "produced": "victuals",
                    "input_goods": ["salt"],
                    "input_amounts": [1.0],
                    "input_cost": 2.0,
                    "output_value": 2.0,
                    "effective_availability_kind": "unlocked_by_advancement",
                    "effective_unlock_age": "age_2_renaissance",
                },
                {
                    "name": "specific_victuals",
                    "building": "specific_kitchen",
                    "production_method_group_index": 0,
                    "produced": "victuals",
                    "input_goods": ["grain"],
                    "input_amounts": [1.0],
                    "input_cost": 100.0,
                    "output_value": 100.0,
                    "effective_availability_kind": "specific_only",
                    "effective_unlock_age": "age_1_traditions",
                },
                {
                    "name": "tools_output_only",
                    "building": "workshop",
                    "production_method_group_index": 0,
                    "produced": "tools",
                    "input_goods": [],
                    "input_amounts": [],
                    "input_cost": 0.0,
                    "output_value": 99.0,
                    "effective_availability_kind": "available_by_default",
                },
                {
                    "name": "tools_no_input_cost",
                    "building": "workshop",
                    "production_method_group_index": 0,
                    "produced": "tools",
                    "input_goods": ["wood"],
                    "input_amounts": [1.0],
                    "input_cost": 0.0,
                    "output_value": 99.0,
                    "effective_availability_kind": "available_by_default",
                },
                {
                    "name": "tools_valid",
                    "building": "workshop",
                    "production_method_group_index": 0,
                    "produced": "tools",
                    "input_goods": ["wood"],
                    "input_amounts": [1.0],
                    "input_cost": 2.345,
                    "output_value": 3.456,
                    "effective_availability_kind": "available_by_default",
                },
            ],
            ["age_1_traditions", "age_2_renaissance"],
        )

    monkeypatch.setattr(cli, "_load_production_throughput_inputs", fake_inputs)

    assert cli.main(["--repo", str(repo), "production-throughput"]) == 0

    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split() == ["good", "age_1_traditions", "age_2_renaissance"]
    assert [line.split()[0] for line in lines[2:]] == ["victuals", "tools", "berries"]
    assert lines[2].split() == ["victuals", "10.50", "16.00"]
    assert lines[3].split() == ["tools", "5.80", "5.80"]
    assert lines[4].split() == ["berries", "0.00", "0.00"]


def test_production_throughput_can_include_specific_gated_methods(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _repo(tmp_path)

    def fake_inputs(*, profile: str, load_order_path: Path, include_specific: bool):
        assert include_specific is True
        return (
            ["fish"],
            [
                {
                    "name": "specific_fishery",
                    "building": "fishery",
                    "production_method_group_index": 0,
                    "produced": "fish",
                    "input_goods": ["salt"],
                    "input_amounts": [1.0],
                    "input_cost": 1.5,
                    "output_value": 2.5,
                    "effective_availability_kind": "specific_only",
                    "effective_unlock_age": "age_2_renaissance",
                },
            ],
            ["age_1_traditions", "age_2_renaissance"],
        )

    monkeypatch.setattr(cli, "_load_production_throughput_inputs", fake_inputs)

    assert cli.main(["--repo", str(repo), "production-throughput", "--include-specific"]) == 0

    lines = capsys.readouterr().out.splitlines()
    assert lines[2].split() == ["fish", "0.00", "4.00"]


def test_dashboard_serves_current_capacity_map(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    dashboard = repo / "artifacts" / "data" / "population_capacity" / "current_capacity_map"
    dashboard.mkdir(parents=True)
    (dashboard / "index.html").write_text("<!doctype html>\n")
    calls: list[list[str]] = []

    def fake_run(command, cwd):
        calls.append([str(part) for part in command])
        assert cwd == repo
        return 0

    monkeypatch.setattr(cli, "_run", fake_run)

    assert cli.main(["--repo", str(repo), "dashboard", "--port", "8765"]) == 0

    assert calls == [
        [
            cli.sys.executable,
            "-m",
            "http.server",
            "8765",
            "--bind",
            "127.0.0.1",
            "--directory",
            str(dashboard),
        ]
    ]


def test_dashboard_reports_missing_index(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    with pytest.raises(SystemExit, match="Dashboard index not found"):
        cli.main(["--repo", str(repo), "dashboard"])


def test_savegame_notebooks_build_ingests_raw_dataset_without_rewrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _repo(tmp_path)
    save_dir = tmp_path / "save games"
    save_dir.mkdir()
    (save_dir / "autosave.eu5").write_text("save\n")
    calls: list[list[str]] = []
    exports: list[tuple[Path, Path]] = []

    def fake_run(command, cwd):
        calls.append([str(part) for part in command])
        assert cwd == repo
        return 0

    def fake_run_collecting_output(command, cwd):
        calls.append([str(part) for part in command])
        assert cwd == repo
        _write_savegame_manifest(repo, save_dir / "autosave.eu5")
        return 0, "processed: 0\nskipped: 1\n"

    monkeypatch.setattr(cli, "_run", fake_run)
    monkeypatch.setattr(cli, "_run_collecting_output", fake_run_collecting_output)
    monkeypatch.setattr(
        cli,
        "_export_savegame_notebook_global_webps",
        lambda *, repo, dataset, load_order, profile: exports.append((repo, dataset)),
    )

    assert (
        cli.main(
            ["--repo", str(repo), "savegame-notebooks", "build", "--save-dir", str(save_dir)]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "raw ingest skipped: no new saves processed (1 already digested)" in output
    assert "notebook rewrite: skipped (not required)" in output

    assert calls == [
        [
            "uv",
            "run",
            "eu5parse",
            "savegame",
            "ingest",
            "--save-dir",
            str(save_dir),
            "--output",
            str(repo / "graphs" / "dataset"),
            "--profile",
            "constructor",
            "--load-order",
            str(repo / "constructor.load_order.toml"),
            "--workers",
            "4",
        ]
    ]
    assert exports == [(repo, repo / "graphs" / "dataset")]


def test_savegame_notebooks_build_passes_extended_only_when_requested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    save_dir = repo / "saves"
    save_dir.mkdir()
    (save_dir / "autosave.eu5").write_text("SAV\nmetadata={}", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run_collecting_output(command, cwd):
        calls.append([str(part) for part in command])
        assert cwd == repo
        _write_savegame_manifest(repo, save_dir / "autosave.eu5")
        return 0, "processed: 0\nskipped: 1\n"

    monkeypatch.setattr(cli, "_run_collecting_output", fake_run_collecting_output)
    monkeypatch.setattr(cli, "_export_savegame_notebook_global_webps", lambda **kwargs: None)

    assert (
        cli.main(
            [
                "--repo",
                str(repo),
                "savegame-notebooks",
                "build",
                "--save-dir",
                str(save_dir),
                "--extended",
            ]
        )
        == 0
    )

    assert calls
    assert calls[0][-1] == "--extended"


def test_savegame_notebooks_build_no_ingest_reports_existing_raw_dataset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _repo(tmp_path)
    _write_savegame_manifest(repo)
    calls: list[list[str]] = []
    exports: list[Path] = []

    def fake_run(command, cwd):
        calls.append([str(part) for part in command])
        assert cwd == repo
        return 0

    monkeypatch.setattr(cli, "_run", fake_run)
    monkeypatch.setattr(
        cli,
        "_export_savegame_notebook_global_webps",
        lambda *, repo, dataset, load_order, profile: exports.append(dataset),
    )

    assert cli.main(["--repo", str(repo), "savegame-notebooks", "build", "--no-ingest"]) == 0
    output = capsys.readouterr().out
    assert f"raw dataset: {repo / 'graphs' / 'dataset'}" in output
    assert "notebook rewrite: skipped (not required)" in output

    assert calls == []
    assert exports == [repo / "graphs" / "dataset"]


def test_savegame_notebooks_build_no_webp_skips_global_exports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    _write_savegame_manifest(repo)
    exports: list[Path] = []

    monkeypatch.setattr(
        cli,
        "_export_savegame_notebook_global_webps",
        lambda *, repo, dataset, load_order, profile: exports.append(dataset),
    )

    assert cli.main(["--repo", str(repo), "savegame-notebooks", "build", "--no-ingest", "--no-webp"]) == 0

    assert exports == []


def test_savegame_notebooks_build_auto_detects_save_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    missing_home = tmp_path / "home" / "Documents" / "Paradox Interactive" / "Europa Universalis V" / "save games"
    save_dir = tmp_path / "windows" / "Documents" / "Paradox Interactive" / "Europa Universalis V" / "save games"
    missing_home.mkdir(parents=True)
    save_dir.mkdir(parents=True)
    (save_dir / "autosave.eu5").write_text("save\n")
    calls: list[list[str]] = []

    def fake_run(command, cwd):
        calls.append([str(part) for part in command])
        assert cwd == repo
        return 0

    def fake_run_collecting_output(command, cwd):
        calls.append([str(part) for part in command])
        assert cwd == repo
        return 0, "processed: 0\nskipped: 1\n"

    monkeypatch.setattr(cli, "_run", fake_run)
    monkeypatch.setattr(cli, "_run_collecting_output", fake_run_collecting_output)
    monkeypatch.setattr(cli, "_savegame_dir_candidates", lambda: [missing_home, save_dir])

    assert cli.main(["--repo", str(repo), "savegame-notebooks", "build"]) == 0

    assert calls[0][5:7] == ["--save-dir", str(save_dir)]


def test_savegame_notebooks_build_reports_checked_auto_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    missing_home = tmp_path / "home" / "Documents" / "Paradox Interactive" / "Europa Universalis V" / "save games"
    missing_home.mkdir(parents=True)

    monkeypatch.setattr(cli, "_savegame_dir_candidates", lambda: [missing_home])

    with pytest.raises(SystemExit, match="Could not auto-detect"):
        cli.main(["--repo", str(repo), "savegame-notebooks", "build"])


def test_savegame_notebooks_build_reports_empty_save_dir(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    save_dir = tmp_path / "save games"
    save_dir.mkdir()

    with pytest.raises(SystemExit, match="No .eu5 saves found"):
        cli.main(["--repo", str(repo), "savegame-notebooks", "build", "--save-dir", str(save_dir)])


def test_stop_existing_dashboard_processes_uses_listening_port_pid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    terminated: list[tuple[int, object]] = []

    monkeypatch.setattr(cli, "_matching_processes", lambda markers: set())
    monkeypatch.setattr(cli, "_matching_listening_port_processes", lambda port: {4242})
    monkeypatch.setattr(cli, "_terminate_process", lambda pid, sig: terminated.append((pid, sig)))
    monkeypatch.setattr(cli, "_process_exists", lambda pid: False)

    cli._stop_existing_dashboard_processes(("eu5parse",), port=8050)

    assert terminated == [(4242, cli.signal.SIGTERM)]


def test_stop_existing_dashboard_processes_never_terminates_current_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    terminated: list[tuple[int, object]] = []
    current_pid = os.getpid()

    monkeypatch.setattr(cli, "_matching_processes", lambda markers: {current_pid, 4242})
    monkeypatch.setattr(cli, "_matching_listening_port_processes", lambda port: {current_pid})
    monkeypatch.setattr(cli, "_terminate_process", lambda pid, sig: terminated.append((pid, sig)))
    monkeypatch.setattr(cli, "_process_exists", lambda pid: False)

    cli._stop_existing_dashboard_processes(("eu5parse",), port=8050)

    assert terminated == [(4242, cli.signal.SIGTERM)]


def test_savegame_purge_deletes_generated_savegame_outputs(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    savegame_dir = repo / "artifacts" / "data" / "savegame"
    progression_dir = repo / "artifacts" / "data" / "savegame_progression"
    dataset_dir = repo / "graphs" / "dataset"
    notebook_data_dir = repo / "graphs" / "savegame_notebooks" / "data"
    dataset_v2_dir = repo / "graphs" / "dataset_v2"
    progression_dataset_dir = repo / "graphs" / "savegame_progression_dataset"
    notebook_exports_dir = repo / "graphs" / "savegame_notebooks" / "exports"
    explorer = repo / "graphs" / "savegame_explorer.html"
    progression_explorer = repo / "graphs" / "savegame_progression.html"
    published_explorer = repo / "docs" / "examples" / "savegame_explorer.html"
    benchmark = repo / "graphs" / "dashboard_benchmark_report.json"

    savegame_dir.mkdir(parents=True)
    (savegame_dir / "facts.parquet").write_text("generated\n")
    progression_dir.mkdir(parents=True)
    (progression_dir / "dataset" / "manifest.json").parent.mkdir()
    (progression_dir / "dataset" / "manifest.json").write_text("{}\n")
    dataset_dir.mkdir(parents=True)
    (dataset_dir / "manifest.json").write_text("{}\n")
    notebook_data_dir.mkdir(parents=True)
    (notebook_data_dir / "metadata.json").write_text("{}\n")
    notebook_exports_dir.mkdir(parents=True)
    (notebook_exports_dir / "absolute" / "population_current.webp").parent.mkdir()
    (notebook_exports_dir / "absolute" / "population_current.webp").write_text("webp\n")
    dataset_v2_dir.mkdir(parents=True)
    (dataset_v2_dir / "manifest.json").write_text("{}\n")
    progression_dataset_dir.mkdir(parents=True)
    (progression_dataset_dir / "manifest.json").write_text("{}\n")
    explorer.write_text("<!doctype html>\n")
    progression_explorer.write_text("<!doctype html>\n")
    published_explorer.parent.mkdir(parents=True)
    published_explorer.write_text("<!doctype html>\n")
    benchmark.write_text("{}\n")

    assert cli.main(["--repo", str(repo), "savegame-purge"]) == 0

    assert not savegame_dir.exists()
    assert not progression_dir.exists()
    assert not dataset_dir.exists()
    assert not notebook_data_dir.exists()
    assert not notebook_exports_dir.exists()
    assert not dataset_v2_dir.exists()
    assert not progression_dataset_dir.exists()
    assert not explorer.exists()
    assert not progression_explorer.exists()
    assert not published_explorer.exists()
    assert not benchmark.exists()


def test_savegame_purge_dry_run_keeps_generated_outputs(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    savegame_dir = repo / "artifacts" / "data" / "savegame"
    savegame_dir.mkdir(parents=True)
    (savegame_dir / "facts.parquet").write_text("generated\n")

    assert cli.main(["--repo", str(repo), "savegame-purge", "--dry-run"]) == 0

    assert savegame_dir.exists()


def test_location_changes_detect_writes_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _repo(tmp_path)
    calls: list[tuple[str, object]] = []
    report = object()

    import prosper_or_perish_constructor.location_changes as location_changes

    def fake_build(*, repo: Path, project: Path, config_path: Path | None):
        calls.append(("build", (repo, project, config_path)))
        return report

    def fake_write(report_arg, output):
        calls.append(("write", (report_arg, output)))
        return output

    def fake_print(report_arg, *, output=None):
        calls.append(("print", (report_arg, output)))

    monkeypatch.setattr(location_changes, "build_location_change_report", fake_build)
    monkeypatch.setattr(location_changes, "write_location_change_report", fake_write)
    monkeypatch.setattr(location_changes, "print_location_change_report", fake_print)

    assert (
        cli.main(
            [
                "--repo",
                str(repo),
                "location-changes",
                "detect",
                "--config",
                "labeling.yaml",
                "--output",
                "artifacts/data/labeling/location_template_changes.csv",
            ]
        )
        == 0
    )

    assert calls == [
        ("build", (repo, repo / "constructor.toml", Path("labeling.yaml"))),
        ("write", (report, repo / "artifacts/data/labeling/location_template_changes.csv")),
        ("print", (report, repo / "artifacts/data/labeling/location_template_changes.csv")),
    ]


def test_location_changes_detect_prints_summary_stats(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from prosper_or_perish_constructor.location_changes import (
        ConstructorLocationChangeReport,
        print_location_change_report,
    )

    changes = pl.DataFrame(
        [
            {
                "location_id": 1,
                "location_tag": "loc_a",
                "changed_fields": "raw_material|topography",
                "changes_json": json.dumps(
                    {
                        "raw_material": {"old": "cotton", "new": "saffron"},
                        "topography": {"old": "hills", "new": "mountains"},
                    }
                ),
                "old_raw_material": "cotton",
                "new_raw_material": "saffron",
                "affected_goods": "cotton|saffron|wheat",
                "canonical_targets_json": json.dumps({"saffron": "loc_a"}),
                "canonical_feature_hashes_json": json.dumps({"saffron": 123}),
                "labelable": True,
                "relabel_status": "pending",
            },
            {
                "location_id": 2,
                "location_tag": "loc_b",
                "changed_fields": "topography",
                "changes_json": json.dumps(
                    {"topography": {"old": "flatland", "new": "hills"}}
                ),
                "old_raw_material": "wine",
                "new_raw_material": "wine",
                "affected_goods": "wheat",
                "canonical_targets_json": "{}",
                "canonical_feature_hashes_json": "{}",
                "labelable": False,
                "relabel_status": "not_labelable",
            },
            {
                "location_id": 3,
                "location_tag": "loc_c",
                "changed_fields": "modifier",
                "changes_json": json.dumps({"modifier": {"old": None, "new": "foo"}}),
                "old_raw_material": "fish",
                "new_raw_material": "fish",
                "affected_goods": "",
                "canonical_targets_json": "{}",
                "canonical_feature_hashes_json": "{}",
                "labelable": False,
                "relabel_status": "no_relabel_needed",
            },
        ]
    )
    report = ConstructorLocationChangeReport(
        config=object(),
        changes=changes,
        field_counts={"raw_material": 1, "topography": 2, "modifier": 1},
        unmodeled_current_fields=("movement_assistance",),
        location_template_paths=(tmp_path / "location_templates.txt",),
        overlaid_baseline=pl.DataFrame(),
    )

    print_location_change_report(report, output=tmp_path / "changes.csv")

    out = capsys.readouterr().out
    assert "changed_locations=3" in out
    assert "field_counts=modifier=1, raw_material=1, topography=2" in out
    assert "raw_material_transitions=cotton->saffron=1" in out
    assert "affected_goods_counts=cotton=1, saffron=1, wheat=2" in out
    assert "labelable_counts=false=2, true=1" in out
    assert "relabel_status_counts=no_relabel_needed=1, not_labelable=1, pending=1" in out
    assert "unmodeled_current_fields=movement_assistance" in out
    assert "location_tag\tchanged_fields\tchanges\taffected_goods" in out
    assert "loc_a\traw_material|topography" in out


def test_location_changes_run_invokes_focused_relabel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _repo(tmp_path)
    calls: list[tuple[str, object]] = []
    report = object()

    import prosper_or_perish_constructor.location_changes as location_changes

    monkeypatch.setattr(
        location_changes,
        "build_location_change_report",
        lambda *, repo, project, config_path: calls.append(
            ("build", (repo, project, config_path))
        )
        or report,
    )
    monkeypatch.setattr(
        location_changes,
        "print_location_change_report",
        lambda report_arg, **_: calls.append(("print", report_arg)),
    )

    def fake_run(report_arg, **kwargs):
        calls.append(("run", (report_arg, kwargs)))
        return 0

    monkeypatch.setattr(location_changes, "run_focused_relabel", fake_run)

    assert (
        cli.main(
            [
                "--repo",
                str(repo),
                "location-changes",
                "run",
                "--max-rounds-per-good",
                "12",
                "--min-target-appearances",
                "2",
                "--target-sigma-ratio",
                "0.9",
                "--goods",
                "saffron,cotton",
            ]
        )
        == 0
    )

    assert calls[0] == ("build", (repo, repo / "constructor.toml", None))
    assert calls[1] == ("print", report)
    assert calls[2][0] == "run"
    assert calls[2][1][0] is report
    assert calls[2][1][1] == {
        "max_rounds_per_good": 12,
        "min_target_appearances": 2,
        "target_sigma_ratio": 0.9,
        "goods_filter": {"saffron", "cotton"},
    }
