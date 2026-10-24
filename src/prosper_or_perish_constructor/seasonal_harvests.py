"""Seasonal Harvests: the standalone mod is the main mod's harvest system, file for file.

The standalone mod (``mod/Prosper or Perish Seasonal Harvests``) ships the main mod's harvest files at the same paths, so a
player who loads both mods gets every file once (the later mod's copy replaces the other's) and no localization key twice.
``apply`` runs in ``ppc finalize``:

1. the localization keys the shared files need (situation, concept, game rule, tooltip and legend texts, followed through
   ``$key$`` and ``[concept|e]`` references) move out of the main mod's other English files into ``SHARED_LOCALIZATION``,
   a file of the same name in both mods;
2. ``COPIED`` files are copied into the standalone mod, and its ``SHARED_LOCALIZATION`` is the main mod's with the
   standalone branding (``BRANDING``); other script or localization files there are removed.

Edit harvest texts in the main mod's ``SHARED_LOCALIZATION`` once they have moved there.
``tests/test_seasonal_harvests.py`` checks that the standalone mod needs nothing from the main mod.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from prosper_or_perish_constructor import loc_replace

STANDALONE_FOLDER = "Prosper or Perish Seasonal Harvests"
COPIED = (
    "in_game/common/situations/pp_variable_harvest_situation.txt",
    "in_game/common/scripted_effects/pp_variable_harvest_effects.txt",
    "in_game/common/static_modifiers/pp_variable_harvest_modifiers.txt",
    "in_game/common/customizable_localization/pp_location_status.txt",
    "main_menu/common/game_rules/pp_variable_harvest_rules.txt",
    "main_menu/common/game_concepts/pp_variable_harvests.txt",
    "main_menu/localization/english/pp_variable_harvest_modifiers_l_english.yml",
    "main_menu/localization/english/pp_location_status_harvest_l_english.yml",
)
SHARED_LOCALIZATION = "main_menu/localization/english/pp_seasonal_harvests_l_english.yml"
BRANDING = (
    ("Prosper or Perish: Variable Harvests", "Seasonal Harvests"),
    ("P&P: Variable Harvests", "Seasonal Harvests"),
    ("P&P: ", ""),
)
HEADER = (
    "l_english:\n"
    " # Harvest texts the Seasonal Harvests standalone mod shares (seasonal_harvests.py in the constructor): the same\n"
    " # file name in both mods, so loading both defines every key once. The standalone copy is written from this file.\n"
)
_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*")
_DOLLAR = re.compile(r"\$([A-Za-z_][A-Za-z0-9_.]*)[|$]")
_CONCEPT = re.compile(r"\[([A-Za-z_][A-Za-z0-9_]*)\|[eE]\]")
# name conventions that turn a script name into the localization keys the engine looks up
_CONVENTIONS = ("{}", "{}_desc", "{}_monthly", "game_concept_{}", "game_concept_{}_desc", "rule_{}", "setting_{}",
                "setting_{}_desc")


@dataclass
class Result:
    copied: int = 0
    changed: list[str] = field(default_factory=list)
    moved: dict[str, list[str]] = field(default_factory=dict)   # main mod file -> keys moved into SHARED_LOCALIZATION
    removed: list[str] = field(default_factory=list)            # stale standalone files
    keys: int = 0


def brand(text: str) -> str:
    for old, new in BRANDING:
        text = text.replace(old, new)
    return text


def _strip_comments(text: str) -> str:
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def _entry_lines(path: Path) -> dict[str, str]:
    lines: dict[str, str] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            parsed = loc_replace.parse_line(line)
            if parsed is not None:
                lines.setdefault(parsed[0], " " + line.strip())
    return lines


def needed_keys(mod_root: Path) -> set[str]:
    """Localization keys of the main mod's English files that the shared files use, followed through references."""
    english = {}
    for path in loc_replace.english_files(mod_root):
        for key, text in loc_replace.read_entries(path).items():
            english.setdefault(key, text)
    shipped: set[str] = set()
    words: set[str] = set()
    for rel in COPIED:
        text = (mod_root / rel).read_text(encoding="utf-8-sig")
        if rel.endswith(".yml"):
            shipped.update(loc_replace.read_entries(mod_root / rel))
            words.update(_DOLLAR.findall(text))
            words.update(f"game_concept_{c}" for c in _CONCEPT.findall(text))
        else:
            words.update(_WORD.findall(_strip_comments(text)))
    candidates = {pattern.format(word) for word in words for pattern in _CONVENTIONS}
    needed = {key for key in candidates if key in english and key not in shipped}
    queue = list(needed)
    while queue:
        text = english[queue.pop()]
        refs = set(_DOLLAR.findall(text)) | {f"game_concept_{c}" for c in _CONCEPT.findall(text)}
        refs |= {f"{ref}_desc" for ref in refs if ref.startswith("game_concept_")}
        for ref in refs:
            if ref in english and ref not in shipped and ref not in needed:
                needed.add(ref)
                queue.append(ref)
    return needed


def apply(mod_root: Path) -> Result:
    result = Result()
    standalone = mod_root.parent / STANDALONE_FOLDER
    if not standalone.is_dir():
        return result
    shared = mod_root / SHARED_LOCALIZATION
    needed = needed_keys(mod_root)
    entries = _entry_lines(shared)
    skip = {shared.resolve(), *((mod_root / rel).resolve() for rel in COPIED)}
    for path in loc_replace.english_files(mod_root):
        if path.resolve() in skip:
            continue
        raw = path.read_bytes().decode("utf-8-sig")   # bytes: a CRLF file keeps its line ends
        kept: list[str] = []
        moved: list[str] = []
        for line in raw.splitlines(keepends=True):
            parsed = loc_replace.parse_line(line)
            if parsed is not None and parsed[0] in needed:
                entries[parsed[0]] = " " + line.strip()
                moved.append(parsed[0])
            else:
                kept.append(line)
        if moved:
            path.write_text("".join(kept), encoding="utf-8-sig", newline="")
            result.moved[path.name] = moved
    text = HEADER + "".join(f"{entries[key]}\n" for key in sorted(entries, key=str.lower))
    result.keys = len(entries)
    if not shared.is_file() or shared.read_text(encoding="utf-8-sig") != text:
        shared.parent.mkdir(parents=True, exist_ok=True)
        shared.write_text(text, encoding="utf-8-sig", newline="\n")
        result.changed.append(str(shared.relative_to(mod_root)))

    outputs = {rel: (mod_root / rel).read_bytes() for rel in COPIED}
    outputs[SHARED_LOCALIZATION] = ("﻿" + brand(text)).encode("utf-8")
    for rel, data in outputs.items():
        target = standalone / rel
        result.copied += 1
        if not target.is_file() or target.read_bytes() != data:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            result.changed.append(f"{STANDALONE_FOLDER}/{rel}")
    for path in sorted(standalone.rglob("*")):
        rel = path.relative_to(standalone).as_posix()
        if path.is_file() and rel.split("/", 1)[0] in ("in_game", "main_menu") and rel not in outputs:
            path.unlink()
            result.removed.append(rel)
    return result
