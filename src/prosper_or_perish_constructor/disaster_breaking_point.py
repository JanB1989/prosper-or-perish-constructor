"""Disasters come to a head and break (2026-11-27, Jan).

Observer runs kept about 20 disasters running for more than 50 years and about 10 for more than a century (the Ottomans
in ``religious_turmoil`` 1538-1837, Yuan in ``crisis_of_the_chinese_dynasty`` from 1441, the Nahuatl states in
``reform_society`` for 300-400 years). A vanilla disaster has no timer: it ends only when ``can_end`` holds, and while it
runs the AI declares no war and (``has_any_active_disaster = no`` in nearly every ``can_start``) no other disaster starts.
Jan: "It shouldn't be 250 years of disaster. It should at some point either be resolved or accelerated in a manner that
has catastrophic consequences"; "I like the 25-year variant, then ramp up ... in the vanilla style".

One rule for every disaster, written into same-path copies of vanilla's disaster files (a mod file with the same
relative path replaces vanilla's whatever the rule; ``INJECT:`` cannot do it: an injected trigger section the target
already has is dropped, and ``can_end`` must become vanilla's condition OR the breaking point):

- ``can_start`` gets ``pp_disaster_restart_allowed_trigger``: no restart while the block set at a breaking point runs.
- ``can_end`` becomes ``OR = { AND = { <vanilla> } pp_disaster_breaking_point_trigger = { type = <disaster> } }``.
- ``on_monthly`` ends with ``pp_disaster_escalation_effect``: the three bands (events ``pp_disaster.1-3``).
- ``on_end`` becomes: past the breaking point without vanilla's way out, vanilla's ``on_end`` without its reward for a
  won disaster (``TIMEOUT_RULES``), the disaster's own cleanup, then ``pp_disaster_breaking_point_effect`` (the blow,
  event ``pp_disaster.10``, and the restart block); otherwise vanilla's ``on_end`` unchanged. The band modifiers go in
  both cases.
- A disaster that ends by ``outcome`` blocks (``rise_of_the_szlachta``) gets the band cleanup in each outcome and one
  more outcome for the breaking point, valid only when no vanilla outcome is.

The scripted triggers, effects, events and modifiers are hand-written (``pp_disaster_*``); this pass writes only the
copies. Vanilla's text stays byte for byte apart from the inserted lines, so a game update is ``ppc disasters apply``;
``tests/disaster_vanilla_pins.csv`` holds a hash of each vanilla file reviewed (``ppc disasters pin``), and the test
fails when vanilla changes one: review its ``on_end`` for rewards first (``TIMEOUT_RULES``).
"""

from __future__ import annotations

import csv
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

MOD_FOLDER = "pp"
DISASTERS = Path("in_game/common/disasters")
PINS_PATH = Path("tests") / "disaster_vanilla_pins.csv"
HEADER = ("# PP: same-path copy of vanilla's disaster, written by `uv run ppc disasters apply` "
          "(src/prosper_or_perish_constructor/disaster_breaking_point.py); do not edit.")
MARK = "# PP: breaking point"

# Disasters vanilla already ends within 25 years: they stay as they are (Jan, 2026-11-27).
EXEMPT: dict[str, str] = {
    "aspiration_for_liberty": "vanilla ends it after 20 years (aspiration_for_liberty_end_trigger)",
    "coup_attempt": "vanilla ends it after 5 years (coup_attempt_end_trigger, inconclusive ending)",
    "court_and_country": "vanilla ends it after 20 years (court_and_country_end_trigger)",
    "english_civil_war": "vanilla ends it after 10 years once no civil war runs; ends_on_regime_change",
    "french_wars_religion": "vanilla ends it after 25 years (french_wars_religion.14, the unresolved ending)",
    "revolutionary_chaos": "vanilla ends it after 10 years once no civil war runs",
    "time_of_troubles": "vanilla ends it after 15 years (time_of_troubles_end_trigger)",
}


@dataclass(frozen=True)
class TimeoutRule:
    """How vanilla's on_end runs at a breaking point: the reward for a won disaster goes, the cleanup stays.

    ``drop_events``: events whose ``trigger_event_*`` statement is removed (every one must be found);
    ``drop_effects``: exact ``key = value`` statements removed; ``replace_events``: event ids exchanged;
    ``cleanup``: lines added after it (what a dropped event did besides its reward); ``why``: the review."""

    why: str
    drop_events: tuple[str, ...] = ()
    drop_effects: tuple[str, ...] = ()
    replace_events: tuple[tuple[str, str], ...] = ()
    cleanup: tuple[str, ...] = ()


_SUCCESSION_CLEANUP = (
    "remove_variable = pretender_given_throne_variable",
)

TIMEOUT_RULES: dict[str, TimeoutRule] = {
    "fate_of_the_phoenix": TimeoutRule(
        "won: .14 (casus belli, military modifier, won variable); the loss .15 is vanilla's unresolved ending",
        replace_events=(("fate_of_the_phoenix.14", "fate_of_the_phoenix.15"),)),
    "ambrosian_republic_disaster": TimeoutRule(
        "ambrosian_republic_disaster.1 is the reward (stability, prestige)",
        drop_events=("ambrosian_republic_disaster.1",)),
    "byzantine_succession_crisis": TimeoutRule(
        "legitimacy in on_end and succession_crisis.100 are the reward; its after-block cleanup kept here",
        drop_events=("succession_crisis.100",), drop_effects=("add_legitimacy = legitimacy_extreme_bonus",),
        cleanup=_SUCCESSION_CLEANUP),
    "castilian_civil_war": TimeoutRule(
        "legitimacy in on_end, castilian_civil_war.100 (peace option: legitimacy, stability) and succession_crisis.100 "
        "are the reward; no civil war runs at a breaking point (can_end holds in one), so .100 would take its peace option",
        drop_events=("castilian_civil_war.100", "succession_crisis.100"),
        drop_effects=("add_legitimacy = legitimacy_extreme_bonus",),
        cleanup=(*_SUCCESSION_CLEANUP,
                 "every_character = { limit = { has_character_modifier = ccw_ruler_siblings } "
                 "remove_character_modifier = ccw_ruler_siblings }")),
    "ciompi_revolt": TimeoutRule("ciompi_revolt.8 is the reward (stability, political influence, Medici)",
                                 drop_events=("ciompi_revolt.8",)),
    "crisis_of_faith": TimeoutRule(
        "the won branch's devotion and crisis_of_faith.100 are the reward; .101/.102 are losses; the heresiarch cleanup "
        "of .100's after-block kept here",
        drop_events=("crisis_of_faith.100",), drop_effects=("add_devotion = devotion_extreme_bonus",),
        cleanup=("clear_crisis_of_faith_heresiarch_effect = yes",)),
    "crisis_of_the_chinese_dynasty": TimeoutRule("no reward: .2 and .3 are both penalties; kept"),
    "crisis_of_the_sayfawa_dynasty": TimeoutRule(
        "crisis_of_the_sayfawa_dynasty.6: stability and influence reward (and Bilala land abandoned); the blow replaces it",
        drop_events=("crisis_of_the_sayfawa_dynasty.6",)),
    "curse_of_stefan_uros_iii": TimeoutRule(
        "curse_of_stefan_uros_iii.2 is the reward; its flag kept here",
        drop_events=("curse_of_stefan_uros_iii.2",), cleanup=("set_variable = had_serbian_disaster_variable",)),
    "death_of_hayan_wuruk": TimeoutRule(
        "vanilla ends it at 30 years with its own timeout branch (.7, a penalty), before the breaking point; kept"),
    "decline_of_empire": TimeoutRule("decline_of_empire.2 is the reward (stability, pop satisfaction)",
                                     drop_events=("decline_of_empire.2",)),
    "decline_of_majapahit": TimeoutRule("decline_of_majapahit.100 is the reward (stability, Weathered the Storm)",
                                        drop_events=("decline_of_majapahit.100",)),
    "decline_of_mali": TimeoutRule("decline_of_mali.2 is mostly reward (prestige, stability)",
                                   drop_events=("decline_of_mali.2",)),
    "dissolution_of_delhi": TimeoutRule("dissolution_of_delhi.7 is the reward (Restored Authority)",
                                        drop_events=("dissolution_of_delhi.7",)),
    "hook_and_cod_wars": TimeoutRule(
        "hook_and_cod_wars.100 kept: it crowns the ruler and cleans up through scripted effects local to its event file, "
        "which a disaster file cannot call; its stability is the one reward left at a breaking point"),
    "horde_civil_war": TimeoutRule("horde_civil_war.100 is the reward (stability)", drop_events=("horde_civil_war.100",)),
    "muscovite_succession_war": TimeoutRule("muscovite_succession_war.20 is the reward",
                                            drop_events=("muscovite_succession_war.20",)),
    "oligarchic_capture": TimeoutRule(
        "the restored branch's republican tradition and oligarchic_capture.100 are the reward; .101 is the loss; the "
        "ringleader cleanup of .100's after-block kept here",
        drop_events=("oligarchic_capture.100",),
        drop_effects=("add_republican_tradition = republican_tradition_extreme_bonus",),
        cleanup=("if = { limit = { exists = var:oligarchic_ringleader_variable } "
                 "remove_variable = oligarchic_ringleader_variable }",
                 "if = { limit = { has_variable = oligarchic_ringleader_revealed_variable } "
                 "remove_variable = oligarchic_ringleader_revealed_variable }")),
    "peasants_war": TimeoutRule("peasants_war.6 is the reward (stability, estate modifier)",
                                drop_events=("peasants_war.6",)),
    "reform_society": TimeoutRule("reform_society.2 is the reward (the reformed society, annexed altepetl)",
                                  drop_events=("reform_society.2",)),
    "religious_turmoil": TimeoutRule("religious_turmoil.2 is the reward (stability)",
                                     drop_events=("religious_turmoil.2",)),
    "revolution_disaster": TimeoutRule(
        "revolution_disaster.3 is the reward (government power, stability); its list removal kept here, its 20-year "
        "block is the breaking point's own",
        drop_events=("revolution_disaster.3",), cleanup=("remove_from_revolutionary_list = yes",)),
    "rise_of_the_szlachta": TimeoutRule("ends by outcomes: the breaking point is one more outcome"),
    "savonarola_disaster": TimeoutRule(
        "savonarola_disaster.11 is the reward (government power); its variable cleanup kept here",
        drop_events=("savonarola_disaster.11",),
        cleanup=("if = { limit = { has_variable = flo_savonarola_reforms } remove_variable = flo_savonarola_reforms }",
                 "if = { limit = { has_variable = flo_savonarola_piagnoni } remove_variable = flo_savonarola_piagnoni }")),
    "sinicization_disaster": TimeoutRule(
        "sinicization_disaster.100 holds the rewards (victory over China, sovereign realm); its after-block (restart "
        "gate, variables, modifiers) kept here",
        drop_events=("sinicization_disaster.100",),
        cleanup=("set_variable = { name = had_sinicization_disaster_variable years = 10 }",
                 "remove_variable = sovereign_side", "remove_variable = china_side",
                 "remove_variable = sinicization_attitude_event_variable",
                 "remove_country_modifier = struggle_against_china_modifier",
                 "remove_country_modifier = embracing_sinicization_modifier")),
    "struggle_for_royal_power": TimeoutRule("no reward: struggle_for_royal_power.100 only cleans up; kept"),
    "succession_crisis": TimeoutRule(
        "legitimacy in on_end, castilian_civil_war.100 and succession_crisis.100 are the reward",
        drop_events=("castilian_civil_war.100", "succession_crisis.100"),
        drop_effects=("add_legitimacy = legitimacy_extreme_bonus",),
        cleanup=(*_SUCCESSION_CLEANUP,
                 "every_character = { limit = { has_character_modifier = ccw_ruler_siblings } "
                 "remove_character_modifier = ccw_ruler_siblings }")),
    "turmoil_in_brandenburg": TimeoutRule("turmoil_in_brandenburg.300 is the reward (Overcome the Turmoil)",
                                          drop_events=("turmoil_in_brandenburg.300",)),
    "twilight_of_the_tsardom": TimeoutRule(
        ".2/.3/.4 are rewards; the removal of the local elites modifiers (all three) kept here",
        drop_events=("twilight_of_the_tsardom.2", "twilight_of_the_tsardom.3", "twilight_of_the_tsardom.4"),
        cleanup=("every_owned_location = { limit = { has_location_modifier = bul_powerful_local_elites } "
                 "remove_location_modifier = bul_powerful_local_elites }",)),
    "war_of_the_aragonese_union_disaster": TimeoutRule(
        "war_of_the_aragonese_union_disaster.3 option b is the reward; option a (penalty) goes with it",
        drop_events=("war_of_the_aragonese_union_disaster.3",)),
    "war_of_the_roses": TimeoutRule("war_of_the_roses.100 is the reward (stability, prestige, supporters' events)",
                                    drop_events=("war_of_the_roses.100",)),
}


class DisasterError(ValueError):
    pass


@dataclass
class Copy:
    name: str          # file name
    key: str           # disaster key
    data: bytes


@dataclass
class Result:
    copies: list[Copy] = field(default_factory=list)
    exempt: list[str] = field(default_factory=list)
    changed: list[Path] = field(default_factory=list)
    removed: list[Path] = field(default_factory=list)


# ---------------------------------------------------------------------------------------------------------- text scan

def _code_mask(text: str) -> list[bool]:
    """True for each character that is script (not inside a comment or a quoted string)."""
    mask = [True] * len(text)
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "#":
            j = text.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                mask[k] = False
            i = j
        elif c == '"':
            j = text.find('"', i + 1)
            j = n - 1 if j < 0 else j
            for k in range(i, j + 1):
                mask[k] = False
            i = j + 1
        else:
            i += 1
    return mask


@dataclass(frozen=True)
class Block:
    key: str
    start: int   # first character of the key
    open: int    # index of "{"
    close: int   # index of the matching "}"


_KEY_AT = re.compile(r"([A-Za-z0-9_.:]+)[ \t\r\n]*=[ \t\r\n]*\{")


def _blocks(text: str, lo: int, hi: int, mask: list[bool]) -> list[Block]:
    """The ``key = { ... }`` blocks directly inside text[lo:hi] (depth 0 there)."""
    out: list[Block] = []
    depth = 0
    i = lo
    while i < hi:
        if not mask[i]:
            i += 1
            continue
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif depth == 0 and (c.isalnum() or c == "_") and (i == lo or not (text[i - 1].isalnum() or text[i - 1] in "_.:")):
            m = _KEY_AT.match(text, i)
            if m and all(mask[k] for k in range(m.start(), m.end())) and m.end() <= hi:
                open_ = m.end() - 1
                close = _match(text, open_, mask)
                out.append(Block(m.group(1), i, open_, close))
                i = close + 1
                continue
        i += 1
    return out


def _match(text: str, open_: int, mask: list[bool]) -> int:
    depth = 0
    for i in range(open_, len(text)):
        if not mask[i]:
            continue
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    raise DisasterError("unbalanced braces")


def _one(blocks: list[Block], key: str, where: str) -> Block | None:
    found = [b for b in blocks if b.key == key]
    if len(found) > 1:
        raise DisasterError(f"{where}: {len(found)} {key} blocks")
    return found[0] if found else None


# ------------------------------------------------------------------------------------------------------ the timeout

def _event_statement(event: str) -> re.Pattern[str]:
    ev = re.escape(event)
    return re.compile(
        rf"trigger_event_(?:non_)?silently[ \t]*=[ \t]*(?:\{{\s*id[ \t]*=[ \t]*{ev}\s*\}}|{ev})(?![A-Za-z0-9_.])"
        rf"[ \t]*(?:#[^\r\n]*)?")


def timeout_body(key: str, body: str, rule: TimeoutRule) -> str:
    """Vanilla's on_end body as it runs at a breaking point: every listed reward statement out."""
    out = body
    for event in rule.drop_events:
        out, n = _event_statement(event).subn("", out)
        if not n:
            raise DisasterError(f"{key}: on_end fires no {event} (vanilla changed; review TIMEOUT_RULES)")
    for statement in rule.drop_effects:
        lhs, _, rhs = statement.partition("=")
        pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(lhs.strip())}[ \t]*=[ \t]*{re.escape(rhs.strip())}(?![A-Za-z0-9_])")
        out, n = pattern.subn("", out)
        if not n:
            raise DisasterError(f"{key}: on_end has no `{statement}` (vanilla changed; review TIMEOUT_RULES)")
    for old, new in rule.replace_events:
        pattern = re.compile(rf"(?<![A-Za-z0-9_.]){re.escape(old)}(?![A-Za-z0-9_.])")
        out, n = pattern.subn(new, out)
        if not n:
            raise DisasterError(f"{key}: on_end fires no {old} (vanilla changed; review TIMEOUT_RULES)")
    return out


# ------------------------------------------------------------------------------------------------------- the copy

def _indent(lines: list[str], tabs: int, nl: str) -> str:
    return "".join("\t" * tabs + line + nl for line in lines)


def rewrite(name: str, text: str) -> tuple[str, str]:
    """(disaster key, the copy's text) for a vanilla disaster file's text (BOM stripped)."""
    nl = "\r\n" if "\r\n" in text else "\n"
    mask = _code_mask(text)
    top = _blocks(text, 0, len(text), mask)
    if len(top) != 1:
        raise DisasterError(f"{name}: {len(top)} top-level blocks, expected one disaster")
    disaster = top[0]
    key = disaster.key
    if key in EXEMPT:
        raise DisasterError(f"{name}: {key} is exempt")
    rule = TIMEOUT_RULES.get(key)
    if rule is None:
        raise DisasterError(f"{name}: {key} has no TIMEOUT_RULES entry nor an EXEMPT reason (review its on_end)")
    inner = _blocks(text, disaster.open + 1, disaster.close, mask)
    where = f"{name} ({key})"
    can_start = _one(inner, "can_start", where)
    can_end = _one(inner, "can_end", where)
    on_monthly = _one(inner, "on_monthly", where)
    on_end = _one(inner, "on_end", where)
    outcomes = [b for b in inner if b.key == "outcome"]
    if can_start is None or on_monthly is None:
        raise DisasterError(f"{where}: no can_start or on_monthly")
    if (can_end is None) != (on_end is None) or (can_end is None and not outcomes):
        raise DisasterError(f"{where}: expected can_end with on_end, or outcome blocks")
    t = f"type = {key}"
    edits: list[tuple[int, int, str]] = []   # (start, end, replacement), applied from the back

    # can_start: no restart while the breaking point's block runs
    edits.append((can_start.open + 1, can_start.open + 1,
                  f"{nl}\t\tpp_disaster_restart_allowed_trigger = {{ {t} }} {MARK}{nl}"))
    # on_monthly: the bands
    edits.append((on_monthly.close, on_monthly.close,
                  f"\t{MARK}{nl}\t\tpp_disaster_escalation_effect = {{ {t} }}{nl}\t"))
    if can_end is not None:
        vanilla_end = text[can_end.open + 1:can_end.close]
        edits.append((can_end.open, can_end.close + 1, (
            f"{{ {MARK}: vanilla's way out, or the breaking point{nl}"
            f"\t\tOR = {{{nl}\t\t\tAND = {{{vanilla_end}}}{nl}"
            f"\t\t\tpp_disaster_breaking_point_trigger = {{ {t} }}{nl}\t\t}}{nl}\t}}")))
        body = text[on_end.open + 1:on_end.close]
        timeout = timeout_body(key, body, rule)
        cleanup = _indent(list(rule.cleanup), 3, nl)
        edits.append((on_end.open, on_end.close + 1, (
            f"{{ {MARK}: past it without vanilla's way out, vanilla's end without the reward, then the blow{nl}"
            f"\t\tif = {{{nl}"
            f"\t\t\tlimit = {{{nl}"
            f"\t\t\t\tpp_disaster_breaking_point_trigger = {{ {t} }}{nl}"
            f"\t\t\t\tNOT = {{ AND = {{{vanilla_end}}} }}{nl}"
            f"\t\t\t}}{nl}"
            f"\t\t\t{timeout.strip()}{nl}"
            f"{cleanup}"
            f"\t\t\tpp_disaster_breaking_point_effect = {{ {t} }}{nl}"
            f"\t\t}}{nl}"
            f"\t\telse = {{{body}}}{nl}"
            f"\t\tpp_disaster_escalation_cleanup_effect = {{ {t} }}{nl}\t}}")))
    else:
        triggers: list[str] = []
        for outcome in outcomes:
            parts = _blocks(text, outcome.open + 1, outcome.close, mask)
            trig = _one(parts, "trigger", where)
            effect = _one(parts, "effect", where)
            if trig is None or effect is None:
                raise DisasterError(f"{where}: an outcome without trigger or effect")
            triggers.append(text[trig.open + 1:trig.close])
            edits.append((effect.close, effect.close,
                          f"\t{MARK}{nl}\t\t\tpp_disaster_escalation_cleanup_effect = {{ {t} }}{nl}\t\t"))
        nots = "".join(f"\t\t\t\tNOT = {{ AND = {{{trig}}} }}{nl}" for trig in triggers)
        last = outcomes[-1]
        edits.append((last.close + 1, last.close + 1, (
            f"{nl}\t{MARK}: no vanilla outcome in sight{nl}"
            f"\toutcome = {{{nl}"
            f"\t\tname = \"pp_disaster_breaking_point_outcome\"{nl}"
            f"\t\tdesc = \"pp_disaster_breaking_point_outcome_desc\"{nl}"
            f"\t\ttrigger = {{{nl}"
            f"\t\t\tpp_disaster_breaking_point_trigger = {{ {t} }}{nl}"
            f"{nots}"
            f"\t\t}}{nl}"
            f"\t\teffect = {{{nl}"
            f"\t\t\tpp_disaster_escalation_cleanup_effect = {{ {t} }}{nl}"
            f"\t\t\tpp_disaster_breaking_point_effect = {{ {t} }}{nl}"
            f"\t\t}}{nl}"
            f"\t}}")))
    out = text
    for start, end, new in sorted(edits, key=lambda e: e[0], reverse=True):
        out = out[:start] + new + out[end:]
    return key, f"{HEADER}{nl}{out}"


def vanilla_files(game_root: Path) -> list[Path]:
    folder = Path(game_root) / DISASTERS
    return sorted(p for p in folder.glob("*.txt") if p.name != "readme.txt")


def disaster_key(path: Path) -> str:
    text = path.read_text(encoding="utf-8-sig")
    top = _blocks(text, 0, len(text), _code_mask(text))
    if len(top) != 1:
        raise DisasterError(f"{path.name}: {len(top)} top-level blocks")
    return top[0].key


def plan(game_root: Path) -> Result:
    result = Result()
    files = vanilla_files(game_root)
    if not files:
        raise DisasterError(f"{game_root}: no vanilla disasters")
    keys = {disaster_key(p): p for p in files}
    stale = [k for k in sorted(set(EXEMPT) | set(TIMEOUT_RULES)) if k not in keys]
    if stale:
        raise DisasterError(f"rules for disasters vanilla no longer has: {', '.join(stale)}")
    for key, path in sorted(keys.items(), key=lambda kv: kv[1].name):
        if key in EXEMPT:
            result.exempt.append(key)
            continue
        raw = path.read_bytes()
        bom = raw.startswith(b"\xef\xbb\xbf")
        text = raw.decode("utf-8-sig")
        _, copy = rewrite(path.name, text)
        result.copies.append(Copy(path.name, key, (b"\xef\xbb\xbf" if bom else b"") + copy.encode("utf-8")))
    return result


def _game_root(repo: Path, project: Path, vanilla_root: Path | None) -> Path:
    from prosper_or_perish_constructor.cap_tooltips import game_root
    from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root as configured

    return game_root(Path(vanilla_root) if vanilla_root is not None else configured(repo, project))


def apply(repo: Path, project: Path, mod_root: Path | None = None, vanilla_root: Path | None = None, *,
          write: bool = True) -> Result:
    """Write (or with ``write=False`` only compare) the disaster copies; stale copies of exempt or gone disasters go."""
    repo = Path(repo)
    mod_root = Path(mod_root) if mod_root is not None else repo / "mod" / MOD_FOLDER
    result = plan(_game_root(repo, project, vanilla_root))
    folder = mod_root / DISASTERS
    wanted = {c.name for c in result.copies}
    for copy in result.copies:
        path = folder / copy.name
        if not path.is_file() or path.read_bytes() != copy.data:
            result.changed.append(DISASTERS / copy.name)
            if write:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(copy.data)
    for path in sorted(folder.glob("*.txt")) if folder.is_dir() else ():
        if path.name not in wanted:
            result.removed.append(DISASTERS / path.name)
            if write:
                path.unlink()
    return result


def file_hash(path: Path) -> str:
    """Hash of a vanilla disaster file's text (BOM and line endings ignored)."""
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def current_pins(game_root: Path) -> dict[str, str]:
    return {p.name: file_hash(p) for p in vanilla_files(game_root)}


def read_pins(repo: Path) -> dict[str, str]:
    path = Path(repo) / PINS_PATH
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["file"]: row["vanilla_hash"] for row in csv.DictReader(handle)}


def write_pins(repo: Path, project: Path, vanilla_root: Path | None = None) -> dict[str, str]:
    pins = current_pins(_game_root(Path(repo), project, vanilla_root))
    path = Path(repo) / PINS_PATH
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["file", "vanilla_hash"])
        for name in sorted(pins):
            writer.writerow([name, pins[name]])
    return pins


def summary(result: Result, *, check: bool = False) -> str:
    if check:
        state = "current" if not (result.changed or result.removed) else (
            "OFF (run uv run ppc disasters apply): " + ", ".join(str(p) for p in [*result.changed, *result.removed]))
    else:
        n = len(result.changed) + len(result.removed)
        state = f"{n} files rewritten" if n else "unchanged"
    return (f"Disasters come to a head: {len(result.copies)} vanilla disasters copied with the bands and the breaking "
            f"point, {len(result.exempt)} exempt (vanilla ends them within 25 years); {state}.")
