import os
from pathlib import Path

import pytest

from prosper_or_perish_constructor import cli


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "constructor.toml").write_text('name = "test"\n')
    return tmp_path


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


def test_sync_requires_explicit_confirmation(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    with pytest.raises(SystemExit, match="without explicit confirmation"):
        cli.main(["--repo", str(repo), "sync"])


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
    static_modifiers.mkdir(parents=True)
    localization.mkdir(parents=True)
    (static_modifiers / "pp_location_modifiers.txt").write_text(
        "pp_loc_slagelse = {\n"
        "\tgame_data = { category = location }\n"
        "\tlocal_fish_output_modifier = 0.1\n"
        "}\n"
        "pp_loc_sant_feliu = {\n"
        "\tlocal_medicaments_output_modifier = 0.2\n"
        "}\n",
        encoding="utf-8",
    )
    (localization / "pp_location_modifiers_l_english.yml").write_text(
        '\ufeffl_english:\n'
        ' pp_location_modifiers_title: "Prosper or Perish per-location suitability"\n'
        ' pp_location_modifiers_title_desc: "stale"\n',
        encoding="utf-8",
    )
    (localization / "pp_europedia_l_english.yml").write_text("l_english:\n", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(command, cwd):
        calls.append([str(part) for part in command])
        assert cwd == repo
        return 0

    monkeypatch.setattr(cli, "_run", fake_run)

    assert cli.main(["--repo", str(repo), "build"]) == 0

    modifier_text = (localization / "pp_location_modifiers_l_english.yml").read_text(
        encoding="utf-8-sig"
    )
    europedia_text = (localization / "pp_europedia_l_english.yml").read_text(encoding="utf-8-sig")
    assert calls == [
        ["eu5-orchestrator", "build", "--project", str(repo / "constructor.toml"), "--overwrite"]
    ]
    assert 'pp_location_potential_modifier_name: "[pp_location_potential|e]"' in modifier_text
    assert 'STATIC_MODIFIER_NAME_pp_loc_slagelse: "$pp_location_potential_modifier_name$"' in modifier_text
    assert 'STATIC_MODIFIER_DESC_pp_loc_slagelse: "$pp_location_potential_modifier_desc$"' in modifier_text
    assert "pp_location_modifiers_title:" not in modifier_text
    assert 'game_concept_pp_location_potential: "Location Potential"' in europedia_text
    assert "\\n\\nThe values combine" in europedia_text


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
    (graphs / "goods_flow_explorer.html").write_text("goods\n")
    (graphs / "savegame_explorer.html").write_text("savegame\n")
    (graphs / "assets").mkdir()
    (graphs / "assets" / "icon.svg").write_text("<svg />\n")

    assert cli.main(["--repo", str(repo), "publish-docs"]) == 0

    assert (repo / "docs" / "examples" / "goods_flow_explorer.html").read_text() == "goods\n"
    assert (repo / "docs" / "examples" / "savegame_explorer.html").read_text() == "savegame\n"
    assert (repo / "docs" / "examples" / "assets" / "icon.svg").read_text() == "<svg />\n"


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


def test_savegame_dashboard_ingest_uses_constructor_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    save_dir = tmp_path / "save games"
    save_dir.mkdir()
    (save_dir / "autosave.eu5").write_text("save\n")
    calls: list[list[str]] = []

    def fake_run(command, cwd):
        calls.append([str(part) for part in command])
        assert cwd == repo
        return 0

    monkeypatch.setattr(cli, "_run", fake_run)

    assert (
        cli.main(
            ["--repo", str(repo), "savegame-dashboard", "ingest", "--save-dir", str(save_dir)]
        )
        == 0
    )

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
            "8",
        ]
    ]


def test_savegame_dashboard_ingest_auto_detects_save_dir(
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

    monkeypatch.setattr(cli, "_run", fake_run)
    monkeypatch.setattr(cli, "_savegame_dir_candidates", lambda: [missing_home, save_dir])

    assert cli.main(["--repo", str(repo), "savegame-dashboard", "ingest"]) == 0

    assert calls[0][5:7] == ["--save-dir", str(save_dir)]


def test_savegame_dashboard_ingest_reports_checked_auto_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    missing_home = tmp_path / "home" / "Documents" / "Paradox Interactive" / "Europa Universalis V" / "save games"
    missing_home.mkdir(parents=True)

    monkeypatch.setattr(cli, "_savegame_dir_candidates", lambda: [missing_home])

    with pytest.raises(SystemExit, match="Could not auto-detect"):
        cli.main(["--repo", str(repo), "savegame-dashboard", "ingest"])


def test_savegame_dashboard_ingest_reports_empty_save_dir(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    save_dir = tmp_path / "save games"
    save_dir.mkdir()

    with pytest.raises(SystemExit, match="No .eu5 saves found"):
        cli.main(["--repo", str(repo), "savegame-dashboard", "ingest", "--save-dir", str(save_dir)])


def test_savegame_dashboard_serve_uses_constructor_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    calls: list[list[str]] = []
    stopped: list[tuple[str, ...]] = []

    def fake_run(command, cwd):
        calls.append([str(part) for part in command])
        assert cwd == repo
        return 0

    monkeypatch.setattr(cli, "_run", fake_run)
    monkeypatch.setattr(
        cli,
        "_stop_existing_dashboard_processes",
        lambda markers, port=None: stopped.append((tuple(markers), port)),
    )

    assert cli.main(["--repo", str(repo), "savegame-dashboard", "serve", "--port", "8765"]) == 0

    assert stopped == [(("eu5parse", "dashboard", "serve", "--port", "8765"), 8765)]
    assert calls == [
        [
            "uv",
            "run",
            "eu5parse",
            "dashboard",
            "serve",
            "--dataset",
            str(repo / "graphs" / "dataset"),
            "--profile",
            "constructor",
            "--load-order",
            str(repo / "constructor.load_order.toml"),
            "--host",
            "127.0.0.1",
            "--port",
            "8765",
        ]
    ]


def test_savegame_dashboard_process_matching_includes_cli_and_python_launches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []
    responses = {
        ("eu5parse", "dashboard", "serve", "--port", "8050"): {101},
        ("eu5gameparser.savegame.dashboard", "run_dashboard", "port=8050"): {202},
        ("run_dashboard", "port=8050"): {303},
    }

    def fake_matching_processes(markers):
        marker_tuple = tuple(markers)
        calls.append(marker_tuple)
        return responses.get(marker_tuple, set())

    monkeypatch.setattr(cli, "_matching_processes", fake_matching_processes)

    assert cli._matching_savegame_dashboard_processes(8050) == {101, 202, 303}
    assert calls == list(responses)


def test_stop_existing_dashboard_processes_uses_listening_port_pid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    terminated: list[tuple[int, object]] = []

    monkeypatch.setattr(cli, "_matching_processes", lambda markers: set())
    monkeypatch.setattr(cli, "_matching_savegame_dashboard_processes", lambda port: set())
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
    monkeypatch.setattr(cli, "_matching_savegame_dashboard_processes", lambda port: {current_pid})
    monkeypatch.setattr(cli, "_matching_listening_port_processes", lambda port: {current_pid})
    monkeypatch.setattr(cli, "_terminate_process", lambda pid, sig: terminated.append((pid, sig)))
    monkeypatch.setattr(cli, "_process_exists", lambda pid: False)

    cli._stop_existing_dashboard_processes(("eu5parse",), port=8050)

    assert terminated == [(4242, cli.signal.SIGTERM)]


def test_savegame_dashboard_start_uses_constructor_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    calls: list[list[str]] = []

    def fake_run(command, cwd):
        calls.append([str(part) for part in command])
        assert cwd == repo
        return 0

    monkeypatch.setattr(cli, "_run", fake_run)

    assert cli.main(["--repo", str(repo), "savegame-dashboard", "start", "--port", "8765"]) == 0

    assert calls == [
        [
            "uv",
            "run",
            "eu5parse",
            "dashboard",
            "start",
            "--dataset",
            str(repo / "graphs" / "dataset"),
            "--profile",
            "constructor",
            "--load-order",
            str(repo / "constructor.load_order.toml"),
            "--host",
            "127.0.0.1",
            "--port",
            "8765",
            "--timeout",
            "20.0",
        ]
    ]


def test_savegame_dashboard_stop_and_status_forward_port(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    calls: list[list[str]] = []

    def fake_run(command, cwd):
        calls.append([str(part) for part in command])
        assert cwd == repo
        return 0

    monkeypatch.setattr(cli, "_run", fake_run)

    assert cli.main(["--repo", str(repo), "savegame-dashboard", "stop", "--port", "8765"]) == 0
    assert cli.main(["--repo", str(repo), "savegame-dashboard", "status", "--port", "8765"]) == 0

    assert calls == [
        ["uv", "run", "eu5parse", "dashboard", "stop", "--port", "8765"],
        [
            "uv",
            "run",
            "eu5parse",
            "dashboard",
            "status",
            "--host",
            "127.0.0.1",
            "--port",
            "8765",
        ],
    ]


def test_savegame_dashboard_watch_uses_constructor_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    save_dir = tmp_path / "save games"
    save_dir.mkdir()
    (save_dir / "autosave.eu5").write_text("save\n")
    calls: list[list[str]] = []

    def fake_run(command, cwd):
        calls.append([str(part) for part in command])
        assert cwd == repo
        return 0

    monkeypatch.setattr(cli, "_run", fake_run)

    assert (
        cli.main(
            [
                "--repo",
                str(repo),
                "savegame-dashboard",
                "watch",
                "--save-dir",
                str(save_dir),
                "--max-cycles",
                "1",
            ]
        )
        == 0
    )

    assert calls == [
        [
            "uv",
            "run",
            "eu5parse",
            "savegame",
            "watch",
            "--save-dir",
            str(save_dir),
            "--output",
            str(repo / "graphs" / "dataset"),
            "--profile",
            "constructor",
            "--load-order",
            str(repo / "constructor.load_order.toml"),
            "--workers",
            "8",
            "--interval",
            "30.0",
            "--min-file-age",
            "0.0",
            "--max-cycles",
            "1",
        ]
    ]


def test_savegame_dashboard_run_starts_then_watches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    save_dir = tmp_path / "save games"
    save_dir.mkdir()
    (save_dir / "autosave.eu5").write_text("save\n")
    calls: list[list[str]] = []

    def fake_run(command, cwd):
        calls.append([str(part) for part in command])
        assert cwd == repo
        return 0

    monkeypatch.setattr(cli, "_run", fake_run)

    assert (
        cli.main(
            [
                "--repo",
                str(repo),
                "savegame-dashboard",
                "run",
                "--save-dir",
                str(save_dir),
                "--max-cycles",
                "1",
            ]
        )
        == 0
    )

    assert calls[0][:5] == ["uv", "run", "eu5parse", "dashboard", "start"]
    assert calls[1][:5] == ["uv", "run", "eu5parse", "savegame", "watch"]


def test_savegame_dashboard_benchmark_writes_constructor_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    calls: list[list[str]] = []

    def fake_run(command, cwd):
        calls.append([str(part) for part in command])
        assert cwd == repo
        return 0

    monkeypatch.setattr(cli, "_run", fake_run)

    assert cli.main(["--repo", str(repo), "savegame-dashboard", "benchmark"]) == 0

    assert calls == [
        [
            "uv",
            "run",
            "eu5parse",
            "dashboard",
            "benchmark",
            "--dataset",
            str(repo / "graphs" / "dataset"),
            "--profile",
            "constructor",
            "--load-order",
            str(repo / "constructor.load_order.toml"),
            "--output",
            str(repo / "graphs" / "dashboard_benchmark_report.json"),
        ]
    ]


def test_savegame_purge_deletes_generated_savegame_outputs(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    savegame_dir = repo / "artifacts" / "data" / "savegame"
    progression_dir = repo / "artifacts" / "data" / "savegame_progression"
    dataset_dir = repo / "graphs" / "dataset"
    dataset_v2_dir = repo / "graphs" / "dataset_v2"
    progression_dataset_dir = repo / "graphs" / "savegame_progression_dataset"
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
