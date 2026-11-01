"""The Seasonal Harvests standalone mod is the main mod's harvest system, file for file, and needs nothing else.

Loading both mods must define every file and localization key once: the standalone mod ships only paths the main mod
has, and its keys live in no other main-mod file. Loading it alone must work: every script name and localization key
it uses is its own or vanilla's.
"""

from __future__ import annotations

import re
from pathlib import Path

from prosper_or_perish_constructor import loc_languages, loc_replace, seasonal_harvests
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
STANDALONE = ROOT / "mod" / seasonal_harvests.STANDALONE_FOLDER
_TOP = re.compile(r"^(?:[A-Z_]+:)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{", re.M)
_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _vanilla_game() -> Path:
    return vanilla_root(ROOT, ROOT / "constructor.toml") / "game"


def _derived(path: Path) -> bool:
    """A copy of an English file for another game language (loc_languages.py; tests/test_loc_languages.py checks them)."""
    return any(part in loc_languages.LANGUAGES for part in path.parts)


def _standalone_files() -> list[str]:
    return sorted(
        p.relative_to(STANDALONE).as_posix()
        for p in STANDALONE.rglob("*")
        if p.is_file() and p.relative_to(STANDALONE).parts[0] in ("in_game", "main_menu") and not _derived(p)
    )


def _top_keys(root: Path) -> set[str]:
    keys: set[str] = set()
    for path in root.rglob("*.txt"):
        if "common" in path.parts or "events" in path.parts:
            text = "\n".join(line.split("#", 1)[0] for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines())
            keys.update(_TOP.findall(text))
    return keys


def test_standalone_ships_only_main_mod_paths_with_the_main_mod_content() -> None:
    files = _standalone_files()
    assert set(files) == {*seasonal_harvests.COPIED, seasonal_harvests.SHARED_LOCALIZATION}
    for rel in seasonal_harvests.COPIED:
        assert (STANDALONE / rel).read_bytes() == (MOD_ROOT / rel).read_bytes(), rel
    shared = (MOD_ROOT / seasonal_harvests.SHARED_LOCALIZATION).read_text(encoding="utf-8-sig")
    assert (STANDALONE / seasonal_harvests.SHARED_LOCALIZATION).read_text(encoding="utf-8-sig") == seasonal_harvests.brand(shared)


def test_no_key_is_defined_twice_when_both_mods_load() -> None:
    standalone_keys: dict[str, str] = {}
    for rel in _standalone_files():
        if rel.endswith(".yml"):
            for key in loc_replace.read_entries(STANDALONE / rel):
                standalone_keys[key] = rel
    clashes = []
    for path in sorted((MOD_ROOT / "main_menu" / "localization").rglob("*.yml")):
        if _derived(path):
            continue   # the language copies mirror the English files key for key
        rel = path.relative_to(MOD_ROOT).as_posix()
        for key in loc_replace.read_entries(path):
            if key in standalone_keys and standalone_keys[key] != rel:
                clashes.append(f"{key}: {rel} and the standalone {standalone_keys[key]}")
    assert not clashes, "\n".join(clashes)


def test_standalone_needs_nothing_from_the_main_mod() -> None:
    vanilla = _vanilla_game()
    vanilla_loc = loc_replace.vanilla_english(vanilla)
    # any word vanilla script uses (object names and engine fields alike) is not a main-mod dependency
    vanilla_words: set[str] = set()
    for path in vanilla.rglob("*.txt"):
        if "common" in path.parts or "events" in path.parts:
            vanilla_words.update(_WORD.findall(path.read_text(encoding="utf-8-sig", errors="replace")))
    main_only = _top_keys(MOD_ROOT) - vanilla_words - _top_keys(STANDALONE)
    own_loc: dict[str, str] = {}
    for rel in _standalone_files():
        if rel.endswith(".yml"):
            own_loc.update(loc_replace.read_entries(STANDALONE / rel))
    main_loc: set[str] = set()
    for path in (MOD_ROOT / "main_menu" / "localization").rglob("*.yml"):
        main_loc.update(loc_replace.read_entries(path))

    missing = []
    for rel in _standalone_files():
        text = (STANDALONE / rel).read_text(encoding="utf-8-sig")
        if rel.endswith(".txt"):
            body = "\n".join(line.split("#", 1)[0] for line in text.splitlines())
            for word in sorted(set(_WORD.findall(body))):
                if word in main_only:
                    missing.append(f"{rel}: script name {word} exists only in the main mod")
                if word in main_loc and word not in own_loc and word not in vanilla_loc:
                    missing.append(f"{rel}: localization key {word} exists only in the main mod")
    for key, value in own_loc.items():
        for ref in re.findall(r"\$([A-Za-z_][A-Za-z0-9_.]*)[|$]", value):
            if ref not in own_loc and ref not in vanilla_loc:
                missing.append(f"{key}: ${ref}$ is not defined in the standalone mod or vanilla")
        for concept in re.findall(r"\[([A-Za-z_][A-Za-z0-9_]*)\|[eE]\]", value):
            if f"game_concept_{concept}" not in own_loc and f"game_concept_{concept}" not in vanilla_loc:
                missing.append(f"{key}: concept [{concept}|e] is not defined in the standalone mod or vanilla")
    assert not missing, "\n".join(missing)


def test_standalone_texts_carry_no_main_mod_branding() -> None:
    for rel in _standalone_files():
        if rel.endswith(".yml"):
            text = (STANDALONE / rel).read_text(encoding="utf-8-sig")
            assert "P&P" not in text and "Prosper or Perish" not in text, rel
