"""PP trade expeditions (docs/trade_expeditions.md): every piece the three expedition types use exists.

The types in in_game/common/expedition_types/pp_trade_expeditions.txt call scripted effects and triggers, read script
values, raise buildings, add area preferences and fire outcome events defined in other files; the player sees their
names, descriptions and outcomes through localization keys; the historical sites are vanilla location keys.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
COMMON = MOD_ROOT / "in_game" / "common"
TYPES = COMMON / "expedition_types" / "pp_trade_expeditions.txt"
EVENTS = MOD_ROOT / "in_game" / "events" / "pp_trade_expedition_events.txt"
EFFECTS = COMMON / "scripted_effects" / "pp_trade_expedition_effects.txt"
TRIGGERS = COMMON / "scripted_triggers" / "pp_trade_expedition_triggers.txt"
VALUES = COMMON / "script_values" / "pp_trade_expedition_values.txt"
BUILDINGS = COMMON / "building_types" / "pp_trade_expedition_buildings.txt"
PREFERENCES = COMMON / "area_preferences" / "pp_trade_expedition_preferences.txt"
LOC = MOD_ROOT / "main_menu" / "localization" / "english" / "pp_trade_expeditions_l_english.yml"
PREF_LOC = MOD_ROOT / "main_menu" / "localization" / "english" / "pp_area_preferences_l_english.yml"
VANILLA_DEFINITIONS = Path.home() / ".cache" / "eu5-vanilla" / "game" / "in_game" / "map_data" / "definitions.txt"
KINDS = ("africa", "india", "far_east")


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _top_keys(path: Path) -> set[str]:
    return set(re.findall(r"^([a-z_][a-z0-9_.]*) = \{", _text(path), re.M))


def _loc_keys(path: Path = LOC) -> set[str]:
    return set(re.findall(r"^ ([A-Za-z_][A-Za-z0-9_.]*):", _text(path), re.M))


def _types() -> set[str]:
    return _top_keys(TYPES)


def _sites() -> set[str]:
    text = _text(EFFECTS) + _text(TRIGGERS)
    return set(re.findall(r"location:([a-z_0-9]+)", text))


def test_three_expedition_types() -> None:
    assert _types() == {f"pp_te_{kind}" for kind in KINDS}


def test_every_type_has_its_text() -> None:
    loc = _loc_keys()
    for name in _types():
        for suffix in ("", "_desc", "_historical_info", "_outcome_overview"):
            assert f"{name}{suffix}" in loc, f"{name}{suffix} missing"


def test_every_event_fired_exists_and_has_text() -> None:
    fired = set(re.findall(r"pp_trade_expedition\.\d+", _text(TYPES) + _text(EFFECTS)))
    defined = {key for key in _top_keys(EVENTS) if key.startswith("pp_trade_expedition.")}
    assert fired <= defined, fired - defined
    loc = _loc_keys()
    for event in defined:
        assert f"{event}.title" in loc and f"{event}.desc" in loc and f"{event}.a" in loc, event


def test_scripted_effects_triggers_and_values_exist() -> None:
    effects, triggers, values = _top_keys(EFFECTS), _top_keys(TRIGGERS), _top_keys(VALUES)
    used = _text(TYPES) + _text(EVENTS) + _text(EFFECTS) + _text(TRIGGERS) + _text(VALUES)
    for kind in KINDS:
        used = used + "\n" + _text(EFFECTS).replace("$KIND$", kind)
    called = set(re.findall(r"(?<![:\w])(pp_te_[a-z_]+) = (?:yes|\{)", used))
    for name in called:
        if "$" in name:
            continue
        assert name in effects | triggers | values | _types() or name.startswith("pp_te_hold_"), name
    for name in set(re.findall(r"\b(pp_te_(?:cost|reserve|years_since|utility|ai_check|land|licence|cede|site|garrison|root)_[a-z_]*)\b", used)):
        if name.endswith(("_effect", "_")) or name in triggers:
            continue
        assert name in values, name


def test_sites_are_vanilla_locations() -> None:
    if not VANILLA_DEFINITIONS.exists():
        pytest.skip("vanilla mirror not present (uv run ppc vanilla-mirror)")
    words = set(re.findall(r"\b([a-z_0-9]+)\b", VANILLA_DEFINITIONS.read_text(encoding="utf-8-sig")))
    missing = sorted(site for site in _sites() if site not in words)
    assert not missing, missing


def test_each_site_list_matches_its_trigger() -> None:
    """The candidate list an expedition picks from (effects) and the free-site test (triggers) name the same places."""
    effects, triggers = _text(EFFECTS), _text(TRIGGERS)
    for kind in KINDS:
        start = effects.index(f"pp_te_build_list_{kind} = {{")
        body = effects[start: effects.index("\n}", start)]
        listed = set(re.findall(r"location:([a-z_0-9]+) = \{ add_to_list", body))
        start = triggers.index(f"pp_te_any_{kind}_site = {{")
        body = triggers[start: triggers.index("\n}", start)]
        tested = set(re.findall(r"location:([a-z_0-9]+) = \{ pp_te_site_free", body))
        assert listed == tested, (kind, listed ^ tested)


def test_buildings_and_preferences_exist_with_text() -> None:
    loc = _loc_keys()
    buildings = _top_keys(BUILDINGS)
    for name in set(re.findall(r"building_type:(pp_te_[a-z_]+)", _text(EFFECTS))):
        assert name in buildings, name
    for name in buildings:
        assert name in loc and f"{name}_desc" in loc and f"{name}_maintenance" in loc, name
    prefs = _top_keys(PREFERENCES)
    for name in set(re.findall(r"preference = (pp_te_hold_[a-z_]+)", _text(EFFECTS))):
        assert name in prefs, name
    pref_loc = _loc_keys(PREF_LOC)
    for name in prefs:
        assert name in pref_loc, name


def test_castle_cannot_be_demolished() -> None:
    """Forts are what the AI demolishes to save money; the expedition's Castle and Factory must stay."""
    text = _text(BUILDINGS)
    start = text.index("pp_te_factory = {")
    body = text[start: text.index("\n}", start)]
    assert "is_indestructible = yes" in body
    assert re.search(r"fort_level = \d", body)


def test_expeditions_are_never_free() -> None:
    """Every type pays its income-scaled fitting-out cost at the start and demands a gold reserve."""
    types, effects, values = _text(TYPES), _text(EFFECTS), _text(VALUES)
    assert "pp_te_pay_effect = { COST = pp_te_cost_$KIND$ }" in effects
    for kind in KINDS:
        start = types.index(f"\npp_te_{kind} = {{")
        body = types[start: types.find("\npp_te_", start + 1)]
        assert f"gold >= pp_te_reserve_{kind}" in body, kind
        assert f"pp_te_start_effect = {{ KIND = {kind} }}" in body, kind
        start = values.index(f"pp_te_cost_{kind} = {{")
        assert "yearly_gold" in values[start: values.index("\n}", start)], kind


def test_localization_has_no_balance_numbers() -> None:
    """Player-facing text names no balance values (AGENTS.md Localization)."""
    for line in _text(LOC).splitlines():
        if ":" not in line or line.strip().startswith("#") or "historical_info" in line:
            continue
        value = line.split(":", 1)[1]
        assert not re.search(r"\d+ ?%|[+-]\d", value), line


def test_fort_works_modifiers_exist_with_text() -> None:
    """The castle is built to the standard of its age: every works modifier it adds exists, raises the fort level and has text."""
    modifiers_path = MOD_ROOT / "main_menu" / "common" / "static_modifiers" / "pp_trade_expedition_modifiers.txt"
    modifiers = _top_keys(modifiers_path)
    text = _text(modifiers_path)
    loc = _loc_keys()
    used = set(re.findall(r"modifier = (pp_te_works_[a-z_]+)", _text(EFFECTS)))
    assert used and used <= modifiers, used - modifiers
    for name in modifiers:
        body = text[text.index(f"{name} = {{"):]
        assert re.search(r"fort_level = \d", body[: body.index("\n}")]), name
        assert f"STATIC_MODIFIER_NAME_{name}" in loc and f"STATIC_MODIFIER_DESC_{name}" in loc, name


def test_chartered_company_subject_type() -> None:
    """Asian castle towns go to a land-holding chartered company: the subject type exists, is never offered in
    diplomacy, and has a name."""
    path = COMMON / "subject_types" / "pp_te_company.txt"
    text = _text(path)
    assert "pp_te_company = {" in text
    assert "type = building" not in text  # land-holding; script-made building companies died in Asia
    for key in ("creation_visible", "visible_through_diplomacy", "visible_through_treaty"):
        start = text.index(f"{key} = {{")
        assert "always = no" in text[start: text.index("}", start)], key
    assert "subject_type:pp_te_company" in _text(EFFECTS)
    assert "pp_te_company" in _loc_keys()
