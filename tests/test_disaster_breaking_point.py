"""Disasters come to a head and break (2026-11-27, Jan; AGENTS.md "Disasters Come to a Head").

Every vanilla disaster is either a same-path copy with the bands (25, 30, 35 years), the breaking point (40 years, OR
vanilla's way out) and the restart block, or exempt because vanilla ends it within 25 years. The copies are vanilla's
text plus the inserted lines; a game update that changes a vanilla disaster fails here until its on_end is reviewed
(``disaster_breaking_point.TIMEOUT_RULES``), the copies rewritten (``ppc disasters apply``) and the pins recorded
(``ppc disasters pin``).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from eu5gameparser.load_order import LoadOrderConfig

from prosper_or_perish_constructor import disaster_breaking_point as dbp

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mod" / "pp"
COPIES = MOD / dbp.DISASTERS
EFFECTS = MOD / "in_game/common/scripted_effects/pp_disaster_effects.txt"
TRIGGERS = MOD / "in_game/common/scripted_triggers/pp_disaster_triggers.txt"
EVENTS = MOD / "in_game/events/pp_disaster_events.txt"
MODIFIERS = MOD / "main_menu/common/static_modifiers/pp_disaster_modifiers.txt"
LOC = MOD / "main_menu/localization/english/pp_disasters_l_english.yml"


@pytest.fixture(scope="module")
def game() -> Path:
    return LoadOrderConfig.load(ROOT / "constructor.load_order.toml").vanilla_root / "game"


def _norm(text: str) -> str:
    return " ".join(re.sub(r"#[^\n]*", "", text).split())


def _parts(text: str) -> tuple[str, dict[str, list[dbp.Block]], dbp.Block]:
    mask = dbp._code_mask(text)
    (disaster,) = dbp._blocks(text, 0, len(text), mask)
    inner: dict[str, list[dbp.Block]] = {}
    for block in dbp._blocks(text, disaster.open + 1, disaster.close, mask):
        inner.setdefault(block.key, []).append(block)
    return disaster.key, inner, disaster


def _body(text: str, block: dbp.Block) -> str:
    return _norm(text[block.open + 1:block.close])


def _outside(text: str, inner: dict[str, list[dbp.Block]], disaster: dbp.Block, keys: set[str]) -> str:
    """The disaster's text with the named blocks cut out."""
    cuts = sorted((b.start, b.close + 1) for k in keys for b in inner.get(k, ()))
    out, pos = [], disaster.open + 1
    for start, end in cuts:
        out.append(text[pos:start])
        pos = end
    out.append(text[pos:disaster.close])
    return _norm("".join(out))


def _vanilla(game: Path) -> dict[str, Path]:
    return {dbp.disaster_key(p): p for p in dbp.vanilla_files(game)}


def test_every_vanilla_disaster_is_covered_or_exempt(game) -> None:
    keys = set(_vanilla(game))
    assert keys, "no vanilla disasters"
    assert not set(dbp.EXEMPT) & set(dbp.TIMEOUT_RULES)
    assert keys == set(dbp.EXEMPT) | set(dbp.TIMEOUT_RULES)
    assert all(reason.strip() for reason in dbp.EXEMPT.values())
    assert all(rule.why.strip() for rule in dbp.TIMEOUT_RULES.values())
    # a DLC that adds or replaces disasters needs this pass to read it
    for dlc in sorted((game / "dlc").glob("*")):
        assert not (dlc / dbp.DISASTERS).is_dir(), dlc.name


def test_copies_are_current_and_vanilla_is_the_reviewed_one(game) -> None:
    result = dbp.apply(ROOT, ROOT / "constructor.toml", MOD, game.parent, write=False)
    assert not result.changed and not result.removed, "run uv run ppc disasters apply"
    assert dbp.read_pins(ROOT) == dbp.current_pins(game), (
        "a vanilla disaster changed: review its on_end for rewards (TIMEOUT_RULES), then ppc disasters apply and pin")
    names = {p.name for p in COPIES.glob("*.txt")}
    assert names == {p.name for k, p in _vanilla(game).items() if k not in dbp.EXEMPT}


def test_each_copy_is_vanilla_with_the_rule_added(game) -> None:
    for key, source in _vanilla(game).items():
        if key in dbp.EXEMPT:
            continue
        vtext = source.read_text(encoding="utf-8-sig")
        ctext = (COPIES / source.name).read_text(encoding="utf-8-sig")
        vkey, vin, vdis = _parts(vtext)
        ckey, cin, cdis = _parts(ctext)
        assert vkey == ckey == key
        t = f"type = {key}"
        blocks = {"can_start", "can_end", "on_monthly", "on_end", "outcome"}
        assert _outside(ctext, cin, cdis, blocks) == _outside(vtext, vin, vdis, blocks), key
        # restart block
        assert _body(ctext, cin["can_start"][0]) == f"pp_disaster_restart_allowed_trigger = {{ {t} }} " + _body(
            vtext, vin["can_start"][0]), key
        # the bands, from the disaster's own on_monthly
        assert _body(ctext, cin["on_monthly"][0]) == _body(vtext, vin["on_monthly"][0]) + (
            f" pp_disaster_escalation_effect = {{ {t} }}"), key
        if "can_end" in vin:
            vend = _body(vtext, vin["can_end"][0])
            # the 40-year exit beside vanilla's way out
            assert _body(ctext, cin["can_end"][0]) == (
                f"OR = {{ AND = {{ {vend} }} pp_disaster_breaking_point_trigger = {{ {t} }} }}"), key
            on_end = _body(ctext, cin["on_end"][0])
            vbody = _body(vtext, vin["on_end"][0])
            assert on_end.startswith(
                f"if = {{ limit = {{ pp_disaster_breaking_point_trigger = {{ {t} }} NOT = {{ AND = {{ {vend} }} }} }} "), key
            tail = f"else = {{ {vbody} }} pp_disaster_escalation_cleanup_effect = {{ {t} }}"
            assert on_end.endswith(tail), key
            timeout = on_end[: len(on_end) - len(tail)]
            assert timeout.rstrip().endswith(f"pp_disaster_breaking_point_effect = {{ {t} }} }}"), key
            rule = dbp.TIMEOUT_RULES[key]
            for event in rule.drop_events + tuple(old for old, _ in rule.replace_events):
                assert event in vbody, (key, event)
                assert not re.search(rf"{re.escape(event)}(?![0-9A-Za-z_.])", timeout), (key, event)
            for statement in rule.drop_effects:
                assert _norm(statement) in vbody and _norm(statement) not in timeout, (key, statement)
        else:
            outcomes = cin["outcome"]
            assert len(outcomes) == len(vin["outcome"]) + 1, key
            last = _body(ctext, outcomes[-1])
            assert f"pp_disaster_breaking_point_trigger = {{ {t} }}" in last, key
            assert f"pp_disaster_breaking_point_effect = {{ {t} }}" in last, key
            for outcome in outcomes:
                assert f"pp_disaster_escalation_cleanup_effect = {{ {t} }}" in _body(ctext, outcome), key


def test_exempt_disasters_end_on_their_own_within_25_years(game) -> None:
    triggers = (game / "in_game/common/scripted_triggers/disaster_triggers.txt").read_text(encoding="utf-8-sig")
    for key in dbp.EXEMPT:
        start = triggers.find(f"{key}_end_trigger = {{")
        assert start >= 0, key
        years = re.findall(rf"disaster_type = (?:disaster_type:{key}|scope:disaster)\s+years\s*>=?\s*(\d+)", triggers[start:])
        assert years and int(years[0]) <= 25, key


def test_numbers_of_the_rule() -> None:
    triggers = _norm(TRIGGERS.read_text(encoding="utf-8-sig"))
    assert ("pp_disaster_breaking_point_trigger = { had_disaster_for_years = { disaster_type = disaster_type:$type$ "
            "years >= 40 } }") in triggers
    assert "pp_disaster_restart_allowed_trigger = { NOT = { has_blocked_disaster_trigger = { type = $type$ } } }" in triggers
    effects = _norm(EFFECTS.read_text(encoding="utf-8-sig"))
    for years, band in ((35, 3), (30, 2), (25, 1)):
        assert (f"had_disaster_for_years = {{ disaster_type = disaster_type:$type$ years >= {years} }} NOT = {{ "
                f"pp_disaster_band_reached_trigger = {{ type = $type$ band = {band} }} }} }} set_variable = {{ name = "
                f"pp_disaster_band_$type$ value = {band} }} trigger_event_silently = pp_disaster.{band}") in effects
    assert "block_disaster_temporarily_effect = { type = $type$ years = 25 years_in_days = 9125 }" in effects
    events = _norm(EVENTS.read_text(encoding="utf-8-sig"))
    for band, stability, estates in ((1, "mild", "mild"), (2, "severe", "severe"), (3, "extreme", "extreme")):
        assert (f"add_stability = stability_{stability}_penalty pp_disaster_estates_lose_satisfaction_effect = {{ value = "
                f"estate_satisfaction_{estates}_penalty }} pp_disaster_remove_band_modifiers_effect = yes "
                f"add_country_modifier = {{ modifier = pp_disaster_coming_to_head_{band}") in events
    assert "add_stability = stability_ultimate_penalty add_government_power = government_power_ultimate_penalty" in events
    modifiers = _norm(MODIFIERS.read_text(encoding="utf-8-sig"))
    for band, rebels, investment, target in ((1, "0.005", "stability_investment_penalty", "small"),
                                             (2, "0.01", "large_stability_investment_penalty", "medium"),
                                             (3, "0.02", "huge_stability_investment_penalty", "large")):
        assert (f"pp_disaster_coming_to_head_{band} = {{ game_data = {{ category = country }} monthly_rebel_growth = "
                f"{rebels} stability_investment = {investment} global_estate_target_satisfaction = "
                f"{target}_permanent_target_satisfaction_penalty }}") in modifiers


def test_texts_exist_and_hold_no_numbers() -> None:
    loc = LOC.read_text(encoding="utf-8-sig")
    keys = dict(re.findall(r"^ ([A-Za-z0-9_.]+):\d* \"(.*)\"$", loc, re.M))
    events = EVENTS.read_text(encoding="utf-8-sig")
    used = set(re.findall(r"(?:title|desc|name) = (pp_disaster\.[0-9a-z_.]+)", events))
    used |= set(re.findall(r"custom_tooltip = (pp_disaster\.[0-9a-z_.]+)", events))
    used |= {"pp_disaster_breaking_point_outcome", "pp_disaster_breaking_point_outcome_desc"}
    used |= {f"STATIC_MODIFIER_{kind}_pp_disaster_coming_to_head_{band}" for kind in ("NAME", "DESC") for band in (1, 2, 3)}
    assert used <= set(keys), sorted(used - set(keys))
    for key, text in keys.items():
        if key != "game_concept_disaster_desc":
            assert not re.search(r"\d", re.sub(r"\[[^\]]*\]", "", text)), key


def test_no_pulse_of_its_own() -> None:
    """The bands run from each disaster's on_monthly, the breaking point from its on_end: no on_action, no timed event."""
    for path in (MOD / "in_game/common/on_action").rglob("*.txt"):
        assert "pp_disaster" not in path.read_text(encoding="utf-8-sig"), path.name
    events = EVENTS.read_text(encoding="utf-8-sig")
    for word in ("dynamic_historical_event", "mean_time_to_happen", "trigger_event", "days ="):
        assert word not in re.sub(r"set_variable = \{[^}]*\}", "", events), word
    callers = {"pp_disaster_escalation_effect", "pp_disaster_breaking_point_effect"}
    for path in [*(MOD / "in_game").rglob("*.txt"), *(MOD / "main_menu/common").rglob("*.txt")]:
        if path.parent == COPIES or path == EFFECTS:
            continue
        text = _norm(path.read_text(encoding="utf-8-sig", errors="replace"))
        for name in callers:
            assert name not in text, (path.relative_to(MOD), name)
