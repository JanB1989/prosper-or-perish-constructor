"""Country start adjustments (docs/country_finetunes.md, 2026-11-19, Jan) stay wired together.

A country's change to the vanilla treasury is one scripted effect. On the first day of a new game an AI country takes
it, always; a human player gets the country's event, whose accept option calls the same effect and whose decline option
changes nothing. Nothing else in the mod's game-start scripts touches a treasury, so a player who declines keeps the
vanilla start and nobody gets an adjustment twice.
"""

from __future__ import annotations

import re
from pathlib import Path

from eu5gameparser.clausewitz.parser import parse_file, parse_text
from eu5gameparser.clausewitz.syntax import CList

MOD = Path(__file__).resolve().parents[1] / "mod" / "pp"
EFFECT_FILE = MOD / "in_game/common/scripted_effects/pp_country_start_adjustments.txt"
ON_ACTION_FILE = MOD / "in_game/common/on_action/pp_country_finetunes.txt"
EVENT_FILE = MOD / "in_game/events/pp_start_adjustment_events.txt"
LOC_FILE = MOD / "main_menu/localization/english/pp_country_finetunes_l_english.yml"
ON_ACTION = "pp_country_start_adjustments"
EFFECT_PREFIX = "pp_start_adjustment_"
ACCEPT, DECLINE = "pp_start_adjustments.accept", "pp_start_adjustments.decline"
DECLINE_TOOLTIP = "pp_start_adjustments.decline.tt"
# A start adjustment changes money only; aims, preferences, opinions and advances are no start adjustments.
MONEY_EFFECTS = {"add_gold", "add_inflation"}
TREASURY_KEYS = re.compile(r"\b(add_gold|add_inflation|add_loan|add_gold_to_estate|change_gold_effect)\b")


def _code(path: Path) -> str:
    return re.sub(r"#[^\n]*", "", path.read_text(encoding="utf-8-sig"))


def _block(text: str, name: str, top: bool = False) -> str:
    """The text inside the first ``name = { ... }`` (``top``: only at the start of a line)."""
    anchor = "^" if top else r"\b"
    match = re.search(anchor + re.escape(name) + r" \??= \{", text, re.MULTILINE)
    assert match, f"{name} missing"
    depth = 0
    for i in range(match.end() - 1, len(text)):
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        if depth == 0:
            return text[match.end():i]
    raise AssertionError(f"{name}: unbalanced braces")


def _effects() -> dict[str, CList]:
    return {entry.key: entry.value for entry in parse_file(EFFECT_FILE).entries}


def _events() -> dict[str, CList]:
    return {entry.key: entry.value for entry in parse_file(EVENT_FILE).entries if isinstance(entry.value, CList)}


def _branches() -> dict[str, tuple[str, str]]:
    """Country tag -> (effect the AI gets, event a human player gets), read from the on_action."""
    effect = _block(_block(_code(ON_ACTION_FILE), ON_ACTION, top=True), "effect")
    branches = {}
    for tag in re.findall(r"\bc:([A-Z0-9]{3}) \?= \{", effect):
        body = parse_text(_block(effect, f"c:{tag}"))
        assert [entry.key for entry in body.entries] == ["if", "else"], tag
        then, other = body.entries[0].value, body.entries[1].value
        assert [(e.key, e.value) for e in then.first("limit").entries] == [("is_ai", True)], tag
        calls = [(e.key, e.value) for e in then.entries if e.key != "limit"]
        assert len(calls) == 1 and calls[0][1] is True, f"{tag}: the AI branch calls one effect"
        fired = [(e.key, e.value) for e in other.entries]
        assert len(fired) == 1 and fired[0][0] == "trigger_event_silently", f"{tag}: the player branch fires one event"
        assert tag not in branches, f"{tag} twice"
        branches[tag] = (calls[0][0], fired[0][1])
    return branches


def _loc() -> dict[str, str]:
    return dict(re.findall(r'^ ([A-Za-z0-9_.]+):\d* "(.*)"$', LOC_FILE.read_text(encoding="utf-8-sig"), re.MULTILINE))


def test_every_adjustment_is_one_money_effect_per_country() -> None:
    effects = _effects()
    assert effects, "no start adjustments"
    for name, body in effects.items():
        assert re.fullmatch(rf"{EFFECT_PREFIX}[a-z0-9]{{3}}", name), name
        keys = {entry.key for entry in body.entries}
        assert keys and keys <= MONEY_EFFECTS, f"{name}: a start adjustment changes money only, not {sorted(keys - MONEY_EFFECTS)}"


def test_the_ai_takes_and_a_player_chooses_the_same_effect() -> None:
    effects, events, branches = _effects(), _events(), _branches()
    assert sorted(effect for effect, _ in branches.values()) == sorted(effects), "every effect belongs to one country"
    assert len({event for _, event in branches.values()}) == len(branches), "every country has its own event"
    assert set(events) == {event for _, event in branches.values()}, "an event nobody fires"
    for tag, (effect, event_id) in branches.items():
        assert effect == f"{EFFECT_PREFIX}{tag.lower()}", tag
        event = events[event_id]
        assert event.first("type") == "country_event", event_id
        assert event.first("trigger") is None, f"{event_id}: a trigger could keep a player from the choice"
        accept, decline = event.values("option")
        assert (accept.first("name"), decline.first("name")) == (ACCEPT, DECLINE), event_id
        assert [(e.key, e.value) for e in accept.entries if e.key not in ("name", "ai_chance")] == [(effect, True)], event_id
        assert [(e.key, e.value) for e in decline.entries if e.key not in ("name", "ai_chance")] == [
            ("custom_tooltip", DECLINE_TOOLTIP)], f"{event_id}: decline changes nothing, its tooltip says so"
        assert (accept.first("ai_chance").first("factor"), decline.first("ai_chance").first("factor")) == (100, 0), event_id


def test_adjustments_run_on_the_first_day_once_players_hold_their_countries() -> None:
    on_actions = _block(_block(_code(ON_ACTION_FILE), "on_game_start", top=True), "on_actions")
    before, after = re.split(r"\bdelay = \{ days = 1 \}", on_actions, maxsplit=1)
    assert ON_ACTION in after.split() and ON_ACTION not in before.split(), f"{ON_ACTION} runs after the day's delay only"


def test_nothing_else_changes_a_treasury_at_game_start() -> None:
    # The old pp_country_finetune_start_gold gave the gold at on_game_start to every country, players included.
    for path in sorted((MOD / "in_game/common/on_action").glob("*.txt")):
        assert not TREASURY_KEYS.search(_code(path)), f"{path.name}: treasury changes at start go through {EFFECT_FILE.name}"
    callers = set()
    for folder in ("in_game/common", "in_game/events"):
        for path in (MOD / folder).rglob("*.txt"):
            if path != EFFECT_FILE and EFFECT_PREFIX in (code := _code(path)):
                callers.add(path)
                assert set(re.findall(rf"\b({EFFECT_PREFIX}\w+) = yes", code)) <= set(_effects()), path.name
    assert callers == {ON_ACTION_FILE, EVENT_FILE}


def test_every_event_text_exists_and_carries_no_numbers() -> None:
    loc = _loc()
    for event_id, event in _events().items():
        for key in (event.first("title"), event.first("desc"), ACCEPT, DECLINE, DECLINE_TOOLTIP):
            assert loc.get(key), f"{event_id}: {key} has no English text"
        desc = loc[event.first("desc")]
        assert "[treasury|e]" in desc and "[gold|e]" in desc, f"{event_id}: link the money concepts"
        # The accept option's tooltip shows the effect's numbers; the text keeps none of its own (years are fine).
        assert not re.search(r"\d", re.sub(r"\b1[3-8]\d\d\b|\\n", "", desc + loc[event.first("title")])), event_id
