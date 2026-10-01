"""pp_navigation_preserve_rivers gives a World Builder river back only where the location has no river size at all.

The engine's own river_flowing_through_N statics are invisible to has_location_modifier, and has_river is yes on banks
that keep stray river pixels without a size (Yangtze: Hanyang, Jiangling, Jinhua), so neither can tell "no river size".
modifier:irrigant_cap_modifier can: it is N on every river_flowing_through_N (engine statics included) and on nothing
else, so < 0.5 means no size and no location ever gets a second river modifier.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MOD = REPO / "mod/Prosper or Perish (Population Growth & Food Rework)"
EFFECT = MOD / "in_game/common/scripted_effects/pp_navigation_river_bonuses.txt"
TRIGGERS = MOD / "in_game/common/scripted_triggers/pp_navigation_rivers.txt"


@pytest.fixture(scope="module")
def effect() -> str:
    if not EFFECT.is_file():
        pytest.skip("mod not built")
    return EFFECT.read_text(encoding="utf-8-sig")


def test_missing_river_reads_the_river_size_with_a_has_river_fallback():
    text = TRIGGERS.read_text(encoding="utf-8-sig")
    line = next(l for l in text.splitlines() if l.startswith("pp_navigation_river_missing = "))
    assert "has_global_variable = pp_navigation_river_sizes_live modifier:irrigant_cap_modifier < 0.5" in line
    assert "NOT = { has_global_variable = pp_navigation_river_sizes_live } NOT = { pp_navigation_has_river = yes }" in line


def test_every_restore_waits_for_a_missing_river(effect):
    restores = [l for l in effect.splitlines() if "add_location_modifier" in l]
    assert len(restores) > 1000
    for line in restores:
        assert re.match(r"^ location:[A-Za-z0-9_\-]+ = \{ if = \{ limit = \{ pp_navigation_river_missing = yes \} add_location_modifier = \{ modifier = river_flowing_through_[1-5] ", line), line
    assert "has_river" not in effect and "has_location_modifier" not in effect


def test_river_sizes_live_flag_is_probed_first_and_removed_last(effect):
    lines = effect.splitlines()
    assert lines[0] == "pp_navigation_preserve_rivers = {"
    probes = re.findall(r"location:([A-Za-z0-9_\-]+) = \{ modifier:irrigant_cap_modifier > 0.5 \}", lines[1])
    assert len(probes) >= 3
    assert lines[2].strip() == "set_global_variable = { name = pp_navigation_river_sizes_live value = yes }"
    assert lines[-2:] == [" remove_global_variable = pp_navigation_river_sizes_live", "}"]
    on_action = (MOD / "in_game/common/on_action/pp_navigation.txt").read_text(encoding="utf-8-sig")
    assert on_action.index("pp_navigation_preserve_rivers = yes") < on_action.index("pp_start_river_topup = yes")


def test_irrigant_cap_modifier_is_exactly_the_river_size():
    """Only river_flowing_through_N carries irrigant_cap_modifier, with value N, in every block the mod writes."""
    found = {}
    for path in (MOD / "main_menu/common/static_modifiers").glob("*.txt"):
        text = re.sub(r"#[^\n]*", "", path.read_text(encoding="utf-8-sig"))
        for block in re.finditer(r"(?ms)^(?:[A-Z_]+:)?([A-Za-z0-9_]+)\s*=\s*\{(.*?)^\}", text):
            for value in re.findall(r"(?<!:)\birrigant_cap_modifier\s*=\s*([-\d.]+)", block.group(2)):
                found.setdefault(block.group(1), set()).add(float(value))
    assert found == {f"river_flowing_through_{n}": {float(n)} for n in range(1, 6)}
    elsewhere = []
    for path in MOD.rglob("*.txt"):
        if "static_modifiers" in path.parts:
            continue
        text = re.sub(r"#[^\n]*", "", path.read_text(encoding="utf-8-sig", errors="replace"))
        if re.search(r"(?<![:\w])irrigant_cap_modifier\s*=\s*[-\d.]", text):
            elsewhere.append(str(path.relative_to(MOD)))
    assert elsewhere == []
