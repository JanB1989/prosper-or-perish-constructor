from __future__ import annotations

from functools import cache
from pathlib import Path

from prosper_or_perish_constructor import text_formats
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"


@cache
def _vanilla_game() -> Path:
    return vanilla_root(ROOT, ROOT / "constructor.toml") / "game"


def test_mod_gui_and_localization_use_only_defined_formatting_tags():
    unknown = text_formats.check(_vanilla_game(), MOD_ROOT)
    assert unknown == [], "\n".join(f"#{u.tag} in {u.path}:{u.line}" for u in unknown)


def test_alias_file_is_compiled_into_the_mod():
    path = MOD_ROOT / text_formats.ALIASES_RELATIVE_PATH
    assert path.read_text(encoding="utf-8-sig") == text_formats.aliases_text()


def test_aliases_are_still_needed_and_point_at_real_formats():
    vanilla = _vanilla_game()
    vanilla_known = text_formats.known_tags(vanilla, vanilla / "no_mod")
    for tag, (target, source) in text_formats.ALIASES.items():
        assert tag not in vanilla_known, f"vanilla now defines '{tag}': drop the alias"
        assert target in vanilla_known, f"alias '{tag}' points at unknown format '{target}'"
        used = {key for _, key in text_formats.tags_in((vanilla / source).read_text(encoding="utf-8-sig"))}
        assert tag in used, f"{source} no longer uses '#{tag}': drop the alias"


def test_check_flags_undefined_tags_only(tmp_path):
    (tmp_path / "main_menu/gui").mkdir(parents=True)
    (tmp_path / "main_menu/gui/fmt.gui").write_text(
        'textformatting = {\n\tformat = {\n\t\tname = pp_gold\n\t\tformat = "color:{1,1,0};semibold"\n\t}\n}\n'
    )
    loc = tmp_path / "main_menu/localization/english"
    loc.mkdir(parents=True)
    (loc / "x_l_english.yml").write_text(
        'l_english:\n KEY: "#pp_gold a#! #bold;color:{1,0,0} b#! #semibold c#! #l d#! [X|0]#!"  # #comment\n'
    )
    empty_vanilla = tmp_path / "vanilla"
    assert [(u.tag, u.line) for u in text_formats.check(empty_vanilla, tmp_path)] == [("l", 2)]
