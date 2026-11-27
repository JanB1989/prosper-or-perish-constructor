"""Long disasters: growing pain (2026-11-27, Jan; replaces the breaking point of the same morning).

Observer runs kept general disasters running for decades: of 14 ``religious_turmoil`` cases stuck 50+ years, 13 met
every condition but stability (the Ottomans from year 29 at stability ~4 against the bar of 30). A vanilla disaster has
no timer, and while it runs the AI declares no war and no other disaster starts. Jan: "I want there to be a period of
pain. If it's resolved with whatever conditions the game wants to have, then it's fine. If it's not resolved, there's
a period of growing bigger pain, but at the end, you can resolve it with lower stability if you survived until then";
"I kind of don't even want something like a hard end"; the pain must not lower what the disaster's end asks for
("circular"), it should weaken the state "until breakaway factions or other nations feel strong enough to come in",
and "it shouldn't always just cause bankruptcy".

Scope: only GENERAL disasters (``COVERED``: any country of a broad kind can get them). Disasters tied to one tag, one
culture or one scripted national story keep vanilla's file (``VANILLA``); so do those vanilla ends by its own timer
within 25 years (``EXEMPT``).

The rule, written into same-path copies of vanilla's disaster files (a same-path mod file replaces vanilla's;
``INJECT:`` cannot add to a trigger section the target already has):

- Years 0-25: vanilla.
- ``on_monthly`` ends with ``pp_disaster_pain_effect``: from 25 years one country modifier per five years
  (``pp_disaster_pain_<disaster>_1..5`` at 25/30/35/40/45, each worse, swapped in place; notice events
  ``pp_disaster.1`` / ``.2``). The last step stays for as long as the disaster runs: there is no hard end. The lines
  come from ``CORE`` plus the disaster's own ``extra`` (``COVERED``); a line that would lower a number the disaster's
  ``can_end`` asks for (``EXIT_NUMBERS``, ``STABILITY``) is never written.
- ``can_end`` becomes ``OR = { AND = { <vanilla> } AND = { pp_disaster_relief_due_trigger (50 years)
  pp_disaster_relief_<disaster>_trigger } }``: vanilla's end trigger with its stability bar lowered (``RELIEF``),
  every other requirement kept. Those triggers are generated from vanilla's ``disaster_triggers.txt`` into
  ``pp_disaster_relief_triggers.txt``.
- ``on_end``: when vanilla's own condition does not hold (the relaxed branch ended it) the same disaster is blocked for
  25 years (``block_disaster_temporarily_effect``, read by ``pp_disaster_restart_allowed_trigger`` at the top of
  ``can_start``); vanilla's ``on_end`` runs unchanged (the reward stays); the pain modifiers go.

Hand-written: ``pp_disaster_triggers.txt``, ``pp_disaster_effects.txt``, ``pp_disaster_events.txt``,
``pp_disasters_l_english.yml``. Generated here: the copies, the relief triggers, the step modifiers
(``pp_disaster_modifiers.txt``) and their text (``pp_disaster_pain_l_english.yml``). ``tests/disaster_vanilla_pins.csv``
holds a hash of each vanilla file this pass reads (``ppc disasters pin``); a test fails when vanilla changes one.
"""

from __future__ import annotations

import csv
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

MOD_FOLDER = "pp"
DISASTERS = Path("in_game/common/disasters")
VANILLA_TRIGGERS = Path("in_game/common/scripted_triggers/disaster_triggers.txt")
RELIEF_TRIGGERS = Path("in_game/common/scripted_triggers/pp_disaster_relief_triggers.txt")
MODIFIERS = Path("main_menu/common/static_modifiers/pp_disaster_modifiers.txt")
LOC = Path("main_menu/localization/english/pp_disaster_pain_l_english.yml")
PINS_PATH = Path("tests") / "disaster_vanilla_pins.csv"
HEADER = ("# PP: written by `uv run ppc disasters apply` (src/prosper_or_perish_constructor/disaster_growing_pain.py); "
          "do not edit.")
MARK = "# PP: growing pain"

STEP_YEARS = (25, 30, 35, 40, 45)
RELIEF_YEARS = 50
RESTART_BLOCK_YEARS = 25

# ------------------------------------------------------------------------------------------------------- the scope

# Disasters vanilla already ends within 25 years: untouched (Jan, 2026-11-27).
EXEMPT: dict[str, str] = {
    "aspiration_for_liberty": "vanilla ends it after 20 years (aspiration_for_liberty_end_trigger)",
    "coup_attempt": "vanilla ends it after 5 years (coup_attempt_end_trigger, inconclusive ending)",
    "court_and_country": "vanilla ends it after 20 years (court_and_country_end_trigger); players only",
    "english_civil_war": "England / Great Britain only; vanilla ends it after 10 years once no civil war runs",
    "french_wars_religion": "France only; vanilla ends it after 25 years (french_wars_religion.14)",
    "revolutionary_chaos": "vanilla ends it after 10 years once no civil war runs",
    "time_of_troubles": "Russia / Muscovy only; vanilla ends it after 15 years (time_of_troubles_end_trigger)",
}

# Country-specific disasters: pure vanilla, no copy (Jan: "I'm fine if there's some historic reason for some country
# being stuck in some disaster").
VANILLA: dict[str, str] = {
    "ambrosian_republic_disaster": "Milan only (tag = MLO)",
    "byzantine_succession_crisis": "Byzantium only (tag = BYZ)",
    "castilian_civil_war": "Castile only (tag = CAS, Pedro I and the Trastamara bastards)",
    "ciompi_revolt": "Florence only (tag = FLO)",
    "crisis_of_the_chinese_dynasty": "the Middle Kingdom's leader only, with its celestial authority story",
    "crisis_of_the_sayfawa_dynasty": "Kanem-Bornu only (tag = KBO, Sayfawa dynasty)",
    "curse_of_stefan_uros_iii": "Serbia only (tag = SER)",
    "death_of_hayan_wuruk": "Majapahit only (tag = MAJ)",
    "decline_of_majapahit": "Majapahit only (tag = MAJ)",
    "decline_of_mali": "Mali only (tag = MAL)",
    "dissolution_of_delhi": "Delhi only (tag = DLH, fall_of_delhi situation)",
    "fate_of_the_phoenix": "Byzantium only (tag = BYZ, 1337 start)",
    "hook_and_cod_wars": "Holland only (tag = HOL)",
    "muscovite_succession_war": "Muscovy only (tag = MOS)",
    "reform_society": "Nahuatl religion only (the Aztec reform story)",
    "rise_of_the_szlachta": "Poland only (tag = POL / PLC)",
    "savonarola_disaster": "Florence only (has_or_had_tag = FLO)",
    "sinicization_disaster": "China's neighbours against China only (needs c:CHI and the sinicization value; ends "
                             "by its own event counters, no stability bar)",
    "struggle_for_royal_power": "Poland only (tag = POL / PLC)",
    "turmoil_in_brandenburg": "Brandenburg only (tag = BRA, Wittelsbach dynasty)",
    "twilight_of_the_tsardom": "Bulgaria only (tag = BUL, 1337 start)",
    "war_of_the_aragonese_union_disaster": "Aragon only (tag = ARA)",
    "war_of_the_roses": "England only (tag = ENG, York and Lancaster)",
}


@dataclass(frozen=True)
class Line:
    """One modifier line per step (five values, 25/30/35/40/45 years) and the vanilla value it is anchored on."""

    modifier: str
    steps: tuple[str, ...]
    anchor: str


def ramp(last: float) -> tuple[str, ...]:
    """Five even steps up to ``last`` at 45 years."""
    out = []
    for i in range(1, 6):
        value = round(last * i / 5, 4)
        text = f"{value:.4f}".rstrip("0").rstrip(".")
        out.append("0" if text in ("-0", "") else text)
    return tuple(out)


# Placeholders in CORE, expanded per disaster: "estate_target" (global, or per estate where an estate's satisfaction is
# an exit number), "government_power" (the five government-type lines minus exit ones), "rebels" (the disaster's own
# rebel kind, split evenly when it names more than one).
CORE: tuple[Line, ...] = (
    Line("estate_target", ("small_permanent_target_satisfaction_penalty", "medium_permanent_target_satisfaction_penalty",
                           "large_permanent_target_satisfaction_penalty", "larger_permanent_target_satisfaction_penalty",
                           "great_permanent_target_satisfaction_penalty"),
         "vanilla's permanent target satisfaction penalties -0.025 / -0.05 / -0.1 / -0.15 / -0.2 (great: "
         "byzantine_succession_crisis; large: ambrosian_republic_disaster)"),
    Line("global_crown_estate_power", ramp(-0.2), "-0.2 in succession_crisis, horde_civil_war, crisis_of_faith"),
    Line("government_power", ramp(-0.3),
         "monthly_legitimacy -0.3 in decline_of_empire; sinicization_disaster -0.25 on all five government lines"),
    Line("rebels", ramp(0.015),
         "monthly_rebel_growth 0.003 decline_of_empire .. 0.015 crisis_of_the_sayfawa_dynasty (0.02 dissolution_of_delhi)"),
    Line("global_separatism", ramp(0.1), "vanilla's -0.05 / -0.1 separatism bonuses, mirrored"),
    Line("subject_loyalty", ("-4", "-8", "-12", "-16", "-20"), "-10 horde_civil_war, death_of_hayan_wuruk; -20 vanilla"),
    Line("global_levy_size_modifier", ramp(-0.3), "global_manpower_modifier -0.3 in decline_of_empire"),
    Line("land_morale_modifier", ramp(-0.1), "-0.10 in decline_of_empire"),
    Line("discipline", ramp(-0.1), "-0.10 in decline_of_empire, horde_civil_war"),
    Line("tax_income_efficiency", ("-0.025", "-0.05", "-0.075", "-0.1", "-0.15"),
         "vanilla tax penalties small -0.025, medium -0.05, large -0.1, huge -0.2"),
)

GOVERNMENT_POWER = ("monthly_legitimacy", "monthly_republican_tradition", "monthly_devotion", "monthly_horde_unity",
                    "monthly_tribal_cohesion")
ESTATES = ("nobles", "clergy", "burghers", "peasants")

# Modifiers that would lower the stability any covered disaster's end asks for: never written.
STABILITY = ("stability_investment", "stability_decay", "stability_cost_efficiency", "harmony_stability")

# Every number a covered disaster's vanilla end trigger compares, and the modifiers that would push it the wrong way:
# none of them is written into that disaster's steps. A test reads every comparison in the end trigger and fails
# when one is missing here.
_CLERGY_SATISFACTION = ("clergy_estate_target_satisfaction", "global_estate_target_satisfaction",
                        "clergy_estate_satisfaction_decay", "global_estate_satisfaction_decay")
_PEASANTS_SATISFACTION = ("peasants_estate_target_satisfaction", "global_estate_target_satisfaction",
                          "peasants_estate_satisfaction_decay", "global_estate_satisfaction_decay")
EXIT_NUMBERS: dict[str, dict[str, tuple[str, ...]]] = {
    "religious_turmoil": {
        "religious_unity": ("global_pop_conversion_speed_modifier", "tolerance_heretic", "tolerance_heathen"),
        "societal_value:spiritualist_vs_humanist": ("monthly_towards_spiritualist", "monthly_towards_humanist"),
        "estate_satisfaction:clergy_estate": _CLERGY_SATISFACTION,
        "estate_power(estate_type:clergy_estate)": ("global_clergy_estate_power",),
        "stability": STABILITY,
    },
    "horde_civil_war": {
        "horde_unity": ("monthly_horde_unity", "horde_unity_hit_at_ruler_death"),
        "stability": STABILITY,
    },
    "succession_crisis": {
        "legitimacy": ("monthly_legitimacy",),
        "stability": STABILITY,
    },
    "crisis_of_faith": {
        "devotion": ("monthly_devotion",),
        "stability": STABILITY,
    },
    "oligarchic_capture": {
        "republican_tradition": ("monthly_republican_tradition",),
        "stability": STABILITY,
    },
    "decline_of_empire": {
        "years": (),
        "average_control_in_home_region": ("global_monthly_control", "global_max_control", "global_max_rural_control",
                                           "global_monthly_control_decline", "global_separatism"),
        "total_not_tolerated_culture_population": ("global_pop_assimilation_speed_modifier",),
        "stability": STABILITY,
    },
    "peasants_war": {
        "societal_value:serfdom_vs_free_subjects": ("monthly_towards_serfdom", "monthly_towards_free_subjects"),
        "estate_satisfaction:peasants_estate": _PEASANTS_SATISFACTION,
        "war_exhaustion_percentage": ("monthly_war_exhaustion",),
        "stability": STABILITY,
    },
    "revolution_disaster": {},
}


@dataclass(frozen=True)
class Covered:
    kind: str                       # who can get it (from vanilla's can_start)
    rebels: tuple[str, ...]         # the rebel growth that fits the story
    extra: tuple[Line, ...]         # story lines on top of CORE
    relief: tuple[str, str] | None  # (vanilla's stability clause, the relaxed one); None: no stability bar
    story: str                      # first sentence of the step modifiers' description
    # the government power lines its countries can have (GOVERNMENT_POWER when None); exit ones still go
    government: tuple[str, ...] | None = None


COVERED: dict[str, Covered] = {
    "religious_turmoil": Covered(
        "any Christian country but Orthodox, Miaphysite and France, not a subject, in the age of reformation",
        ("monthly_religious_rebel_growth",),
        (Line("pop_join_rebel_threshold", ramp(0.1), "0.1 court_and_country, 0.05 english_civil_war"),),
        ("stability > 30", "stability >= 0"),
        "The quarrel over the true faith has divided the realm for a generation, and the faithful of every confession "
        "look to arms rather than to the crown.",
        ("monthly_legitimacy", "monthly_republican_tradition", "monthly_devotion")),  # Christian realms
    "horde_civil_war": Covered(
        "any independent steppe horde",
        ("monthly_pretender_rebel_growth",),
        (Line("global_manpower_modifier", ramp(-0.3), "-0.3 in decline_of_empire"),),
        ("stability > HORDE_CIVIL_WAR_END_STABILITY", "stability >= 0"),
        "The clans have fought over the throne for a generation, and every pretender finds riders willing to follow "
        "him.",
        ("monthly_horde_unity",)),
    "succession_crisis": Covered(
        "any monarchy (a few tags only wait for a date)",
        ("monthly_pretender_rebel_growth",),
        (Line("country_cabinet_efficiency", ramp(-0.2), "-0.2 in decline_of_empire, coup_attempt"),),
        ("stability > 25", "stability >= 0"),
        "The quarrel over the succession has dragged on for a generation, and every pretender finds lords willing to "
        "back him.",
        ("monthly_legitimacy",)),
    "crisis_of_faith": Covered(
        "any theocracy but the Papacy",
        ("monthly_clergy_estate_rebel_growth",),
        (Line("monthly_religious_influence", ramp(-0.2), "-0.20 in crisis_of_faith itself"),),
        ("stability > 25", "stability >= 0"),
        "The crisis of faith has divided the clergy for a generation, and schismatic preachers win more followers every "
        "year.",
        ("monthly_devotion",)),
    "oligarchic_capture": Covered(
        "any republic that is not revolutionary",
        ("monthly_nobles_estate_rebel_growth", "monthly_burghers_estate_rebel_growth"),
        (Line("legislative_efficiency", ramp(-0.2), "-0.20 in oligarchic_capture itself"),),
        ("stability > 25", "stability >= 0"),
        "A narrow circle of great families has held the republic in its grip for a generation, and they arm their "
        "followers.",
        ("monthly_republican_tradition",)),
    "decline_of_empire": Covered(
        "any independent empire from the age of discovery",
        ("monthly_nationalist_rebel_growth",),
        (Line("monthly_prestige", ramp(-0.5), "-0.5 in decline_of_empire itself"),),
        # vanilla's bar is already 0: lowered a further 25 points
        ("stability > 0", "stability >= -25"),
        "The empire has been in decline for a generation, and its subject peoples dream of rulers of their own."),
    "peasants_war": Covered(
        "any monarchy or theocracy with a peasant estate, in the ages of discovery and reformation",
        ("monthly_peasants_estate_rebel_growth",),
        (Line("global_manpower_modifier", ramp(-0.3), "-0.3 in decline_of_empire"),),
        ("stability > 10", "stability >= 0"),
        "The peasants have risen again and again for a generation, and the countryside no longer obeys its lords.",
        ("monthly_legitimacy", "monthly_devotion")),
    "revolution_disaster": Covered(
        "any country with the Enlightenment in the age of revolutions",
        ("monthly_burghers_estate_rebel_growth",),
        (Line("pop_join_rebel_threshold", ramp(0.1), "0.1 court_and_country, 0.05 english_civil_war"),),
        None,  # its end asks for no stability: the revolutionaries win or are beaten
        "The revolutionary fever has burned for a generation, and the towns are full of people who want the old order "
        "gone.",
        ("monthly_legitimacy", "monthly_republican_tradition", "monthly_devotion")),  # no hordes, no tribes
}

STEP_NAMES = ("A Lingering Crisis", "A Deepening Crisis", "A Festering Crisis", "Authority Crumbles", "A Weary Realm")
STEP_TEXTS = (
    "The estates lose patience with the crown, the tax collectors bring back less, the levies thin out and rebels find "
    "willing followers.",
    "The crisis deepens. Each season the court's hold weakens, and the provinces listen to it less.",
    "Rebels grow bolder, our subjects drift away and our neighbours take note of our weakness.",
    "The crown's authority crumbles. Our armies have lost heart, our treasury runs thin and rival powers smell blood.",
    "The realm is worn out by the endless crisis and stays this weak for as long as it lasts.",
)
RELIEF_TEXT = (" Before long even its fiercest partisans will be tired of the struggle, and it can be ended with less "
               "stability than usual.")


class DisasterError(ValueError):
    pass


def forbidden(key: str) -> set[str]:
    out = set(STABILITY)
    for modifiers in EXIT_NUMBERS[key].values():
        out.update(modifiers)
    return out


def step_lines(key: str) -> list[tuple[str, tuple[str, ...]]]:
    """(modifier, five step values) for a covered disaster, exit lines left out."""
    spec = COVERED[key]
    banned = forbidden(key)
    out: list[tuple[str, tuple[str, ...]]] = []
    for line in (*CORE, *spec.extra):
        if line.modifier == "estate_target":
            if "global_estate_target_satisfaction" not in banned:
                out.append(("global_estate_target_satisfaction", line.steps))
            else:
                out.extend((f"{e}_estate_target_satisfaction", line.steps) for e in ESTATES
                           if f"{e}_estate_target_satisfaction" not in banned)
        elif line.modifier == "government_power":
            out.extend((m, line.steps) for m in (spec.government or GOVERNMENT_POWER) if m not in banned)
        elif line.modifier == "rebels":
            n = len(spec.rebels)
            steps = line.steps if n == 1 else ramp(round(float(line.steps[-1]) / n, 4))
            out.extend((m, steps) for m in spec.rebels if m not in banned)
        elif line.modifier not in banned:
            out.append((line.modifier, line.steps))
    return out


def modifier_name(key: str, step: int) -> str:
    return f"pp_disaster_pain_{key}_{step}"


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


def _norm(text: str) -> str:
    return " ".join(re.sub(r"#[^\n]*", "", text).split())


# ------------------------------------------------------------------------------------------------- relief triggers

def end_trigger_name(name: str, text: str) -> str:
    """The scripted trigger a covered disaster's can_end calls (vanilla: exactly ``<trigger> = yes``)."""
    mask = _code_mask(text)
    (top,) = _blocks(text, 0, len(text), mask)
    can_end = _one(_blocks(text, top.open + 1, top.close, mask), "can_end", name)
    if can_end is None:
        raise DisasterError(f"{name}: no can_end")
    m = re.fullmatch(r"([A-Za-z0-9_]+) = yes", _norm(text[can_end.open + 1:can_end.close]))
    if not m:
        raise DisasterError(f"{name}: can_end is not one scripted trigger (review RELIEF)")
    return m.group(1)


def trigger_blocks(text: str) -> dict[str, tuple[Block, str]]:
    mask = _code_mask(text)
    return {b.key: (b, text[b.open + 1:b.close]) for b in _blocks(text, 0, len(text), mask)}


def _clause_pattern(clause: str) -> re.Pattern[str]:
    lhs, op, rhs = clause.split()
    return re.compile(rf"(?<![A-Za-z0-9_.:]){re.escape(lhs)}[ \t]*{re.escape(op)}[ \t]*{re.escape(rhs)}(?![A-Za-z0-9_.])")


def relaxed_body(key: str, body: str) -> str:
    old, new = COVERED[key].relief  # type: ignore[misc]
    mask = _code_mask(body)
    hits = [m for m in _clause_pattern(old).finditer(body) if all(mask[i] for i in range(m.start(), m.end()))]
    if len(hits) != 1:
        raise DisasterError(f"{key}: vanilla's end trigger has {len(hits)} `{old}` clauses, expected one (review RELIEF)")
    m = hits[0]
    return body[:m.start()] + new + body[m.end():]


def relief_triggers(game_root: Path, files: dict[str, Path]) -> str:
    triggers = trigger_blocks((Path(game_root) / VANILLA_TRIGGERS).read_text(encoding="utf-8-sig"))
    parts = [HEADER, "# Vanilla's end triggers of the covered disasters with the stability bar lowered (AGENTS.md "
                     "\"Long Disasters: Growing Pain\"). A disaster's can_end takes this from 50 years on.", ""]
    for key in sorted(COVERED):
        spec = COVERED[key]
        if spec.relief is None:
            continue
        path = files[key]
        name = end_trigger_name(path.name, path.read_text(encoding="utf-8-sig"))
        if name not in triggers:
            raise DisasterError(f"{key}: {name} is not in {VANILLA_TRIGGERS.name}")
        body = relaxed_body(key, triggers[name][1].replace("\r\n", "\n"))
        parts.append(f"# {key}: {name}, `{spec.relief[0]}` -> `{spec.relief[1]}`")
        parts.append(f"pp_disaster_relief_{key}_trigger = {{{body}}}")
        parts.append("")
    return "\n".join(parts)


# ------------------------------------------------------------------------------------------------- modifiers + text

def modifiers_text() -> str:
    parts = [HEADER, "# One modifier per step of a long disaster (25, 30, 35, 40, 45 years), swapped by "
                     "pp_disaster_pain_effect from the disaster's on_monthly. Lines and anchors: COVERED / CORE in the "
                     "module.", ""]
    for key in sorted(COVERED):
        lines = step_lines(key)
        for step in range(1, 6):
            parts.append(f"{modifier_name(key, step)} = {{")
            parts.append("\tgame_data = {")
            parts.append("\t\tcategory = country")
            parts.append("\t}")
            parts.extend(f"\t{m} = {steps[step - 1]}" for m, steps in lines)
            parts.append("}")
            parts.append("")
    return "\n".join(parts)


def loc_entries() -> dict[str, str]:
    out: dict[str, str] = {}
    for key in sorted(COVERED):
        spec = COVERED[key]
        for step in range(1, 6):
            name = modifier_name(key, step)
            desc = f"{spec.story} {STEP_TEXTS[step - 1]}"
            if step == 5 and spec.relief is not None:
                desc += RELIEF_TEXT
            out[f"STATIC_MODIFIER_NAME_{name}"] = STEP_NAMES[step - 1]
            out[f"STATIC_MODIFIER_DESC_{name}"] = desc
    return out


def loc_text() -> str:
    lines = ["﻿l_english:"]
    lines.extend(f" {k}: \"{v}\"" for k, v in loc_entries().items())
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------------------------------------------- the copy

def rewrite(name: str, text: str) -> tuple[str, str]:
    """(disaster key, the copy's text) for a covered vanilla disaster file's text (BOM stripped)."""
    nl = "\r\n" if "\r\n" in text else "\n"
    mask = _code_mask(text)
    top = _blocks(text, 0, len(text), mask)
    if len(top) != 1:
        raise DisasterError(f"{name}: {len(top)} top-level blocks, expected one disaster")
    disaster = top[0]
    key = disaster.key
    spec = COVERED.get(key)
    if spec is None:
        raise DisasterError(f"{name}: {key} is not a covered disaster")
    inner = _blocks(text, disaster.open + 1, disaster.close, mask)
    where = f"{name} ({key})"
    can_start = _one(inner, "can_start", where)
    can_end = _one(inner, "can_end", where)
    on_monthly = _one(inner, "on_monthly", where)
    on_end = _one(inner, "on_end", where)
    if None in (can_start, can_end, on_monthly, on_end):
        raise DisasterError(f"{where}: expected can_start, can_end, on_monthly and on_end")
    assert can_start and can_end and on_monthly and on_end
    t = f"type = {key}"
    edits: list[tuple[int, int, str]] = []   # (start, end, replacement), applied from the back
    relief = spec.relief is not None
    if relief:
        # no restart while the block set by a relieved ending runs
        edits.append((can_start.open + 1, can_start.open + 1,
                      f"{nl}\t\tpp_disaster_restart_allowed_trigger = {{ {t} }} {MARK}{nl}"))
    # the steps, from the disaster's own on_monthly
    calls = f"\t\tpp_disaster_pain_effect = {{ {t} }}{nl}"
    if relief:
        calls += f"\t\tpp_disaster_relief_notice_effect = {{ {t} }}{nl}"
    edits.append((on_monthly.close, on_monthly.close, f"\t{MARK}{nl}{calls}\t"))
    vanilla_end = text[can_end.open + 1:can_end.close]
    if relief:
        edits.append((can_end.open, can_end.close + 1, (
            f"{{ {MARK}: vanilla's way out, or from {RELIEF_YEARS} years the same with less stability{nl}"
            f"\t\tOR = {{{nl}\t\t\tAND = {{{vanilla_end}}}{nl}"
            f"\t\t\tAND = {{{nl}"
            f"\t\t\t\tpp_disaster_relief_due_trigger = {{ {t} }}{nl}"
            f"\t\t\t\tpp_disaster_relief_{key}_trigger = yes{nl}"
            f"\t\t\t}}{nl}\t\t}}{nl}\t}}")))
    body = text[on_end.open + 1:on_end.close]
    head = ""
    if relief:
        head = (f"{nl}\t\t{MARK}: ended by the relaxed branch: no restart for a while{nl}"
                f"\t\tif = {{{nl}"
                f"\t\t\tlimit = {{ NOT = {{ AND = {{{vanilla_end}}} }} }}{nl}"
                f"\t\t\tpp_disaster_restart_block_effect = {{ {t} }}{nl}"
                f"\t\t}}")
    edits.append((on_end.open + 1, on_end.close, (
        f"{head}{body}\t{MARK}{nl}\t\tpp_disaster_pain_clear_effect = {{ {t} }}{nl}\t")))
    out = text
    for start, end, new in sorted(edits, key=lambda e: e[0], reverse=True):
        out = out[:start] + new + out[end:]
    return key, f"{HEADER}{nl}{out}"


# ------------------------------------------------------------------------------------------------------- the pass

@dataclass
class Copy:
    name: str          # file name
    key: str           # disaster key
    data: bytes


@dataclass
class Result:
    copies: list[Copy] = field(default_factory=list)
    generated: dict[Path, bytes] = field(default_factory=dict)
    exempt: list[str] = field(default_factory=list)
    vanilla: list[str] = field(default_factory=list)
    changed: list[Path] = field(default_factory=list)
    removed: list[Path] = field(default_factory=list)


def vanilla_files(game_root: Path) -> list[Path]:
    folder = Path(game_root) / DISASTERS
    return sorted(p for p in folder.glob("*.txt") if p.name != "readme.txt")


def disaster_key(path: Path) -> str:
    text = path.read_text(encoding="utf-8-sig")
    top = _blocks(text, 0, len(text), _code_mask(text))
    if len(top) != 1:
        raise DisasterError(f"{path.name}: {len(top)} top-level blocks")
    return top[0].key


def classify(keys: set[str]) -> None:
    classes = (set(COVERED), set(EXEMPT), set(VANILLA))
    for i, a in enumerate(classes):
        for b in classes[i + 1:]:
            if a & b:
                raise DisasterError(f"disasters in two classes: {', '.join(sorted(a & b))}")
    known = set().union(*classes)
    if keys - known:
        raise DisasterError(f"vanilla disasters without a class (COVERED / EXEMPT / VANILLA): "
                            f"{', '.join(sorted(keys - known))}")
    if known - keys:
        raise DisasterError(f"classes for disasters vanilla no longer has: {', '.join(sorted(known - keys))}")
    if set(EXIT_NUMBERS) != set(COVERED):
        raise DisasterError("EXIT_NUMBERS must list exactly the covered disasters")


def plan(game_root: Path) -> Result:
    result = Result()
    files = vanilla_files(game_root)
    if not files:
        raise DisasterError(f"{game_root}: no vanilla disasters")
    keys = {disaster_key(p): p for p in files}
    classify(set(keys))
    for key, path in sorted(keys.items(), key=lambda kv: kv[1].name):
        if key in EXEMPT:
            result.exempt.append(key)
            continue
        if key in VANILLA:
            result.vanilla.append(key)
            continue
        raw = path.read_bytes()
        bom = raw.startswith(b"\xef\xbb\xbf")
        _, copy = rewrite(path.name, raw.decode("utf-8-sig"))
        result.copies.append(Copy(path.name, key, (b"\xef\xbb\xbf" if bom else b"") + copy.encode("utf-8")))
    covered_files = {k: p for k, p in keys.items() if k in COVERED}
    bom = b"\xef\xbb\xbf"
    result.generated[RELIEF_TRIGGERS] = bom + relief_triggers(game_root, covered_files).encode("utf-8")
    result.generated[MODIFIERS] = bom + modifiers_text().encode("utf-8")
    result.generated[LOC] = loc_text().encode("utf-8")
    return result


def _game_root(repo: Path, project: Path, vanilla_root: Path | None) -> Path:
    from prosper_or_perish_constructor.cap_tooltips import game_root
    from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root as configured

    return game_root(Path(vanilla_root) if vanilla_root is not None else configured(repo, project))


def apply(repo: Path, project: Path, mod_root: Path | None = None, vanilla_root: Path | None = None, *,
          write: bool = True) -> Result:
    """Write (or with ``write=False`` only compare) the copies and generated files; other disaster copies go."""
    repo = Path(repo)
    mod_root = Path(mod_root) if mod_root is not None else repo / "mod" / MOD_FOLDER
    result = plan(_game_root(repo, project, vanilla_root))
    folder = mod_root / DISASTERS
    wanted = {c.name for c in result.copies}
    targets = {DISASTERS / c.name: c.data for c in result.copies} | result.generated
    for rel, data in targets.items():
        path = mod_root / rel
        if not path.is_file() or path.read_bytes() != data:
            result.changed.append(rel)
            if write:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
    for path in sorted(folder.glob("*.txt")) if folder.is_dir() else ():
        if path.name not in wanted:
            result.removed.append(DISASTERS / path.name)
            if write:
                path.unlink()
    return result


# ------------------------------------------------------------------------------------------------------------ pins

def file_hash(path: Path) -> str:
    """Hash of a vanilla file's text (BOM and line endings ignored)."""
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def current_pins(game_root: Path) -> dict[str, str]:
    """The vanilla files this pass reads: the covered disasters and disaster_triggers.txt."""
    pins = {p.name: file_hash(p) for p in vanilla_files(game_root) if disaster_key(p) in COVERED}
    pins[VANILLA_TRIGGERS.name] = file_hash(Path(game_root) / VANILLA_TRIGGERS)
    return pins


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
    return (f"Long disasters, growing pain: {len(result.copies)} general disasters copied with the steps and the relief "
            f"at {RELIEF_YEARS} years, {len(result.vanilla)} country-specific and {len(result.exempt)} short ones left "
            f"vanilla; {state}.")
