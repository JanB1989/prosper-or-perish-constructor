"""Players of every game language see the mod's English text instead of raw keys (Steam request, 2026-10-24)."""

from __future__ import annotations

from pathlib import Path

import pytest

from prosper_or_perish_constructor import loc_languages, loc_replace, seasonal_harvests

ROOT = Path(__file__).resolve().parents[1]
MODS = (ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)", ROOT / "mod" / "Prosper or Perish Seasonal Harvests")
SHIPPED = [p for p in (*seasonal_harvests.COPIED, seasonal_harvests.SHARED_LOCALIZATION) if p.endswith("_l_english.yml")]


def test_copies_merge_per_folder_keep_separate_files_and_drop_stale_ones(tmp_path: Path) -> None:
    english = tmp_path / "main_menu/localization/english"
    (english / "sub").mkdir(parents=True)
    (english / "sub/pp_x_l_english.yml").write_text('﻿l_english:\n  pp_x: "[ShowBuildingTypeName(\'tavern\')|e] Price"\n', encoding="utf-8")
    (english / "pp_y_l_english.yml").write_text('﻿# note\nl_english:\n pp_y: "Y"', encoding="utf-8")
    (english / "pp_shared_l_english.yml").write_text('﻿l_english:\n pp_s: "S"\n', encoding="utf-8")
    (tmp_path / "main_menu/localization/replace/english").mkdir(parents=True)
    (tmp_path / "main_menu/localization/replace/english/pp_o_l_english.yml").write_text('﻿l_english:\n  tavern_desc: "x"\n', encoding="utf-8")
    stale = tmp_path / "main_menu/localization/french/pp_old_l_french.yml"
    stale.parent.mkdir(parents=True)
    stale.write_text("﻿l_french:\n", encoding="utf-8")
    result = loc_languages.apply(tmp_path, ("french", "german"), separate=["main_menu/localization/english/pp_shared_l_english.yml"])
    merged = (tmp_path / "main_menu/localization/french/pp_mod_text_l_french.yml").read_text(encoding="utf-8")
    assert merged.startswith("﻿l_french:\n") and merged.count("l_french:") == 1 and "l_english:" not in merged
    assert ' # note\n pp_y: "Y"\n' not in merged and ' pp_y: "Y"\n' in merged
    assert '  pp_x: "[ShowBuildingTypeName(\'tavern\')|e] Price"\n' in merged and "pp_s" not in merged
    assert (tmp_path / "main_menu/localization/french/pp_shared_l_french.yml").read_text(encoding="utf-8") == '﻿l_french:\n pp_s: "S"\n'
    assert "tavern_desc" in (tmp_path / "main_menu/localization/replace/german/pp_mod_text_l_german.yml").read_text(encoding="utf-8")
    assert not stale.exists() and result.removed == [stale] and len(result.written) == 6
    assert loc_languages.apply(tmp_path, ("french", "german"), separate=["main_menu/localization/english/pp_shared_l_english.yml"]).written == []


@pytest.mark.parametrize("mod", MODS, ids=lambda p: p.name)
def test_every_language_holds_every_english_key_with_the_english_text(mod: Path) -> None:
    if not mod.is_dir():
        pytest.skip("mod not built")
    problems = []
    for language in loc_languages.LANGUAGES:
        wanted = loc_languages.plan(mod, language, SHIPPED)
        on_disk = {p for f in loc_languages.FOLDERS for p in (mod / f / language).rglob("*.yml")}
        problems += [f"extra {p.relative_to(mod)}" for p in on_disk - set(wanted)]
        problems += [f"missing or stale {p.relative_to(mod)}" for p, text in wanted.items()
                     if not p.is_file() or p.read_text(encoding="utf-8") != text]
    for folder in loc_languages.FOLDERS:   # every English key, once per language
        english = mod / folder / "english"
        keys = sorted(k for p in english.rglob("*_l_english.yml") for k in loc_replace.read_entries(p)) if english.is_dir() else []
        for language in ("french",):
            copied = sorted(k for p in (mod / folder / language).rglob("*.yml") for k in loc_replace.read_entries(p))
            if copied != keys:
                problems.append(f"{folder}/{language}: {len(copied)} keys, English {len(keys)}")
    assert problems == [], f"{len(problems)} language files wrong (ppc finalize writes them):\n" + "\n".join(problems[:20])


def test_copies_stay_in_the_windows_path_budget() -> None:
    longest = max((len(p.relative_to(ROOT).as_posix()) for mod in MODS for f in loc_languages.FOLDERS
                   for lang in loc_languages.LANGUAGES for p in (mod / f / lang).rglob("*.yml")), default=0)
    assert longest <= 140


def test_the_languages_are_the_games() -> None:
    from prosper_or_perish_constructor.cap_tooltips import game_root
    from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

    folder = game_root(vanilla_root(ROOT, ROOT / "constructor.toml")) / "main_menu/localization"
    if not folder.is_dir():
        pytest.skip("no vanilla game files")
    game = {p.name for p in folder.iterdir() if p.is_dir()} - {"english", "replace"}
    assert set(loc_languages.LANGUAGES) == game
