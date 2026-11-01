from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from prosper_or_perish_constructor import building_footprint as fp

ROOT = Path(__file__).resolve().parents[1]

CONFIG = """
[building_footprint.classes]
farm_land = "ignore"
urban_workshop = 0.75
mining = 0.15
land_reserve = -0.25
"""


def _blueprint(repo: Path, key: str, footprint: str | None, mode: str = "INJECT") -> None:
    folder = repo / fp.BLUEPRINT_ROOT_RELATIVE
    folder.mkdir(parents=True, exist_ok=True)
    tag = f"footprint: {footprint}\n" if footprint else ""
    (folder / f"{key}.yml").write_text(
        f"version: 2\ntag: {key}\n{tag}building:\n  key: {key}\n  mode: {mode}\n  body: |-\n    # x\n", encoding="utf-8"
    )


@pytest.fixture
def world(tmp_path: Path) -> dict[str, Path]:
    repo, mod, vanilla = tmp_path / "repo", tmp_path / "mod", tmp_path / "vanilla"
    (repo).mkdir()
    project = repo / "constructor.toml"
    project.write_text(CONFIG, encoding="utf-8")
    vanilla_types = vanilla / fp.VANILLA_BUILDING_TYPES_RELATIVE
    vanilla_types.mkdir(parents=True)
    (vanilla_types / "common_buildings.txt").write_text(
        "guild = {\n\temployment_size = guild_employment\n\tmodifier = { a = 1 }\n}\n"
        "mine = {\n\temployment_size = 1\n}\n"
        "farm = {\n\temployment_size = 1\n}\n"
        "hunting = {\n\temployment_size = 0.05\n\traw_modifier = { other = 1 }\n}\n",
        encoding="utf-8",
    )
    values = vanilla / "game/main_menu/common/script_values"
    values.mkdir(parents=True)
    (values / "default_values.txt").write_text("guild_employment = 0.1 # comment\n", encoding="utf-8")
    types = mod / fp.BUILDING_TYPES_RELATIVE
    types.mkdir(parents=True)
    # a compat copy of the vanilla file is never the owner
    (types / "common_buildings.txt").write_text("mine = {\n\temployment_size = 1\n}\n", encoding="utf-8")
    (types / "zz_pp_guild.txt").write_text("INJECT:guild = {\n# x\n}\n", encoding="utf-8")
    (types / "zz_pp_mine.txt").write_text(
        "REPLACE:mine = {\n\temployment_size = 2\n\tunique_production_methods = {\n\t\tpm = { employment_size = 9 }\n\t}\n"
        "\traw_modifier = {\n\t\tpp_x = 1 # {\n\t\tlocal_population_capacity = 5\n\t}\n}\n",
        encoding="utf-8",
    )
    (types / "zz_pp_farm.txt").write_text("REPLACE:farm = {\n\traw_modifier = { local_population_capacity = -5 }\n}\n", encoding="utf-8")
    # replaced by hand; its (disabled) blueprint only carries the tag, a hand TRY_INJECT elsewhere is not the owner
    (types / "pp_hand.txt").write_text("REPLACE:hunting = {\n\temployment_size = 0.05\n}\n", encoding="utf-8")
    (types / "pp_later_hand.txt").write_text("TRY_INJECT:hunting = {\n\tx = 1\n}\n", encoding="utf-8")
    _blueprint(repo, "guild", "urban_workshop")
    _blueprint(repo, "mine", "mining", "REPLACE")
    _blueprint(repo, "farm", "farm_land", "REPLACE")
    _blueprint(repo, "hunting", "land_reserve")
    return {"repo": repo, "mod": mod, "vanilla": vanilla, "project": project, "types": types}


def test_capacity_is_share_of_employment_rounded_to_people() -> None:
    assert fp.capacity_per_level(Decimal("0.75"), Decimal("0.3")) == Decimal("0.225")
    assert fp.capacity_per_level(Decimal("0.6"), Decimal("0.001")) == Decimal("0.001")
    assert fp.format_units(Decimal("0.500")) == "0.5"
    assert fp.format_units(Decimal("-0.250")) == "-0.25"
    assert fp.format_units(Decimal("0.000")) == "0"


def test_set_capacity_creates_replaces_and_merges_raw_modifier() -> None:
    created = fp.set_capacity("\n\ttown = yes\n", "0.5")
    assert "\traw_modifier = {\n\t\tlocal_population_capacity = 0.5\n\t}\n" in created
    replaced = fp.set_capacity("\n\traw_modifier = {\n\t\tlocal_population_capacity = 3\n\t\tx = 1\n\t}\n", "0.5")
    assert replaced.count("local_population_capacity") == 1 and "= 0.5" in replaced and "x = 1" in replaced
    two = fp.set_capacity("\n\traw_modifier = { local_population_capacity = 1 }\n\traw_modifier = {\n\t\tlocal_population_capacity = 2\n\t}\n", "0.1")
    assert two.count("local_population_capacity") == 1
    nested = fp.set_capacity("\n\tpm = {\n\t\traw_modifier = { local_population_capacity = 7 }\n\t}\n", "0.2")
    assert "local_population_capacity = 7" in nested and "local_population_capacity = 0.2" in nested
    assert fp.set_capacity(replaced, "0.5") == replaced


def test_zero_share_removes_the_capacity_line() -> None:
    kept = fp.set_capacity("\n\traw_modifier = {\n\t\tlocal_population_capacity = 3\n\t\tx = 1\n\t}\n", "0")
    assert "local_population_capacity" not in kept and "\t\tx = 1\n" in kept
    assert fp.set_capacity("\n\ttown = yes\n\traw_modifier = {\n\t\tlocal_population_capacity = 3\n\t}\n", "0") == "\n\ttown = yes\n"
    assert fp.set_capacity("\n\ttown = yes\n\traw_modifier = { local_population_capacity = 1 }\n", "0") == "\n\ttown = yes\n"
    assert fp.set_capacity("\n\ttown = yes\n", "0") == "\n\ttown = yes\n"
    nested = fp.set_capacity("\n\tpm = {\n\t\traw_modifier = { local_population_capacity = 7 }\n\t}\n", "0")
    assert "local_population_capacity = 7" in nested


def test_apply_with_zero_share_strips_the_line_and_is_idempotent(world: dict[str, Path]) -> None:
    project = world["project"]
    project.write_text(project.read_text(encoding="utf-8").replace("mining = 0.15", "mining = 0"), encoding="utf-8")
    fp.apply(world["repo"], world["mod"], project, world["vanilla"])
    mine = (world["types"] / "zz_pp_mine.txt").read_text(encoding="utf-8-sig")
    assert "local_population_capacity" not in mine and "pp_x = 1" in mine
    assert fp.apply(world["repo"], world["mod"], project, world["vanilla"]).files_changed == 0


def test_apply_writes_owner_blocks_and_is_idempotent(world: dict[str, Path]) -> None:
    result = fp.apply(world["repo"], world["mod"], world["project"], world["vanilla"])
    types = world["types"]
    assert result.buildings_written == 3 and result.buildings_ignored == 1
    # INJECT owner, employment from the vanilla script value: 0.75 x 0.1
    assert "local_population_capacity = 0.075" in (types / "zz_pp_guild.txt").read_text(encoding="utf-8-sig")
    # REPLACE owner, top-level employment only (not the production method's), old value replaced: 0.15 x 2
    mine = (types / "zz_pp_mine.txt").read_text(encoding="utf-8-sig")
    assert "local_population_capacity = 0.3" in mine and "= 5" not in mine and "pp_x = 1" in mine
    # the compat copy of a vanilla file is left alone
    assert "raw_modifier" not in (types / "common_buildings.txt").read_text(encoding="utf-8-sig")
    # ignored class untouched
    assert "local_population_capacity = -5" in (types / "zz_pp_farm.txt").read_text(encoding="utf-8-sig")
    # a hand REPLACE owns the building over a later INJECT; negative share rounds to whole people
    assert "local_population_capacity = -0.013" in (types / "pp_hand.txt").read_text(encoding="utf-8-sig")
    assert "raw_modifier" not in (types / "pp_later_hand.txt").read_text(encoding="utf-8-sig")
    assert (world["repo"] / fp.REPORT_RELATIVE_PATH).is_file()
    again = fp.apply(world["repo"], world["mod"], world["project"], world["vanilla"])
    assert again.files_changed == 0


def test_rendered_inject_into_a_replaced_building_fails(world: dict[str, Path]) -> None:
    (world["types"] / "zz_pp_hunting.txt").write_text("INJECT:hunting = {\n# x\n}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="INJECT:hunting is ignored by the engine"):
        fp.apply(world["repo"], world["mod"], world["project"], world["vanilla"])


def test_validate_reports_missing_and_unknown_classes(world: dict[str, Path]) -> None:
    _blueprint(world["repo"], "mine", None, "REPLACE")
    _blueprint(world["repo"], "guild", "castle_moat")
    (world["vanilla"] / fp.VANILLA_BUILDING_TYPES_RELATIVE / "extra.txt").write_text("new_wonder = {\n}\n", encoding="utf-8")
    errors = fp.validate(world["repo"], fp.load_config(world["project"]), world["vanilla"])
    assert any("mine.yml: no footprint class" in e for e in errors)
    assert any("'castle_moat'" in e for e in errors)
    assert any("new_wonder has no blueprint" in e for e in errors)
    with pytest.raises(ValueError, match="building footprint"):
        fp.apply(world["repo"], world["mod"], world["project"], world["vanilla"])


def _dlc_building(world: dict[str, Path]) -> None:
    """A building only a DLC folder defines (UTF-8 BOM like the game's DLC files), its employment a DLC script value."""
    dlc = world["vanilla"] / "game/dlc/D999_test_pack"
    (dlc / fp.BUILDING_TYPES_RELATIVE).mkdir(parents=True)
    (dlc / fp.BUILDING_TYPES_RELATIVE / "d999_forts.txt").write_text(
        "﻿dlc_fort = {\n\temployment_size = dlc_fort_employment\n}\n", encoding="utf-8"
    )
    (dlc / "in_game/common/script_values").mkdir(parents=True)
    (dlc / "in_game/common/script_values/d999_values.txt").write_text("dlc_fort_employment = 2\n", encoding="utf-8")


def test_dlc_buildings_need_a_blueprint_in_a_skip_if_missing_mode(world: dict[str, Path]) -> None:
    _dlc_building(world)
    config = fp.load_config(world["project"])
    assert fp.dlc_only_buildings(world["vanilla"]) == {"dlc_fort"}
    assert any("dlc_fort has no blueprint" in e for e in fp.validate(world["repo"], config, world["vanilla"]))
    for mode in ("INJECT", "REPLACE", "CREATE", "INJECT_OR_CREATE"):
        _blueprint(world["repo"], "dlc_fort", "urban_workshop", mode)
        errors = fp.validate(world["repo"], config, world["vanilla"])
        assert any("dlc_fort.yml: dlc_fort is defined only in a DLC folder" in e and mode in e for e in errors), mode
    for mode in sorted(fp.DLC_SAFE_MODES):
        _blueprint(world["repo"], "dlc_fort", "urban_workshop", mode)
        assert fp.validate(world["repo"], config, world["vanilla"]) == []


def test_apply_reads_the_dlc_definition_for_a_try_inject_owner(world: dict[str, Path]) -> None:
    _dlc_building(world)
    _blueprint(world["repo"], "dlc_fort", "urban_workshop", "TRY_INJECT")
    (world["types"] / "zz_pp_dlc_fort.txt").write_text("TRY_INJECT:dlc_fort = {\n# x\n}\n", encoding="utf-8")
    fp.apply(world["repo"], world["mod"], world["project"], world["vanilla"])
    # employment from the DLC definition and the DLC script value: 0.75 x 2
    assert "local_population_capacity = 1.5" in (world["types"] / "zz_pp_dlc_fort.txt").read_text(encoding="utf-8-sig")


def test_every_accepted_blueprint_has_a_configured_footprint_class() -> None:
    config = fp.load_config(ROOT / "constructor.toml")
    assert fp.validate(ROOT, config, None) == []
    shares = [s for s in config.shares.values() if s is not None]
    assert all(Decimal("-1") <= s <= Decimal("0.75") for s in shares)
