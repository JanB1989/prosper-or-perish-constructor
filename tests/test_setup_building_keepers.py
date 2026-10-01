"""Vanilla setup buildings kept where the World Builder geography fails their location_potential."""

from __future__ import annotations

import tomllib
from pathlib import Path
from types import SimpleNamespace

from eu5gameparser.clausewitz.parser import parse_file, parse_text

from prosper_or_perish_constructor.worldbuilder import start_simulation as ss
from prosper_or_perish_constructor.worldbuilder.start_rules import Rules

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"


def _configured() -> list[str]:
    raw = tomllib.loads((ROOT / "constructor.toml").read_text(encoding="utf-8"))
    return list(raw["worldbuilder"]["start"]["keep_setup_buildings"])


def _sim(potential: str, rows: dict[str, dict]) -> SimpleNamespace:
    rules = Rules.__new__(Rules)
    rules.triggers, rules.values = {}, {}
    rules.buildings = {"tar_kiln": parse_text(f"tar_kiln = {{ location_potential = {{ {potential} }} }}").entries[0].value}
    counts = {tag: {"tar_kiln": row.pop("levels")} for tag, row in rows.items()}
    return SimpleNamespace(rules=rules, locations=list(rows), counts=counts, ctx=lambda tag: {"location_tag": tag, **rows[tag]})


def test_failing_setup_rows_are_listed_and_then_pass(tmp_path: Path) -> None:
    sim = _sim("OR = { pp_wb_setup_tar_kiln_location = yes vegetation = forest }", {
        "woods": {"vegetation": "forest", "levels": 2},
        "plain": {"vegetation": "grasslands", "levels": 4},
        "empty": {"vegetation": "grasslands", "levels": 0},   # no setup row: not kept
    })
    kept, unreferenced = ss.keep_setup_buildings(sim, ["tar_kiln"], tmp_path)
    assert kept == {"tar_kiln": ["plain"]} and unreferenced == []
    text = (tmp_path / ss.SETUP_BUILDING_TRIGGERS_PATH).read_text(encoding="utf-8-sig")
    assert "pp_wb_setup_tar_kiln_location = {\n\tOR = { this = location:plain }\n}" in text
    potential = next(iter(sim.rules.buildings["tar_kiln"].values("location_potential")))
    assert sim.rules.test(potential, sim.ctx("plain")) and not sim.rules.test(potential, sim.ctx("empty"))


def test_nothing_failing_writes_an_always_no_trigger_and_reports_missing_references(tmp_path: Path) -> None:
    sim = _sim("vegetation = forest", {"woods": {"vegetation": "forest", "levels": 1}})
    kept, unreferenced = ss.keep_setup_buildings(sim, ["tar_kiln"], tmp_path)
    assert kept == {"tar_kiln": []} and unreferenced == ["tar_kiln"]
    assert "pp_wb_setup_tar_kiln_location = {\n\talways = no\n}" in (tmp_path / ss.SETUP_BUILDING_TRIGGERS_PATH).read_text(encoding="utf-8-sig")


def test_the_mod_defines_and_tests_every_keeper_trigger() -> None:
    keys = _configured()
    assert set(keys) >= {"terraces", "fruit_orchard", "tar_kiln", "lumber_mill"}
    defined = {e.key for e in parse_file(MOD_ROOT / ss.SETUP_BUILDING_TRIGGERS_PATH).entries}
    assert defined == {ss.setup_building_trigger(k) for k in keys}
    texts = "\n".join(p.read_text(encoding="utf-8-sig") for p in (MOD_ROOT / "in_game/common/building_types").glob("*.txt"))
    for key in keys:
        assert f"{ss.setup_building_trigger(key)} = yes" in texts, f"{key}: its location_potential must test the keeper"
    report = (ROOT / "artifacts/data/worldbuilder/start_placement.json")
    if report.is_file():
        import json

        data = json.loads(report.read_text(encoding="utf-8"))
        assert data.get("setup_building_keepers_unreferenced", []) == []


def test_terraces_inject_keeps_vanilla_tests() -> None:
    # terraces is a TRY_INJECT: its injected potential must carry vanilla's own tests next to the keeper
    text = (MOD_ROOT / "in_game/common/building_types/zz_pp_terraces.txt").read_text(encoding="utf-8-sig")
    for test in ("topography = mountains", "topography = plateau", "topography = hills", "pp_wb_setup_terraces_location = yes"):
        assert test in text
