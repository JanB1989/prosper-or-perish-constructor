"""No start exceptions (2026-10-23, Jan): buildings stand at game start only where their own rules allow them.

A vanilla setup building that fails its building's rank, location_potential or allow is removed from the setup
(start_simulation ``drop_invalid``); no building rule lets named start locations through.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from types import SimpleNamespace

from eu5gameparser.clausewitz.parser import parse_text

from prosper_or_perish_constructor.worldbuilder import start_simulation as ss
from prosper_or_perish_constructor.worldbuilder.start_rules import Rules

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
# location lists that are a building's design, not a start exception (vanilla's own, or a site classification)
DESIGN_LOCATION_LISTS = {"salt_mine", "salt_mine_improved", "inland_saltworks", "engineered_brine_saltworks", "ablaq_palace", "shoen"}


def test_keepers_are_gone() -> None:
    raw = tomllib.loads((ROOT / "constructor.toml").read_text(encoding="utf-8"))
    assert "keep_setup_buildings" not in raw["worldbuilder"]["start"]
    assert not hasattr(ss, "keep_setup_buildings")
    assert not (MOD_ROOT / "in_game/common/scripted_triggers/pp_wb_setup_buildings.txt").exists()
    for folder in ("building_types", "scripted_triggers", "script_values"):
        for path in (MOD_ROOT / "in_game/common" / folder).glob("*.txt"):
            assert not re.search(r"\bpp_wb_setup_\w+_location\b", path.read_text(encoding="utf-8-sig")), path.name
    for path in (ROOT / "blueprints/accepted/buildings").glob("*.yml"):
        assert "pp_wb_setup_" not in path.read_text(encoding="utf-8"), path.name


def test_orchard_gate_names_no_locations() -> None:
    text = (MOD_ROOT / "in_game/common/scripted_triggers/pp_startup_building_compatibility.txt").read_text(encoding="utf-8-sig")
    assert "location:" not in text


def test_building_rules_name_no_start_locations() -> None:
    """Only design lists may name locations inside a building's location_potential or allow."""
    offenders = []
    for path in (ROOT / "blueprints/accepted/buildings").glob("*.yml"):
        text = path.read_text(encoding="utf-8")
        if path.stem in DESIGN_LOCATION_LISTS:
            continue
        if re.search(r"this = location:\w+", text):
            offenders.append(path.stem)
    assert offenders == []


def _drop(body: str, rows: dict[str, dict]) -> dict[str, int]:
    rules = Rules.__new__(Rules)
    rules.triggers, rules.values = {}, {}
    rules.buildings = {"granary": parse_text(f"granary = {{ {body} }}").entries[0].value}
    counts = {tag: {"granary": row.pop("levels")} for tag, row in rows.items()}
    contexts = {tag: {"location_tag": tag, "location_rank": "town", **row} for tag, row in rows.items()}
    sim = SimpleNamespace(rules=rules, locations=list(rows), counts=counts, trimmed=[], ctx=contexts.__getitem__)
    ss.Simulation.drop_invalid(sim)
    return {tag: c["granary"] for tag, c in sim.counts.items()}


def test_drop_invalid_removes_rows_failing_potential_or_allow() -> None:
    body = "town = yes location_potential = { vegetation = forest } allow = { is_province_capital = yes }"
    assert _drop(body, {
        "capital_forest": {"vegetation": "forest", "is_province_capital": True, "levels": 2},
        "plain_capital": {"vegetation": "grasslands", "is_province_capital": True, "levels": 2},   # potential fails
        "forest_village": {"vegetation": "forest", "is_province_capital": False, "levels": 3},    # allow fails
    }) == {"capital_forest": 2, "plain_capital": 0, "forest_village": 0}


def test_setup_only_buildings_keep_their_start_rows() -> None:
    # vanilla's allow = { always = no } (kokufu, cardinal seats, monuments): nobody builds them, the setup places them
    for allow in ("always = no", "custom_tooltip = { text = x always = no }"):
        body = f"town = yes location_potential = {{ vegetation = forest }} allow = {{ {allow} }}"
        assert _drop(body, {"seat": {"vegetation": "forest", "levels": 1}}) == {"seat": 1}
