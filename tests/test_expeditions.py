"""PP colonial expeditions (docs/expeditions.md): every piece the expedition types use exists.

The eight types in in_game/common/expedition_types/pp_colonial_expeditions.txt fire outcome events, call scripted
effects and triggers, read script values, raise buildings and grant modifiers defined in other files; the player sees
their names, descriptions and outcomes through localization keys.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
COMMON = MOD_ROOT / "in_game" / "common"
TYPES = COMMON / "expedition_types" / "pp_colonial_expeditions.txt"
EVENTS = MOD_ROOT / "in_game" / "events" / "pp_expedition_events.txt"
EFFECTS = COMMON / "scripted_effects" / "pp_expedition_effects.txt"
TRIGGERS = COMMON / "scripted_triggers" / "pp_expedition_triggers.txt"
VALUES = COMMON / "script_values" / "pp_expedition_values.txt"
BUILDINGS = COMMON / "building_types" / "pp_expedition_buildings.txt"
MODIFIERS = MOD_ROOT / "main_menu" / "common" / "static_modifiers" / "pp_expedition_modifiers.txt"
LOC = MOD_ROOT / "main_menu" / "localization" / "english" / "pp_expeditions_l_english.yml"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _top_keys(path: Path) -> set[str]:
    return set(re.findall(r"^([a-z_][a-z0-9_.]*) = \{", _text(path), re.M))


def _loc_keys() -> set[str]:
    return set(re.findall(r"^ ([A-Za-z_][A-Za-z0-9_.]*):", _text(LOC), re.M))


def _types() -> set[str]:
    return _top_keys(TYPES)


def test_eight_expedition_types() -> None:
    assert len(_types()) == 8


def test_every_type_has_its_text() -> None:
    loc = _loc_keys()
    for name in _types():
        for suffix in ("", "_desc", "_historical_info", "_outcome_overview"):
            assert f"{name}{suffix}" in loc, f"{name}{suffix} missing"


def test_every_event_fired_exists_and_has_text() -> None:
    fired = set(re.findall(r"pp_expedition\.\d+", _text(TYPES) + _text(EVENTS)))
    defined = {key for key in _top_keys(EVENTS) if key.startswith("pp_expedition.")}
    assert fired <= defined, fired - defined
    loc = _loc_keys()
    events = _text(EVENTS)
    for event in defined:
        assert f"{event}.title" in loc and f"{event}.desc" in loc, event
        start = events.index(f"{event} = {{")
        body = events[start: events.find("\npp_expedition.", start + 1)]
        for option in re.findall(r"name = (pp_expedition\.\d+\.[a-z])", body):
            assert option in loc, option


def test_scripted_effects_triggers_and_values_exist() -> None:
    effects, triggers, values = _top_keys(EFFECTS), _top_keys(TRIGGERS), _top_keys(VALUES)
    used = _text(TYPES) + _text(EVENTS) + _text(EFFECTS) + _text(TRIGGERS)
    for name in set(re.findall(r"\b(pp_exp_[a-z_]+_effect) = ", used)):
        assert name in effects, name
    for name in set(re.findall(r"\b(pp_exp_[a-z_]+) = yes", used)) - effects:
        assert name in triggers, name
    for name in set(re.findall(r"\b(pp_exp_(?:cost|reserve|years_since|utility|ai_check)_[a-z][a-z_]*)\b", used)):
        assert name in values, name


def test_buildings_and_modifiers_exist_with_text() -> None:
    loc = _loc_keys()
    used = _text(EFFECTS) + _text(EVENTS)
    buildings = _top_keys(BUILDINGS)
    for name in set(re.findall(r"building_type:(pp_[a-z_]+)", used)):
        assert name in buildings, name
    for name in buildings:
        assert name in loc and f"{name}_desc" in loc and f"{name}_maintenance" in loc, name
    modifiers = _top_keys(MODIFIERS)
    for name in set(re.findall(r"modifier = (pp_exp_[a-z_]+)", used)):
        assert name in modifiers, name
    for name in modifiers:
        assert f"STATIC_MODIFIER_NAME_{name}" in loc and f"STATIC_MODIFIER_DESC_{name}" in loc, name


def test_expeditions_are_never_free() -> None:
    """Every type pays its fitting-out cost at the start and demands a gold reserve."""
    text = _text(TYPES)
    for name in _types():
        start = text.index(f"\n{name} = {{")
        body = text[start: text.find("\npp_exp_", start + 1)]
        assert "pp_exp_pay_effect" in body, name
        assert re.search(r"gold >= pp_exp_reserve_", body), name


def test_localization_has_no_balance_numbers() -> None:
    """Player-facing text names no balance values (AGENTS.md Localization)."""
    for line in _text(LOC).splitlines():
        if ":" not in line or line.strip().startswith("#") or "historical_info" in line:
            continue
        value = line.split(":", 1)[1]
        assert not re.search(r"\d+ ?%|[+-]\d", value), line
