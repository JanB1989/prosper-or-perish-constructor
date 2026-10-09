"""Peace treaty files the mod copies from vanilla (same file name replaces vanilla's) stay vanilla except PP's block.

expand_clan_influence.txt: with connected-land peace deals (docs/peace_deal_rulebook.md) Japanese clans took the
Southern Court's palace years earlier and ended the Nanbokucho around 1340 instead of 1344. PP forbids the term
against an imperial court during the first five years of the situation; everything else is vanilla, so a game
update to the vanilla file fails here and must be merged.
"""

from __future__ import annotations

from pathlib import Path

from eu5gameparser.load_order import load_profile

ROOT = Path(__file__).resolve().parents[1]
LOAD_ORDER = ROOT / "constructor.load_order.toml"
MOD_TREATIES = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)" / "in_game" / "common" / "peace_treaties"

PP_COURT_GATE = [
    "\t\t# PP: a court keeps its palace during the first five years of the Nanbokucho (keeps vanilla timing with connected-land",
    "\t\t# peace deals, docs/peace_deal_rulebook.md)",
    "\t\ttrigger_if = {",
    "\t\t\tlimit = {",
    "\t\t\t\tscope:loser = { has_reform = government_reform:japanese_imperial_family }",
    "\t\t\t\tsituation:nanbokuchou = { situation_is_active = yes }",
    "\t\t\t}",
    "\t\t\tsituation:nanbokuchou = { years_since_situation_start >= 5 }",
    "\t\t}",
]


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8-sig").splitlines()


def test_clan_influence_is_vanilla_plus_the_court_gate() -> None:
    vanilla_dir = load_profile(profile="vanilla", load_order_path=LOAD_ORDER).layers[0].common_dir_for("in_game")
    vanilla = _lines(vanilla_dir / "peace_treaties" / "expand_clan_influence.txt")
    mod = _lines(MOD_TREATIES / "expand_clan_influence.txt")
    start = next(i for i, line in enumerate(mod) if line == PP_COURT_GATE[0])
    assert mod[start:start + len(PP_COURT_GATE)] == PP_COURT_GATE
    assert mod[:start] + mod[start + len(PP_COURT_GATE):] == vanilla, (
        "vanilla expand_clan_influence.txt changed: merge the update into the mod copy")
