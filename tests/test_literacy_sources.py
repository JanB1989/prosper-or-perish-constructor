"""Country-wide literacy sources (src/prosper_or_perish_constructor/literacy_sources.py, 2026-11-25, Jan).

A game update that adds a file with literacy lines to a scanned folder, changes an object this pass replaces, or drops
one of the briefed sources fails here with the names in the message.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from prosper_or_perish_constructor import literacy_sources as ls
from prosper_or_perish_constructor import start_technology as st
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

REPO = Path(__file__).resolve().parents[1]
PROJECT = REPO / "constructor.toml"
MOD = REPO / "mod" / ls.MOD_FOLDER

# The sources Jan's brief named (2026-11-25); each must still be cut.
BRIEFED = {
    "advances": {"written_alphabet", "printing_press_advance", "humanism", "innovativeness",
                 "scientific_revolution_advance", "enlightened_court", "free_thinkers"},
    "societal_values": {"traditionalist_vs_innovative"},
    "laws": {"education_masses_law", "education_elites_law", "press_law", "legal_code_law", "divine_cause_law",
             "keju_examination", "sect_school_law", "factory_working_conditions_law", "monastic_reformation_movement",
             "guru_har_krishan_guruship"},
    "government_reforms": {"the_education_act", "visionary_thinkers", "peasant_labor_rights_reform"},
    "estate_privileges": {"freedom_of_interpretation"},
    "religions": {"anglican", "bon", "catharism", "judaism", "lollardy", "mahayana", "orthodox", "sanjiao", "shinto",
                  "strigolniki", "tibetan_buddhism", "waldensian"},
    "religious_aspects": {"pietism", "sola_scriptura", "translated_bibles", "worship_odin_god"},
    "religious_schools": {"mula_sangh_school", "vaisheshika_school"},
}
UPPER = {"global_nobles_max_literacy", "global_burghers_max_literacy", "global_clergy_max_literacy"}


@pytest.fixture(scope="module")
def vanilla() -> Path:
    return vanilla_root(REPO, PROJECT)


@pytest.fixture(scope="module")
def rule() -> ls.Rule:
    return ls.load_rule(REPO)


@pytest.fixture(scope="module")
def result(rule: ls.Rule, vanilla: Path) -> ls.Result:
    return ls.plan(rule, vanilla, MOD)


def test_rule_gives_clean_numbers(rule: ls.Rule) -> None:
    cut = {v: rule.new_value("laws", "x", "global_peasants_max_literacy", v)
           for v in ("10", "5", "3", "2", "2.5", "1", "0", "-5")}
    assert cut == {"10": "4", "5": "2", "3": "1", "2": "1", "2.5": "1", "1": None, "0": None, "-5": None}
    speed = {v: rule.new_value("laws", "x", "global_monthly_literacy", v)
             for v in ("0.1", "0.05", "0.25", "0.33", "0.03", "0.02", "0.01", "0.005")}
    assert speed == {"0.1": "0.008", "0.05": "0.004", "0.25": "0.02", "0.33": "0.026", "0.03": "0.004",
                     "0.02": "0.004", "0.01": "0.004", "0.005": "0.002"}
    assert rule.new_value("laws", "x", "global_monthly_literacy", "-0.02") is None
    assert rule.new_value("laws", "x", "global_nobles_max_literacy", "10") is None
    assert rule.new_value("laws", "x", "local_max_literacy", "10") is None


def _scope(rule: ls.Rule, folder: str) -> ls.FolderScope:
    return rule.folders[folder]


def test_all_class_cap_goes_to_the_estates(rule: ls.Rule) -> None:
    """Jan, 2026-11-26: a positive all-class cap becomes the three estate caps at vanilla's value, added to an estate
    line the block already has; zero and negative caps stay for everyone."""
    assert rule.split_key == "global_max_literacy" and set(rule.split_into) == UPPER
    body = st.parse_statements("country_modifier = { global_max_literacy = 10 global_clergy_max_literacy = 5 a = 1 }"
                               " other_modifier = { global_max_literacy = -5 } potential = { global_max_literacy = 3 }")
    out, changes = ls.cut_statements(rule, _scope(rule, "laws"), "x", body)
    assert st.flat_text(out) == (
        "country_modifier = { global_nobles_max_literacy = 10 global_burghers_max_literacy = 10 "
        "global_clergy_max_literacy = 15 a = 1 } other_modifier = { global_max_literacy = -5 } "
        "potential = { global_max_literacy = 3 }")
    assert {(c.key, c.old, c.new) for c in changes} == {
        ("global_max_literacy", "10", ""), ("global_nobles_max_literacy", "", "10"),
        ("global_burghers_max_literacy", "", "10"), ("global_clergy_max_literacy", "5", "15")}


def test_written_alphabet_keeps_the_commoners_base(rule: ls.Rule, vanilla: Path) -> None:
    """Written Alphabet: 2 for everyone, 3 more for each estate (vanilla's 5 for the estates); the halved base rate."""
    assert rule.split_exceptions == {("advances", "written_alphabet"): (Decimal(2), Decimal(3))}
    body = ls.effective_objects(vanilla, MOD, st.ADVANCES_DIR)["written_alphabet"].body
    lines = {s.key: s.value for s in body if s.key and "literacy" in s.key}
    assert lines == {"global_max_literacy": "2", "global_nobles_max_literacy": "3", "global_clergy_max_literacy": "3",
                     "global_burghers_max_literacy": "3", "global_monthly_literacy": "0.002"}


def test_estates_start_closer_to_history(rule: ls.Rule, vanilla: Path) -> None:
    """Jan, 2026-11-26: Guilds 5 -> 20 for burghers, Improved Religious Organization 5 -> 20 for clergy."""
    advances = ls.effective_objects(vanilla, MOD, st.ADVANCES_DIR)
    assert [s.value for s in advances["guilds"].body if s.key == "global_burghers_max_literacy"] == ["20"]
    assert [s.value for s in advances["organized_religion"].body if s.key == "global_clergy_max_literacy"] == ["20"]


def test_no_positive_all_class_cap_is_left_in_scope(rule: ls.Rule, result: ls.Result, vanilla: Path) -> None:
    """Every cut object, as the game loads it now, gives a positive all-class cap only where an exception says so."""
    cut = {(c.folder, c.obj) for c, _ in result.changes}
    for folder, obj in cut:
        body = ls.effective_objects(vanilla, MOD, rule.folders[folder].path)[obj].body
        positive = [v for _b, k, v in ls.literacy_lines(body) if k == rule.split_key and Decimal(v) > 0]
        keep = rule.split_exceptions.get((folder, obj))
        assert positive == ([ls._number(keep[0])] if keep else []), (folder, obj, positive)


def test_local_caps_are_never_touched(rule: ls.Rule, result: ls.Result) -> None:
    assert not [k for k in rule.keys if k.startswith("local_") and "max_literacy" in k]
    assert {c.key for c, _ in result.changes} <= rule.keys | set(rule.split_into)
    # upper-class keys change only by the split or an explicit value
    explicit = {(f, o, k) for f, o, k in rule.values}
    for change, _ in result.changes:
        if change.key in UPPER and (change.folder, change.obj, change.key) not in explicit:
            assert Decimal(change.new) - Decimal(change.old or 0) > 0, change


def test_base_rate_is_explicit_and_halved(rule: ls.Rule, vanilla: Path) -> None:
    """Jan, 2026-11-25: the base rate of literacy (Written Alphabet, Educated Bureaucrats) halved to 0.005 a month, then x0.4 with every other speed (2026-11-27)."""
    assert {k: v for k, v in rule.values.items() if k[2] == "global_monthly_literacy"} == {
        ("advances", "written_alphabet", "global_monthly_literacy"): Decimal("0.002"),
        ("advances", "educated_bureaucrats", "global_monthly_literacy"): Decimal("0.002")}
    advances = ls.effective_objects(vanilla, MOD, st.ADVANCES_DIR)
    for key in ("written_alphabet", "educated_bureaucrats"):
        assert [s.value for s in advances[key].body if s.key == "global_monthly_literacy"] == ["0.002"], key


def test_no_problems_and_every_file_is_classified(result: ls.Result) -> None:
    assert not result.problems, result.problems


def test_the_briefed_sources_are_cut(result: ls.Result) -> None:
    cut: dict[str, set[str]] = {}
    for change, _ in result.changes:
        cut.setdefault(change.folder, set()).add(change.obj)
    missing = {f: sorted(objs - cut.get(f, set())) for f, objs in BRIEFED.items() if objs - cut.get(f, set())}
    assert not missing, f"briefed literacy sources no longer cut (vanilla changed?): {missing}"


def test_files_are_current(vanilla: Path) -> None:
    result = ls.apply(REPO, PROJECT, MOD, vanilla, write=False)
    assert not result.changed, f"run uv run ppc literacy apply: {result.changed}"


def test_written_blocks_are_the_effective_objects_with_only_literacy_numbers_changed(
        rule: ls.Rule, result: ls.Result, vanilla: Path) -> None:
    for name, blocks in result.written.items():
        scope = rule.folders[name]
        path = MOD / scope.path / ls.OUTPUT_NAME
        written = {st._mode(s.key)[1]: (st._mode(s.key)[0], s.value)
                   for s in st.parse_statements(path.read_text(encoding="utf-8-sig")) if s.key and s.is_block}
        assert set(written) == set(blocks), name
        effective = ls.effective_objects(vanilla, MOD, scope.path, skip=(ls.OUTPUT_NAME,))
        for key, (mode, body) in written.items():
            assert mode == ("REPLACE" if effective[key].base_defined else "TRY_REPLACE"), key
            assert body == ls.cut_statements(rule, scope, key, effective[key].body)[0], key

            def strip(stmts):
                return tuple(st.Stmt(s.key, s.op, strip(s.value)) if s.is_block else s
                             for s in stmts if s.is_block or not (s.key and ls.LITERACY_KEY.match(s.key)))

            assert strip(body) == strip(effective[key].body), f"{name}/{key}: more than literacy numbers changed"


def test_one_replace_per_object(rule: ls.Rule, result: ls.Result, vanilla: Path) -> None:
    """The engine ignores injects into a replaced block, and two replaces make two owners: no object written here is
    replaced or injected by another mod file, and the file sorts after every vanilla and DLC file of its folder."""
    for name, blocks in result.written.items():
        scope = rule.folders[name]
        effective = ls.effective_objects(vanilla, MOD, scope.path)
        for key in blocks:
            mod_files = {f for _m, layer, f in effective[key].history if layer == "mod"}
            assert mod_files == {ls.OUTPUT_NAME}, f"{name}/{key}: also written by {mod_files - {ls.OUTPUT_NAME}}"
        names = [p.name for p in st.layered_files(vanilla, None, scope.path)]   # the definitions load first
        assert all(n < ls.OUTPUT_NAME for n in names), (name, max(names))


def test_other_owners_carry_the_cut(result: ls.Result) -> None:
    owners = {(c.folder, c.obj): by for c, by in result.changes if by != ls.OWN_WRITER}
    assert owners[("advances", "written_alphabet")].startswith("start_technology")
    assert owners[("advances", "educated_bureaucrats")].startswith("start_technology")
    assert owners[("advances", "guilds")].startswith("start_technology")
    assert owners[("advances", "organized_religion")].startswith("start_technology")
    assert owners[("laws", "legal_code_law")] == "pp_rgo_building_cost_redirects.txt"
    assert owners[("advances", "printing_press_advance")] == "pp_institution_advances_adjustments.txt"


def test_cut_lines_keeps_text_and_cuts_modifier_lines_only(rule: ls.Rule) -> None:
    lines = ["TRY_REPLACE:legal_code_law = {", "\tpolicy = {", "\t\tpotential = { global_max_literacy = 5 }",
             "\t\tcountry_modifier = {", "\t\t\tglobal_peasants_max_literacy = 10 # note",
             "\t\t\tglobal_nobles_max_literacy = 10", "\t\t}", "\t}", "}"]
    out = ls.cut_lines(rule, "laws", "legal_code_law", "01_legal_system.txt", lines)
    assert out[4] == "\t\t\tglobal_peasants_max_literacy = 4 # note"
    assert out[:4] == lines[:4] and out[5:] == lines[5:]
    assert ls.cut_lines(rule, "laws", "x", "02_country_specific.txt", lines) == lines
    # moving an all-class cap to the estates needs the whole block: cut_lines refuses rather than guess
    with pytest.raises(ls.LiteracySourcesError):
        ls.cut_lines(rule, "laws", "x", "01_common.txt", ["a = {", "\tcountry_modifier = {", "\t\tglobal_max_literacy = 5",
                                                          "\t}", "}"])
