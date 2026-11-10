"""The sync deploys the Construction Manager patch after the mod (2026-11-10, Jan: "this has to work nicely, be
integrated"): the patch's location window, building view and shared types are merged copies of the mod's."""

from __future__ import annotations

from pathlib import Path

from prosper_or_perish_constructor import cli


def test_no_patch_named_means_nothing_runs(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "constructor.local.toml").write_text("[deploy]\ntarget = \"/x\"\n", encoding="utf-8")
    calls = []
    monkeypatch.setattr(cli, "_run", lambda command, cwd: calls.append(command) or 0)
    assert cli._cm_compat_repo(tmp_path) is None
    assert cli._deploy_cm_compat(tmp_path) == 0
    assert calls == []


def test_named_patch_is_rebuilt_and_deployed(tmp_path: Path, monkeypatch) -> None:
    patch = tmp_path / "patch"
    patch.mkdir()
    (patch / "pyproject.toml").write_text("[project]\nname = \"x\"\n", encoding="utf-8")
    (tmp_path / "constructor.local.toml").write_text(f"[cm_compat]\nrepo = \"{patch.as_posix()}\"\n", encoding="utf-8")
    calls = []
    monkeypatch.setattr(cli, "_run", lambda command, cwd: calls.append((command, cwd)) or 0)
    monkeypatch.setattr(cli, "_game_running", lambda: False)
    assert cli._deploy_cm_compat(tmp_path) == 0
    assert calls == [(["uv", "run", "ppcm", "deploy", "--yes"], patch)]
    # while EU5 runs, the patch deploys interface and text only, unless game data may be reloaded
    calls.clear()
    monkeypatch.setattr(cli, "_game_running", lambda: True)
    cli._deploy_cm_compat(tmp_path)
    assert calls[0][0][-1] == "--game-running"
    calls.clear()
    cli._deploy_cm_compat(tmp_path, reload_game_data=True)
    assert "--game-running" not in calls[0][0]


def test_sync_calls_the_patch_after_the_mod() -> None:
    source = Path(cli.__file__).read_text(encoding="utf-8")
    smart = source[source.index("def _smart_sync"):source.index("def _cm_compat_repo")]
    assert smart.index('"deploy", _deploy_built_mod') < smart.index("_deploy_cm_compat")
    full = source[source.index("def _sync("):]
    assert full.index("_deploy_built_mod(") < full.index("_deploy_cm_compat(")
