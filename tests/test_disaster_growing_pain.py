"""Long disasters: growing pain (2026-11-27, Jan; AGENTS.md "Long Disasters: Growing Pain").

Every vanilla disaster is covered (general: a same-path copy with the steps from 25 years, the relaxed end from 50 and
the restart block), country-specific (pure vanilla) or exempt (vanilla ends it within 25 years). The copies are
vanilla's text plus the inserted lines; a game update that changes a vanilla file this pass reads fails here until its
class, can_end and ``EXIT_NUMBERS`` are reviewed, the copies rewritten (``ppc disasters apply``) and the pins recorded
(``ppc disasters pin``).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from eu5gameparser.load_order import LoadOrderConfig

from prosper_or_perish_constructor import disaster_growing_pain as dgp

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mod" / "pp"
COPIES = MOD / dgp.DISASTERS
EFFECTS = MOD / "in_game/common/scripted_effects/pp_disaster_effects.txt"
TRIGGERS = MOD / "in_game/common/scripted_triggers/pp_disaster_triggers.txt"
EVENTS = MOD / "in_game/events/pp_disaster_events.txt"
LOC = MOD / "main_menu/localization/english/pp_disasters_l_english.yml"
PP_FILES = (EFFECTS, TRIGGERS, EVENTS, MOD / dgp.RELIEF_TRIGGERS, MOD / dgp.MODIFIERS)


@pytest.fixture(scope="module")
def game() -> Path:
    return LoadOrderConfig.load(ROOT / "constructor.load_order.toml").vanilla_root / "game"


def _norm(text: str) -> str:
    return " ".join(re.sub(r"#[^\n]*", "", text).split())


def _parts(text: str) -> tuple[str, dict[str, list[dgp.Block]], dgp.Block]:
    mask = dgp._code_mask(text)
    (disaster,) = dgp._blocks(text, 0, len(text), mask)
    inner: dict[str, list[dgp.Block]] = {}
    for block in dgp._blocks(text, disaster.open + 1, disaster.close, mask):
        inner.setdefault(block.key, []).append(block)
    return disaster.key, inner, disaster


def _body(text: str, block: dgp.Block) -> str:
    return _norm(text[block.open + 1:block.close])


def _outside(text: str, inner: dict[str, list[dgp.Block]], disaster: dgp.Block, keys: set[str]) -> str:
    """The disaster's text with the named blocks cut out."""
    cuts = sorted((b.start, b.close + 1) for k in keys for b in inner.get(k, ()))
    out, pos = [], disaster.open + 1
    for start, end in cuts:
        out.append(text[pos:start])
        pos = end
    out.append(text[pos:disaster.close])
    return _norm("".join(out))


def _vanilla(game: Path) -> dict[str, Path]:
    return {dgp.disaster_key(p): p for p in dgp.vanilla_files(game)}


def _end_trigger(game: Path, key: str) -> str:
    """The body of the scripted trigger a covered disaster's vanilla can_end calls."""
    path = _vanilla(game)[key]
    name = dgp.end_trigger_name(path.name, path.read_text(encoding="utf-8-sig"))
    triggers = dgp.trigger_blocks((game / dgp.VANILLA_TRIGGERS).read_text(encoding="utf-8-sig"))
    return triggers[name][1]


def _modifiers(text: str) -> dict[str, dict[str, str]]:
    mask = dgp._code_mask(text)
    out: dict[str, dict[str, str]] = {}
    for block in dgp._blocks(text, 0, len(text), mask):
        body = text[block.open + 1:block.close]
        body = re.sub(r"game_data\s*=\s*\{[^}]*\}", "", body)
        out[block.key] = dict(re.findall(r"([A-Za-z0-9_]+)\s*=\s*([^\s{}]+)", re.sub(r"#[^\n]*", "", body)))
    return out


# ---------------------------------------------------------------------------------------------------------- scope

def test_every_vanilla_disaster_has_one_class_with_a_reason(game) -> None:
    keys = set(_vanilla(game))
    assert keys, "no vanilla disasters"
    dgp.classify(keys)
    assert all(spec.kind.strip() and spec.story.strip() for spec in dgp.COVERED.values())
    assert all(why.strip() for why in (*dgp.EXEMPT.values(), *dgp.VANILLA.values()))
    # Jan, 2026-11-27: religious turmoil and the horde civil war are in for sure; the national stories are not
    assert {"religious_turmoil", "horde_civil_war"} <= set(dgp.COVERED)
    for key in ("crisis_of_the_chinese_dynasty", "decline_of_majapahit", "crisis_of_the_sayfawa_dynasty",
                "twilight_of_the_tsardom", "fate_of_the_phoenix", "rise_of_the_szlachta", "reform_society",
                "ciompi_revolt", "decline_of_mali", "turmoil_in_brandenburg"):
        assert key in dgp.VANILLA, key
    # a DLC that adds or replaces disasters needs this pass to read it
    for dlc in sorted((game / "dlc").glob("*")):
        assert not (dlc / dgp.DISASTERS).is_dir(), dlc.name


def test_covered_disasters_name_no_tag_or_culture(game) -> None:
    """A covered disaster's start names no single country, culture or national story; a tag in it only moves a date
    (succession_crisis) or keeps one country out (religious_turmoil: France has its own)."""
    allowed = {"religious_turmoil": {"FRA"}, "succession_crisis": {"HOL", "BYZ", "CHI"}, "crisis_of_faith": {"PAP"},
               "revolution_disaster": {"PAP"}}
    triggers = dgp.trigger_blocks((game / dgp.VANILLA_TRIGGERS).read_text(encoding="utf-8-sig"))
    for key in dgp.COVERED:
        text = _vanilla(game)[key].read_text(encoding="utf-8-sig")
        _, inner, _ = _parts(text)
        start = _body(text, inner["can_start"][0])
        for called in re.findall(r"([a-z0-9_]+_trigger) = yes", start):
            if called in triggers:
                start += " " + _norm(triggers[called][1])
        tags = set(re.findall(r"tag = ([A-Z]{3})", start))
        assert tags <= allowed.get(key, set()), (key, tags)
        assert "culture = culture:" not in start and "dynasty:" not in start, key


def test_exempt_disasters_end_on_their_own_within_25_years(game) -> None:
    triggers = (game / dgp.VANILLA_TRIGGERS).read_text(encoding="utf-8-sig")
    for key in dgp.EXEMPT:
        start = triggers.find(f"{key}_end_trigger = {{")
        assert start >= 0, key
        years = re.findall(rf"disaster_type = (?:disaster_type:{key}|scope:disaster)\s+years\s*>=?\s*(\d+)", triggers[start:])
        assert years and int(years[0]) <= 25, key


# ---------------------------------------------------------------------------------------------------------- copies

def test_copies_are_current_and_vanilla_is_the_reviewed_one(game) -> None:
    result = dgp.apply(ROOT, ROOT / "constructor.toml", MOD, game.parent, write=False)
    assert not result.changed and not result.removed, "run uv run ppc disasters apply"
    assert dgp.read_pins(ROOT) == dgp.current_pins(game), (
        "a vanilla disaster file changed: review its class, can_end and EXIT_NUMBERS, then ppc disasters apply and pin")
    names = {p.name for p in COPIES.glob("*.txt")}
    assert names == {p.name for k, p in _vanilla(game).items() if k in dgp.COVERED}, "only general disasters are copied"


def test_each_copy_is_vanilla_with_the_rule_added(game) -> None:
    for key, source in _vanilla(game).items():
        if key not in dgp.COVERED:
            continue
        relief = dgp.COVERED[key].relief is not None
        vtext = source.read_text(encoding="utf-8-sig")
        ctext = (COPIES / source.name).read_text(encoding="utf-8-sig")
        vkey, vin, vdis = _parts(vtext)
        ckey, cin, cdis = _parts(ctext)
        assert vkey == ckey == key
        t = f"type = {key}"
        blocks = {"can_start", "can_end", "on_monthly", "on_end"}
        assert _outside(ctext, cin, cdis, blocks) == _outside(vtext, vin, vdis, blocks), key
        vstart, cstart = _body(vtext, vin["can_start"][0]), _body(ctext, cin["can_start"][0])
        vend = _body(vtext, vin["can_end"][0])
        vbody = _body(vtext, vin["on_end"][0])
        monthly = f" pp_disaster_pain_effect = {{ {t} }}"
        if relief:
            # restart block
            assert cstart == f"pp_disaster_restart_allowed_trigger = {{ {t} }} {vstart}", key
            monthly += f" pp_disaster_relief_notice_effect = {{ {t} }}"
            # vanilla's way out, or from 50 years the relaxed one
            assert _body(ctext, cin["can_end"][0]) == (
                f"OR = {{ AND = {{ {vend} }} AND = {{ pp_disaster_relief_due_trigger = {{ {t} }} "
                f"pp_disaster_relief_{key}_trigger = yes }} }}"), key
            head = f"if = {{ limit = {{ NOT = {{ AND = {{ {vend} }} }} }} pp_disaster_restart_block_effect = {{ {t} }} }} "
        else:
            assert cstart == vstart and _body(ctext, cin["can_end"][0]) == vend, key
            head = ""
        # the steps, from the disaster's own on_monthly
        assert _body(ctext, cin["on_monthly"][0]) == _body(vtext, vin["on_monthly"][0]) + monthly, key
        # vanilla's on_end unchanged (the reward stays), the pain goes
        # (a disaster without a relaxed end has no relief variable: it clears only its step modifiers)
        clear = "pp_disaster_pain_clear_effect" if head else "pp_disaster_pain_clear_modifiers_effect"
        assert _body(ctext, cin["on_end"][0]) == f"{head}{vbody} {clear} = {{ {t} }}", key


def test_relaxed_end_is_vanilla_with_a_lower_stability_bar(game) -> None:
    text = (MOD / dgp.RELIEF_TRIGGERS).read_text(encoding="utf-8-sig")
    pp = dgp.trigger_blocks(text)
    relieved = {k for k, s in dgp.COVERED.items() if s.relief is not None}
    assert set(pp) == {f"pp_disaster_relief_{k}_trigger" for k in relieved}
    for key in relieved:
        old, new = dgp.COVERED[key].relief
        vanilla = _norm(_end_trigger(game, key))
        relaxed = _norm(pp[f"pp_disaster_relief_{key}_trigger"][1])
        assert vanilla.count(old) == 1 and old not in relaxed, key
        assert relaxed == vanilla.replace(old, new), key
        bar = int(new.split()[-1])
        assert bar <= 0, key
        vbar = old.split()[-1]
        if vbar.lstrip("-").isdigit():
            assert bar < int(vbar), key
    triggers = _norm(TRIGGERS.read_text(encoding="utf-8-sig"))
    assert ("pp_disaster_relief_due_trigger = { had_disaster_for_years = { disaster_type = disaster_type:$type$ "
            f"years >= {dgp.RELIEF_YEARS} }} }}") in triggers
    assert "pp_disaster_restart_allowed_trigger = { NOT = { has_blocked_disaster_trigger = { type = $type$ } } }" in triggers
    effects = _norm(EFFECTS.read_text(encoding="utf-8-sig"))
    assert (f"block_disaster_temporarily_effect = {{ type = $type$ years = {dgp.RESTART_BLOCK_YEARS} "
            f"years_in_days = {dgp.RESTART_BLOCK_YEARS * 365} }}") in effects
    # the relief needs a stability bar to lower; a covered disaster without one says so
    for key, spec in dgp.COVERED.items():
        if spec.relief is None:
            assert not re.search(r"(?<![a-z_])stability\s*[<>]", _end_trigger(game, key)), key


# ------------------------------------------------------------------------------------------------------- the steps

def test_steps_rise_and_stay(game) -> None:
    effects = _norm(EFFECTS.read_text(encoding="utf-8-sig"))
    for step, years in enumerate(dgp.STEP_YEARS, start=1):
        event = 1 if step == 1 else 2
        assert (f"limit = {{ had_disaster_for_years = {{ disaster_type = disaster_type:$type$ years >= {years} }} }} "
                f"if = {{ limit = {{ NOT = {{ has_country_modifier = pp_disaster_pain_$type$_{step} }} }} "
                f"pp_disaster_pain_clear_modifiers_effect = {{ type = $type$ }} add_country_modifier = {{ modifier = "
                f"pp_disaster_pain_$type$_{step} years = -1 }} trigger_event_silently = pp_disaster.{event} }}") in effects
    # highest step first: the last step stays for as long as the disaster runs, nothing ends it by time
    order = [effects.find(f"years >= {y} }} }} if") for y in reversed(dgp.STEP_YEARS)]
    assert all(i >= 0 for i in order) and order == sorted(order)
    assert "end_disaster" not in effects and "pp_disaster.10" not in effects
    modifiers = _modifiers((MOD / dgp.MODIFIERS).read_text(encoding="utf-8-sig"))
    values = _script_values(game)
    for key in dgp.COVERED:
        steps = [modifiers[dgp.modifier_name(key, s)] for s in range(1, 6)]
        assert all(s.keys() == steps[0].keys() and s for s in steps), key
        for line in steps[0]:
            numbers = [float(values.get(s[line], s[line])) for s in steps]
            assert all(abs(b) > abs(a) for a, b in zip(numbers, numbers[1:])), (key, line, numbers)
            assert all((n < 0) == (numbers[0] < 0) for n in numbers), (key, line)


def _script_values(game: Path) -> dict[str, str]:
    text = (game / "main_menu/common/script_values/default_values.txt").read_text(encoding="utf-8-sig")
    return dict(re.findall(r"^([a-z_]+)\s*=\s*(-?[0-9.]+)", text, re.M))


def test_no_step_line_touches_an_exit_number(game) -> None:
    """Every number a covered disaster's end compares has an entry in EXIT_NUMBERS; no step line pushes one of them."""
    comparison = re.compile(r'("[^"]*"|[A-Za-z_][A-Za-z0-9_:.]*)\s*(?:>=|<=|>|<)')
    modifiers = _modifiers((MOD / dgp.MODIFIERS).read_text(encoding="utf-8-sig"))
    for key in dgp.COVERED:
        compared = {m.strip('"') for m in comparison.findall(re.sub(r"#[^\n]*", "", _end_trigger(game, key)))}
        assert compared == set(dgp.EXIT_NUMBERS[key]), (key, compared ^ set(dgp.EXIT_NUMBERS[key]))
        banned = dgp.forbidden(key)
        assert set(dgp.STABILITY) <= banned
        for step in range(1, 6):
            lines = set(modifiers[dgp.modifier_name(key, step)])
            assert not lines & banned, (key, step, lines & banned)
            assert not any("stability" in line for line in lines), key
    # religious turmoil: the clergy's satisfaction is an exit number, the other estates' is not
    turmoil = modifiers[dgp.modifier_name("religious_turmoil", 5)]
    assert "global_estate_target_satisfaction" not in turmoil and "clergy_estate_target_satisfaction" not in turmoil
    assert {"nobles_estate_target_satisfaction", "burghers_estate_target_satisfaction",
            "peasants_estate_target_satisfaction", "monthly_religious_rebel_growth"} <= set(turmoil)


def test_the_last_step_weakens_the_state_as_planned() -> None:
    """Jan, 2026-11-27: estates, crown power, legitimacy, rebels, subjects, levies, morale, discipline, a moderate tax
    loss; never bankruptcy as the normal outcome."""
    modifiers = _modifiers((MOD / dgp.MODIFIERS).read_text(encoding="utf-8-sig"))
    for key in dgp.COVERED:
        last = modifiers[dgp.modifier_name(key, 5)]
        assert last["global_crown_estate_power"] == "-0.2"
        assert last["global_levy_size_modifier"] == "-0.3"
        assert last["land_morale_modifier"] == "-0.1" and last["discipline"] == "-0.1"
        assert last["subject_loyalty"] == "-20"
        assert -0.15 <= float(last["tax_income_efficiency"]) < 0
        rebels = [float(v) for m, v in last.items() if m.endswith("rebel_growth")]
        assert rebels and abs(sum(rebels) - 0.015) < 1e-9, key
        assert any(m.endswith("target_satisfaction") for m in last), key


def test_every_modifier_name_exists_in_vanilla(game) -> None:
    defined: set[str] = set()
    for path in (game / "main_menu/common/modifier_type_definitions").glob("*.txt"):
        defined |= set(re.findall(r"^([a-z_]+)\s*=", path.read_text(encoding="utf-8-sig"), re.M))
    values = _script_values(game)
    modifiers = _modifiers((MOD / dgp.MODIFIERS).read_text(encoding="utf-8-sig"))
    assert set(modifiers) == {dgp.modifier_name(k, s) for k in dgp.COVERED for s in range(1, 6)}
    for name, lines in modifiers.items():
        for line, value in lines.items():
            assert line in defined, (name, line)
            assert re.fullmatch(r"-?[0-9.]+", value) or value in values, (name, line, value)


def test_no_argument_inside_a_quoted_value() -> None:
    """Tested in game 2026-11-27: a scripted trigger's $arg$ is not substituted inside a quoted value."""
    for path in (*PP_FILES, *COPIES.glob("*.txt")):
        assert not re.search(r'"[^"\n]*\$[^"\n]*"', path.read_text(encoding="utf-8-sig")), path.name


def test_no_pulse_of_its_own() -> None:
    """The steps run from each disaster's on_monthly, the cleanup from its on_end: no on_action, no timed event."""
    for path in (MOD / "in_game/common/on_action").rglob("*.txt"):
        assert "pp_disaster" not in path.read_text(encoding="utf-8-sig"), path.name
    events = EVENTS.read_text(encoding="utf-8-sig")
    for word in ("dynamic_historical_event", "mean_time_to_happen", "trigger_event", "days =", "immediate"):
        assert word not in events, word
    callers = {"pp_disaster_pain_effect", "pp_disaster_relief_notice_effect", "pp_disaster_pain_clear_effect",
               "pp_disaster_restart_block_effect"}
    for path in [*(MOD / "in_game").rglob("*.txt"), *(MOD / "main_menu/common").rglob("*.txt")]:
        if path.parent == COPIES or path == EFFECTS:
            continue
        text = _norm(path.read_text(encoding="utf-8-sig", errors="replace"))
        for name in callers:
            assert name not in text, (path.relative_to(MOD), name)


def test_the_old_breaking_point_is_gone() -> None:
    for path in [*(MOD / "in_game").rglob("*.txt"), *(MOD / "main_menu").rglob("*.yml"),
                 *(MOD / "main_menu/common").rglob("*.txt")]:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for word in ("pp_disaster_breaking_point", "pp_disaster_coming_to_head", "pp_disaster_band_",
                     "pp_disaster_breakaway", "pp_disaster.10"):
            assert word not in text, (path.relative_to(MOD), word)


def test_texts_exist_and_hold_no_numbers() -> None:
    keys: dict[str, str] = {}
    for path in (LOC, MOD / dgp.LOC):
        loc = path.read_text(encoding="utf-8-sig")
        assert loc.startswith("l_english:"), path.name
        keys |= dict(re.findall(r"^ ([A-Za-z0-9_.]+):\d* \"(.*)\"$", loc, re.M))
    events = EVENTS.read_text(encoding="utf-8-sig")
    used = set(re.findall(r"(?:title|desc|name|custom_tooltip) = (pp_disaster\.[0-9a-z_.]+)", events))
    used |= {f"STATIC_MODIFIER_{kind}_{dgp.modifier_name(k, s)}" for kind in ("NAME", "DESC") for k in dgp.COVERED
             for s in range(1, 6)}
    assert used <= set(keys), sorted(used - set(keys))
    for key, text in keys.items():
        assert not re.search(r"\d", re.sub(r"\[[^\]]*\]", "", text)), key
