"""Russia and Lithuania (2026-11-27, Jan: Russia rarely forms and "a super strong Ukraine" appears every time; a
targeted change, no general union rule).

In 13 full runs Russia never formed: Muscovy reached the 50 % in 6 and was stopped in 5 by the city of Vladimir alone,
held by Vladimir (VLR), a country in a personal union under Muscovy's own ruler. Kyiv grew into the largest East Slavic
state while Lithuania shrank. docs/country_finetunes.md "Russia and Lithuania".
"""

from __future__ import annotations

import re
from pathlib import Path

from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.serializer import render_value
from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.load_order import LoadOrderConfig

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mod" / "pp"
GAME = LoadOrderConfig.load(ROOT / "constructor.load_order.toml").vanilla_root / "game"
HELD = "owner ?= { OR = { this = root is_subject_of = root in_union_with = root } }"


def _block(path: Path, key: str) -> CList:
    blocks = [e.value for e in parse_file(path).entries if e.key == key]
    assert len(blocks) == 1, (path, key, len(blocks))
    return blocks[0]


def _flat(value) -> str:
    return " ".join(render_value(value).split())


def _raw(path: Path, key: str) -> str:
    """The block's text, comments dropped, whitespace collapsed (the parser reads ``a ?= {`` as an item and a ``?``
    entry, so blocks with ``?=`` are compared as text)."""
    text = re.sub(r"#[^\n]*", "", path.read_text(encoding="utf-8-sig"))
    match = re.search(rf"(?m)^{re.escape(key)}\s*=\s*\{{", text)
    assert match, (path, key)
    depth, i = 0, match.end() - 1
    for j in range(i, len(text)):
        depth += {"{": 1, "}": -1}.get(text[j], 0)
        if depth == 0:
            return " ".join(text[i:j + 1].split())
    raise AssertionError((path, key, "unbalanced"))


def _sub(block: str, key: str) -> str:
    """First ``key = { ... }`` inside a flattened block."""
    i = block.index(f" {key} = {{") + len(f" {key} = ")
    depth = 0
    for j in range(i, len(block)):
        depth += {"{": 1, "}": -1}.get(block[j], 0)
        if depth == 0:
            return block[i:j + 1]
    raise AssertionError(key)


def _drop(block: str, key: str) -> str:
    sub = _sub(block, key)
    return block.replace(f" {key} = {sub}", "", 1)


def _owns(allow: str) -> list[str]:
    return re.findall(r"\bowns = location:(\w+)", allow)


def _held_cities(allow: str) -> list[str]:
    return re.findall(rf"location:(\w+) = \{{ {re.escape(HELD)} \}}", allow)


FORMABLE = "in_game/common/formable_countries"
DECISIONS = "in_game/common/decisions"


def test_russia_counts_cities_held_by_subjects_and_union_partners() -> None:
    own = _raw(MOD / FORMABLE / "pp_formable_adjustments.txt", "TRY_REPLACE:RUS_f")
    old = _raw(GAME / FORMABLE / "00_formable_countries.txt", "RUS_f")
    assert _drop(own, "allow") == _drop(old, "allow")
    assert _owns(_sub(old, "allow")) == ["moscow", "novgorod", "tver", "vladimir"]
    assert _owns(_sub(own, "allow")) == ["moscow"]
    assert _held_cities(_sub(own, "allow")) == ["novgorod", "tver", "vladimir"]
    rest = lambda allow: re.sub(r"(owns = location:\w+|location:\w+ = \{ " + re.escape(HELD) + r" \})", "", allow).split()  # noqa: E731
    assert rest(_sub(own, "allow")) == rest(_sub(old, "allow")) == ["{", "is_subject", "=", "no", "}"]
    assert "annex" not in own and "subject" not in _sub(own, "form_effect")  # forming takes no partner's land


def test_tsardom_decision_reads_the_same_cities_the_same_way() -> None:
    own = _raw(MOD / DECISIONS / "pp_russia_decisions.txt", "TRY_REPLACE:rus_proclaim_tsardom_decision")
    old = _raw(GAME / DECISIONS / "flavor_decisions_rus.txt", "rus_proclaim_tsardom_decision")
    assert _drop(own, "allow") == _drop(old, "allow")
    assert _owns(_sub(old, "allow")) == ["moscow", "vladimir", "novgorod"]
    assert _owns(_sub(own, "allow")) == ["moscow"]
    assert _held_cities(_sub(own, "allow")) == ["vladimir", "novgorod"]
    rest = lambda allow: re.sub(r"(owns = location:\w+|location:\w+ = \{ " + re.escape(HELD) + r" \})", "", allow).split()  # noqa: E731
    assert rest(_sub(own, "allow")) == rest(_sub(old, "allow"))


def test_vladimir_starts_under_muscovys_ruler() -> None:
    """The decision's premise: vanilla's setup gives Vladimir Muscovy's ruler (a personal union at start)."""
    text = (GAME / "main_menu/setup/1337/10_countries.txt").read_text(encoding="utf-8-sig")
    rulers = {}
    for tag in ("MOS", "VLR"):
        body = text[re.search(rf"\n\t{tag} = \{{", text).end():]
        rulers[tag] = re.search(r"\bruler = (\w+)", body).group(1)
    assert rulers["MOS"] == rulers["VLR"] == "mos_ivan_i_danilovich_kalita_rurikovich"


def test_vladimir_patrimony_decision() -> None:
    d = _raw(MOD / DECISIONS / "pp_russia_decisions.txt", "pp_mos_vladimir_patrimony_decision")
    assert "tags = { MOS RUS }" in d and "only_once = yes" in d
    assert _sub(d, "potential") == "{ c:VLR ?= { in_union_with = root } }"
    allow = _sub(d, "allow")
    assert "c:VLR ?= { is_ai = yes is_junior_partner = yes at_war = no }" in allow
    assert "owns = location:moscow" in allow and "is_subject = no" in allow
    assert _sub(d, "effect") == "{ annex_country = { country = c:VLR } }"
    loc = (MOD / "main_menu/localization/english/pp_russia_decisions_l_english.yml").read_text(encoding="utf-8-sig")
    for key in ("title", "desc", "a"):
        assert f" pp_mos_vladimir_patrimony_decision.{key}:" in loc
    assert not re.search(r"\d", loc.replace("l_english", "")), "no numbers in player text"


def test_only_muscovy_and_russia_keep_russia_conquer_region() -> None:
    vanilla = (GAME / "in_game/common/on_action/_hardcoded.txt").read_text(encoding="utf-8-sig")
    assert re.search(r"region:russian_region = \{\s*every_country_with_capital_in_geography = \{\s*"
                     r"add_area_preference = russia_conquer_region", vanilla)
    actions = MOD / "in_game/common/on_action/pp_country_finetunes.txt"
    start = _raw(actions, "on_game_start")
    assert start.index("delay = { days = 1 }") < start.index("pp_russia_conquer_region_trim"), start
    trim = _raw(actions, "pp_russia_conquer_region_trim")
    assert "has_area_preference = russia_conquer_region" in trim
    assert "NOR = { tag = MOS tag = RUS }" in trim and "remove_area_preference = russia_conquer_region" in trim


def test_lithuania_ruthenia_preference_doubled_and_reaches_smolensk() -> None:
    own = _block(MOD / "in_game/common/area_preferences/pp_conquest_preferences.txt", "REPLACE:lithuania_conquer_ruthenia")
    old = _block(GAME / "in_game/common/area_preferences/conquest_preferences.txt", "lithuania_conquer_ruthenia")
    assert float(old.first("modifier")) == 5 and float(own.first("modifier")) == 10
    assert own.values("region") == old.values("region") == ["ruthenia_region"]
    assert own.values("area") == old.values("area") + ["smolensk_area"]
    setup = (GAME / "main_menu/setup/1337/25_area_preferences.txt").read_text(encoding="utf-8-sig")
    assert re.search(r"LIT = \{\s*area_preferences = \{[^}]*lithuania_conquer_ruthenia", setup)


def test_lithuania_aim_like_the_other_aims() -> None:
    score = _block(MOD / "in_game/common/ai_scripted_expansion_score/pp_lithuania_ruthenia.txt", "pp_lithuania_ruthenia_focus")
    target = _block(MOD / "in_game/common/ai_scripted_expansion_target/pp_lithuania_ruthenia.txt", "pp_lithuania_ruthenia_targets")
    assert _flat(score.first("attacker_potential")) == "{ tag = LIT }"
    assert float(score.first("score").first("add")) == 30
    assert "months_since_war >= 36" in _flat(target.first("attacker_potential"))
    assert float(target.first("score").values("add")[-1]) == 30
    for block in (score.first("target_trigger"), target.first("candidate_list")):
        text = _flat(block)
        assert "region = region:ruthenia_region" in text and "area = area:smolensk_area" in text


def test_hungary_go_east_retired_kiev_go_west_kept() -> None:
    for folder in ("in_game", "main_menu/localization/english"):
        for path in (MOD / folder).rglob("*"):
            if path.suffix in (".txt", ".yml"):
                text = path.read_text(encoding="utf-8-sig", errors="replace")
                body = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
                for name in ("pp_hungary_go_east", "pp_hungary_east_focus", "pp_hungary_east_targets"):
                    assert name not in body, (name, path.relative_to(MOD))
    finetunes = _raw(MOD / "in_game/common/on_action/pp_country_finetunes.txt", "pp_country_finetune_area_preferences")
    assert "c:KIE ?= { add_area_preference = pp_kiev_go_west }" in finetunes
    assert "c:HUN" not in finetunes
