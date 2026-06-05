import csv
import json
import re
import subprocess
from pathlib import Path

from prosper_or_perish_constructor import cli
from prosper_or_perish_constructor.update_audit import run_update_audit


def test_update_audit_reports_referenced_and_patched_vanilla_changes(tmp_path: Path) -> None:
    repo, vanilla = _write_update_audit_fixture(tmp_path)

    summary = run_update_audit(
        repo=repo,
        project=repo / "constructor.toml",
        load_order_path=repo / "constructor.load_order.toml",
        old_ref="eu5-old",
        new_ref="eu5-new",
        output_dir=repo / "reports" / "audit",
    )

    assert summary.changed_count >= 4
    assert summary.added_count == 2
    assert summary.removed_count == 2
    assert summary.missing_both_count == 1
    assert summary.index_html.is_file()
    assert summary.changed_csv.is_file()
    assert summary.all_csv.is_file()
    assert summary.changed_json.is_file()

    all_rows = _csv_rows(summary.all_csv)
    rows_by_key = {row["qualified"]: row for row in all_rows}

    assert rows_by_key["in_game/goods/wheat"]["status"] == "changed"
    assert "patch_target" in rows_by_key["in_game/goods/wheat"]["reference_kinds"]
    assert rows_by_key["in_game/goods/added_good"]["status"] == "added"
    assert rows_by_key["in_game/goods/unreferenced_added_good"]["status"] == "added"
    assert rows_by_key["in_game/goods/unreferenced_added_good"]["reference_kinds"] == ""
    assert rows_by_key["in_game/goods/unreferenced_added_good"]["mod_sources"] == ""
    assert rows_by_key["in_game/goods/removed_good"]["status"] == "removed"
    assert rows_by_key["in_game/goods/unreferenced_removed_good"]["status"] == "removed"
    assert rows_by_key["in_game/goods/unchanged_good"]["status"] == "unchanged"
    assert rows_by_key["in_game/goods/plain_override"]["status"] == "changed"
    assert rows_by_key["in_game/goods/missing_target"]["status"] == "missing_both"
    assert rows_by_key["main_menu/modifier_type_definitions/global_wheat_output_modifier"][
        "status"
    ] == "changed"
    assert rows_by_key["main_menu/static_modifiers/cross_scope_static"]["status"] == "changed"
    assert (
        rows_by_key["main_menu/static_modifiers/cross_scope_static"]["mod_sources"]
        == "mod/test-mod/in_game/common/static_modifiers/pp_static.txt:1 [patch_target; TRY_INJECT]"
    )
    assert "in_game/static_modifiers/cross_scope_static" not in rows_by_key

    assert "in_game/goods/localization_only_good" not in rows_by_key
    assert rows_by_key["in_game/goods/dupe_key"]["status"] == "changed"
    assert rows_by_key["main_menu/static_modifiers/dupe_key"]["status"] == "unchanged"

    changed_rows = _csv_rows(summary.changed_csv)
    changed_keys = {row["qualified"] for row in changed_rows}
    assert "in_game/goods/unchanged_good" not in changed_keys
    assert "in_game/goods/missing_target" not in changed_keys
    assert "in_game/goods/added_good" in changed_keys
    assert "in_game/goods/unreferenced_added_good" in changed_keys
    assert "in_game/goods/removed_good" in changed_keys
    assert "in_game/goods/unreferenced_removed_good" in changed_keys

    payload = json.loads(summary.changed_json.read_text(encoding="utf-8"))
    assert payload["old_ref"] == "eu5-old"
    assert payload["new_ref"] == "eu5-new"
    assert {row["qualified"] for row in payload["dependencies"]} == changed_keys

    html_text = summary.index_html.read_text(encoding="utf-8")
    assert '<option value="__impacted" selected>Impacted only</option>' in html_text
    assert '<tbody class="record"' in html_text
    assert "Diff & sources" in html_text
    assert "wheat = {" in html_text
    assert "diff-row replace" in html_text
    assert "top: 61px" not in html_text
    assert 'class="detail-row" hidden' in html_text
    assert "data-sort-reference-kinds" in html_text
    assert "data-reference_kinds" not in html_text
    assert "data-mod_sources" not in html_text
    assert all("\n" not in value for value in re.findall(r'data-search="([^"]*)"', html_text))

    assert vanilla.is_dir()


def test_update_audit_cli_writes_report(tmp_path: Path, capsys) -> None:
    repo, _vanilla = _write_update_audit_fixture(tmp_path)

    result = cli.main(
        [
            "--repo",
            str(repo),
            "update-audit",
            "--old-ref",
            "eu5-old",
            "--new-ref",
            "eu5-new",
            "--output-dir",
            "reports/cli-audit",
        ]
    )

    assert result == 0
    output = capsys.readouterr().out
    assert "dependencies=" in output
    assert "changed_csv=" in output
    assert (repo / "reports" / "cli-audit" / "index.html").is_file()
    assert (repo / "reports" / "cli-audit" / "changed_dependencies.csv").is_file()


def _write_update_audit_fixture(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "constructor"
    vanilla = tmp_path / "vanilla"
    repo.mkdir()
    vanilla.mkdir()

    (repo / "constructor.toml").write_text(
        '[project]\nmod_root = "mod/test-mod"\n',
        encoding="utf-8",
    )
    (repo / "constructor.load_order.toml").write_text(
        f'[paths]\nvanilla_root = "{vanilla.as_posix()}"\n\n[profiles]\nvanilla = ["vanilla"]\n',
        encoding="utf-8",
    )

    _git(vanilla, "init")
    _git(vanilla, "config", "user.email", "test@example.com")
    _git(vanilla, "config", "user.name", "Test User")

    _write(
        vanilla / "game" / "in_game" / "common" / "goods" / "00_goods.txt",
        """wheat = {
	value = 1
}
removed_good = {
	value = 1
}
unchanged_good = {
	value = 1
}
unreferenced_removed_good = {
	value = 1
}
plain_override = {
	value = 1
}
dupe_key = {
	value = 1
}
localization_only_good = {
	value = 1
}
""",
        encoding="utf-8-sig",
    )
    _write(
        vanilla
        / "game"
        / "main_menu"
        / "common"
        / "modifier_type_definitions"
        / "00_modifier_types.txt",
        """global_wheat_output_modifier = {
	value = 1
}
""",
    )
    _write(
        vanilla / "game" / "main_menu" / "common" / "static_modifiers" / "00_static.txt",
        """dupe_key = {
	value = 1
}
cross_scope_static = {
	value = 1
}
""",
    )
    _git(vanilla, "add", "-A")
    _git(vanilla, "commit", "-m", "old")
    _git(vanilla, "tag", "eu5-old")

    _write(
        vanilla / "game" / "in_game" / "common" / "goods" / "00_goods.txt",
        """wheat = {
	value = 2
}
added_good = {
	value = 1
}
unreferenced_added_good = {
	value = 1
}
unchanged_good = {
	value = 1
}
plain_override = {
	value = 2
}
dupe_key = {
	value = 2
}
localization_only_good = {
	value = 2
}
""",
    )
    _write(
        vanilla
        / "game"
        / "main_menu"
        / "common"
        / "modifier_type_definitions"
        / "00_modifier_types.txt",
        """global_wheat_output_modifier = {
	value = 2
}
""",
    )
    _write(
        vanilla / "game" / "main_menu" / "common" / "static_modifiers" / "00_static.txt",
        """dupe_key = {
	value = 1
}
cross_scope_static = {
	value = 2
}
""",
    )
    _git(vanilla, "add", "-A")
    _git(vanilla, "commit", "-m", "new")
    _git(vanilla, "tag", "eu5-new")

    mod_root = repo / "mod" / "test-mod"
    _write(
        mod_root / "in_game" / "common" / "goods" / "pp_goods.txt",
        """TRY_INJECT:wheat = {
	value = added_good
}
INJECT:missing_target = {
	value = yes
}
plain_override = {
	value = yes
}
""",
    )
    _write(
        mod_root / "in_game" / "common" / "script_values" / "pp_values.txt",
        """pp_dependency_value = {
	add = wheat
	add = removed_good
	add = unchanged_good
	add = global_wheat_output_modifier
	add = dupe_key
	add = pp_mod_owned
}
""",
    )
    _write(
        mod_root / "in_game" / "common" / "static_modifiers" / "pp_static.txt",
        """TRY_INJECT:cross_scope_static = {
	value = 1
}
""",
    )
    _write(
        mod_root / "main_menu" / "localization" / "english" / "pp_test_l_english.yml",
        'l_english:\n  pp_test: "localization_only_good"\n',
    )
    return repo, vanilla


def _write(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding=encoding)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))
