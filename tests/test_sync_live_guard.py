"""`ppc sync --while-running` deploys only interface, text and graphics into a running game (2026-10-18: a hot reload
of building_types corrupted Jan's running game and its next autosave, which then crashed in
CCancelSpecificConstructionCommand)."""

from __future__ import annotations

from pathlib import Path

from prosper_or_perish_constructor import cli


def test_live_safe_folders():
    assert cli.live_safe(Path("in_game/gui/build_location_lateralview.gui"))
    assert cli.live_safe(Path("main_menu/localization/english/pp_build_panel_l_english.yml"))
    assert cli.live_safe(Path("main_menu/gfx/interface/icons/x.dds"))
    assert not cli.live_safe(Path("in_game/common/building_types/zz_pp_entrepot.txt"))
    assert not cli.live_safe(Path("in_game/events/pp_events.txt"))
    assert not cli.live_safe(Path("main_menu/common/static_modifiers/pp.txt"))
    assert not cli.live_safe(Path("descriptor.mod"))


def test_only_game_data_of_the_deploy_plan_is_reported(monkeypatch, tmp_path):
    """The guard filters the orchestrator's own deploy plan (copies and --clean deletes)."""
    import importlib

    # the package exports a function named deploy, so take the modules themselves
    config = importlib.import_module("eu5_mod_orchestrator.config")
    deploy = importlib.import_module("eu5_mod_orchestrator.deploy")

    target = tmp_path / "live"

    class Plan:
        planned_copies = [target / "in_game/gui/panel.gui", target / "in_game/common/building_types/new.txt"]
        planned_deletes = [target / "in_game/common/building_types/old.txt", target / "main_menu/gfx/old.dds"]

    Plan.target = target
    seen = {}

    def fake_deploy(cfg, *, dry_run, clean, force=False):
        seen.update(dry_run=dry_run, clean=clean)
        return Plan

    monkeypatch.setattr(config, "load_project_config", lambda project: None)
    monkeypatch.setattr(deploy, "deploy", fake_deploy)
    assert cli._unsafe_live_changes(Path("constructor.toml")) == [
        str(Path("in_game/common/building_types/new.txt")),
        str(Path("in_game/common/building_types/old.txt")) + " (removed)",
    ]
    assert seen == {"dry_run": True, "clean": True}
