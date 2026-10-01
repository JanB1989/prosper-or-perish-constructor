"""The mod's game-start setup sits in the folder the active bookmark reads (EU5 1.4+: ``setup_folder``)."""

from pathlib import Path

from eu5gameparser.load_order import LoadOrderConfig

from prosper_or_perish_constructor import setup_layout as sl

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"


def test_the_mod_ships_nothing_in_the_pre_1_4_setup_folder() -> None:
    legacy = MOD_ROOT / sl.LEGACY_SETUP_DIR
    assert not legacy.exists() or not any(legacy.rglob("*")), f"{legacy} is not read since EU5 1.4"


def test_the_mod_setup_folder_is_the_active_bookmarks_setup_folder() -> None:
    vanilla = LoadOrderConfig.load(ROOT / "constructor.load_order.toml").vanilla_root / "game"
    assert sl.active_setup_folder(vanilla, MOD_ROOT) == sl.SETUP_FOLDER
    assert sl.check_setup_folder(vanilla, MOD_ROOT) == sl.SETUP_FOLDER
    # every setup file the mod ships overrides or extends a file of that folder
    shipped = sorted(p.relative_to(MOD_ROOT) for p in (MOD_ROOT / "main_menu" / "setup").rglob("*.txt"))
    outside = [str(p) for p in shipped if p.parts[:3] != sl.SETUP_DIR.parts and p.parts[2] != "templates"]
    assert not outside
    assert (MOD_ROOT / sl.SETUP_DIR / "14_pp_start_buildings.txt").is_file()


def test_the_pp_setup_files_load_after_the_vanilla_files_they_extend() -> None:
    vanilla = LoadOrderConfig.load(ROOT / "constructor.load_order.toml").vanilla_root / "game" / sl.SETUP_DIR
    names = sorted({p.name for p in vanilla.glob("*.txt")} | {p.name for p in (MOD_ROOT / sl.SETUP_DIR).glob("*.txt")})
    order = {name: i for i, name in enumerate(names)}
    for ours, after in (
        ("14_pp_start_buildings.txt", "07_cities_and_buildings.txt"),
        ("14_pp_start_buildings.txt", "14_development.txt"),
        ("14_pp_worldbuilder_buildings.txt", "14_development.txt"),
        ("21_pp_wb_attribute_modifiers.txt", "21_locations.txt"),
    ):
        assert order[ours] > order[after], (ours, after)


def test_the_first_uncommented_bookmark_names_the_setup_folder(tmp_path: Path) -> None:
    bookmarks = tmp_path / "game" / sl.BOOKMARKS_DIR
    bookmarks.mkdir(parents=True)
    (bookmarks / "00_bookmarks.txt").write_text(
        '﻿bookmark_1337 = {\n\tstart_date = 1337.4.1\n\tsetup_folder = "setup/1337"\n}\n'
        '#bookmark_1658 = {\n#\tsetup_folder = "setup/1658"\n#}\n',
        encoding="utf-8",
    )
    (bookmarks / "01_more.txt").write_text('bookmark_1444 = { setup_folder = "setup/1444" }\n', encoding="utf-8")
    assert sl.bookmark_setup_folders(tmp_path / "game") == {"bookmark_1337": "setup/1337", "bookmark_1444": "setup/1444"}
    assert sl.active_setup_folder(tmp_path / "game") == "setup/1337"
    mod = tmp_path / "mod" / sl.BOOKMARKS_DIR
    mod.mkdir(parents=True)
    (mod / "00_bookmarks.txt").write_text('bookmark_x = { setup_folder = "setup/x" }\n', encoding="utf-8")
    assert sl.active_setup_folder(tmp_path / "game", tmp_path / "mod") == "setup/x"
    try:
        sl.check_setup_folder(tmp_path / "game", tmp_path / "mod")
    except ValueError as error:
        assert "setup/x" in str(error)
    else:
        raise AssertionError("a moved setup folder must fail the check")
