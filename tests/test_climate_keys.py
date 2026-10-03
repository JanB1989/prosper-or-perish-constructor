"""Every climate the constructor or the mod names must be one that EU5 (vanilla) or the World Builder handover defines.

A gate on a climate the game does not define is silently false: no error, the building, crop or tooltip just switches
off. EU5 1.4 brought ``hot_semi_arid``, ``cold_semi_arid`` and ``subpolar``; the World Builder renamed its own hot/cold
steppe and subarctic to them (2026-10-01), so the ``ha1300_climate_*`` keys of those three are gone.

Known keys: the climates of vanilla ``in_game/common/climates`` and the game keys of the handover's climate rows
(``attribute_rows.csv``, plus the reference class). Checked: every ``climate = <key>`` test in the mod, the blueprints
and the config; every ``ha1300_climate_*`` name anywhere in the mod, the sources and the config (colours, icons,
localization keys derive from the key); and the climate-keyed tables of the sources and config, which use the
handover's attribute values (the key without the ``ha1300_climate_`` prefix).
"""
from __future__ import annotations

import csv
import json
import re
import tomllib
from pathlib import Path

import pytest

from prosper_or_perish_constructor.worldbuilder.contract import load_config
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

REPO = Path(__file__).resolve().parents[1]
PROJECT = REPO / "constructor.toml"
MOD = REPO / "mod/Prosper or Perish (Population Growth & Food Rework)"
TEXT_SUFFIXES = {".txt", ".gui", ".yml", ".yaml", ".toml", ".json", ".py", ".csv"}

_DEFINITION = re.compile(r"^﻿?(?:[A-Z_]+:)?([a-z_][a-z_0-9]*)\s*=\s*\{", re.M)
_TEST = re.compile(r"\bclimate\s*(?:=|!=|\?=)\s*([a-z_][a-z_0-9]*)\b")
_WB_NAME = re.compile(r"ha1300_climate_[a-z0-9_]+", re.I)


@pytest.fixture(scope="module")
def known() -> tuple[set[str], set[str]]:
    """(game keys, handover attribute values) of every climate EU5 or the World Builder defines."""
    climates = vanilla_root(REPO, PROJECT) / "game/in_game/common/climates"
    if not climates.is_dir():
        pytest.skip(f"vanilla climates not available at {climates}")
    keys = {m.group(1) for path in climates.glob("*.txt") for m in _DEFINITION.finditer(path.read_text(encoding="utf-8-sig"))}
    handover = load_config(REPO, PROJECT).handover
    if not (handover / "attribute_rows.csv").is_file():
        pytest.skip(f"World Builder handover not available at {handover}")
    with (handover / "attribute_rows.csv").open(encoding="utf-8", newline="") as handle:
        rows = [r for r in csv.DictReader(handle) if r["attribute"] == "climate"]
    reference = json.loads((handover / "contract.json").read_text(encoding="utf-8"))["attributes"]["reference_classes"]["climate"]
    keys |= {r["game_key"] or r["value"] for r in rows} | {reference}
    values = {r["value"] for r in rows} | {reference}
    return keys, values


def _files(*roots: Path, suffixes: set[str] = TEXT_SUFFIXES):
    for root in roots:
        paths = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
        for path in paths:
            if path.suffix in suffixes:
                yield path, path.read_text(encoding="utf-8-sig", errors="replace")


def _rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def test_every_climate_test_names_a_defined_climate(known) -> None:
    keys, _ = known
    unknown = sorted(
        f"{_rel(path)}: climate = {key}"
        for path, text in _files(MOD, REPO / "blueprints/accepted", REPO / "config", PROJECT, suffixes={".txt", ".gui", ".yml", ".toml"})
        for key in {m.group(1) for m in _TEST.finditer(re.sub(r"#[^\n]*", "", text))}   # comments are not tests
        if key not in keys
    )
    assert unknown == []


def test_every_world_builder_climate_name_is_defined(known) -> None:
    # colours, icons and localization keys are the climate key plus a suffix (ha1300_climate_savanna_frame, _desc)
    keys, _ = known
    wb = {k for k in keys if k.startswith("ha1300_climate_")}
    stale: set[str] = set()
    for path, text in _files(MOD, REPO / "src", REPO / "scripts", REPO / "blueprints/accepted", REPO / "config", PROJECT):
        for name in {m.group(0).lower() for m in _WB_NAME.finditer(text)}:
            if name not in wb and not any(name.startswith(k + "_") for k in wb):
                stale.add(f"{_rel(path)}: {name}")
    for path in MOD.rglob("*ha1300_climate_*"):
        name = _WB_NAME.search(path.name).group(0).lower()
        if name not in wb and not any(name.startswith(k + "_") for k in wb):
            stale.add(f"{_rel(path)}: file name")
    assert sorted(stale) == []


def test_climate_keyed_tables_use_defined_climates(known) -> None:
    keys, values = known
    from prosper_or_perish_constructor.worldbuilder import food_sim, start_simulation

    problems = [f"food_sim.CLIMATE_WINTER: {k}" for k in food_sim.CLIMATE_WINTER if k not in values]
    problems += [f"start_simulation.VANILLA_CLIMATES: {k}" for k in start_simulation.VANILLA_CLIMATES if k not in keys]

    def walk(node, where: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "yield_climate" and isinstance(value, dict):
                    problems.extend(f"{where} yield_climate: {k}" for k in value if k not in values)
                elif key == "climate" and isinstance(value, list):
                    problems.extend(f"{where} climate: {k}" for k in value if k not in values)
                elif "climates" in key and isinstance(value, list):
                    problems.extend(f"{where} {key}: {k}" for k in value if isinstance(k, str) and k not in keys)
                else:
                    walk(value, where)
        elif isinstance(node, list):
            for item in node:
                walk(item, where)

    for path in [PROJECT, *sorted((REPO / "config").glob("*.toml"))]:
        walk(tomllib.loads(path.read_text(encoding="utf-8")), _rel(path))
    for path in sorted((REPO / "config").glob("*.json")):
        walk(json.loads(path.read_text(encoding="utf-8-sig")), _rel(path))
    assert problems == []
