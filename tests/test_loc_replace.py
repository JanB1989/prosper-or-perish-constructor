from __future__ import annotations

from pathlib import Path

from prosper_or_perish_constructor import loc_replace
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"


def test_mod_english_localization_defines_no_vanilla_key():
    # a key in localization/english that vanilla's English loc defines too loads twice ("defined in multiple files");
    # only localization/replace overrides it (ppc finalize moves them, loc_replace.py)
    clashes = loc_replace.clashes(MOD_ROOT, vanilla_root(ROOT, ROOT / "constructor.toml") / "game")
    assert clashes == {}, "\n".join(f"{path}: {', '.join(keys)}" for path, keys in clashes.items())


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(("﻿" + text).encode("utf-8"))


def test_apply_moves_vanilla_keys_drops_equal_text_and_is_idempotent(tmp_path: Path):
    vanilla = tmp_path / "game"
    _write(vanilla / "main_menu/localization/english/a_l_english.yml",
           'l_english:\n same: "Same"\n changed: "Vanilla"\n block_key: "Vanilla block"\n')
    mod = tmp_path / "mod"
    english = mod / loc_replace.ENGLISH_RELATIVE_PATH
    _write(english / "pp_x_l_english.yml",
           'l_english:\r\n own: "Own"\r\n same: "Same"\r\n changed:0 "Mod text" # note\r\n')
    _write(english / "pp_y_l_english.yml",
           'l_english:\n# >>> eu5-building-pipeline:y:localization\n block_key: "Mod block"\n'
           '# <<< eu5-building-pipeline:y:localization\n')

    result = loc_replace.apply(mod, vanilla)
    assert result.moved_count == 3 and result.dropped_equal == ["same"] and result.kept == 2
    assert (english / "pp_x_l_english.yml").read_bytes().decode("utf-8-sig") == 'l_english:\r\n own: "Own"\r\n'
    generated = (mod / loc_replace.GENERATED_RELATIVE_PATH).read_text(encoding="utf-8-sig")
    assert ' block_key: "Mod block"\n' in generated and ' changed:0 "Mod text" # note\n' in generated
    assert loc_replace.clashes(mod, vanilla) == {}

    again = loc_replace.apply(mod, vanilla)
    assert again.moved_count == 0 and again.files_changed == 0 and again.kept == 2

    # the next render writes the blueprint block again, with new text: it moves again and replaces the old line
    _write(english / "pp_y_l_english.yml",
           'l_english:\n# >>> eu5-building-pipeline:y:localization\n block_key: "New block"\n'
           '# <<< eu5-building-pipeline:y:localization\n')
    loc_replace.apply(mod, vanilla)
    generated = (mod / loc_replace.GENERATED_RELATIVE_PATH).read_text(encoding="utf-8-sig")
    assert ' block_key: "New block"\n' in generated and "Mod block" not in generated
