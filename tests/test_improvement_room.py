"""Land improvements built and possible (improvement_room): the cap arithmetic on small frames, then the caps of the built
mod against the game's own script values and gates (start_rules) and against the handover's caps."""

import json
import math
import re
from pathlib import Path

import polars as pl
import pytest

from prosper_or_perish_constructor import improvement_room as ir
from prosper_or_perish_constructor.arable_land_bar import Building, CapUnit, Model

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod/Prosper or Perish (Population Growth & Food Rework)"
SHARED, SINGLE = "pp_wb_cap_terraces_shared", "pp_wb_cap_clearing_terms"


NICHE = {"terraces_improved": {"family": "terraces", "gate": []},
         "hill_works": {"family": "terraces", "gate": [{"culture": ["wu"], "province": ["hills"]}]}}


def _model(restricted: set[str] | None = None) -> ir.RoomModel:
    """Two caps: terraces (shared: a plain tier, its upgrade, a niche work gated to one province by culture and province,
    so it counts only where it stands) and clearing (one building, forest only)."""
    bar = Model([], [], [], units=[
        CapUnit(SHARED, 15.0, [Building("terraces", 5.0), Building("terraces_improved", 10.0, obsolete="terraces"),
                               Building("hill_works", 15.0)]),
        CapUnit(SINGLE, 15.0, [Building("clearing_works", 5.0)]),
    ])
    equations = {
        "management": {"base_levels": 10.0, "levels_per_development_point": 0.03,
                       "class_terms": [{"attribute": "climate", "value": "arid", "levels": -12.0},
                                       {"attribute": "fertility", "value": "high", "levels": 1.0}]},
        "clearing": {"base_levels": 2.0, "levels_per_development_point": 0.015,
                     "class_terms": [{"attribute": "climate", "value": "tropical", "levels": 4.0}]},
    }
    building_types = pl.DataFrame({
        "building": ["clearing", "management"], "level_limit": [15, 15],
        "gate_json": [json.dumps([{"vegetation": ["forest"]}]), "[]"],
        "cap_equation_json": [json.dumps(equations["clearing"]), json.dumps(equations["management"])],
    })
    attributes = pl.DataFrame({
        "location_tag": ["a", "b", "c", "d"], "climate": ["oceanic", "arid", "tropical", "oceanic"],
        "vegetation": ["forest", "desert", "forest", "grasslands"], "fertility": ["high", "low", "moderate", "moderate"],
        "province": ["x", "x", "hills", "x"],
    })
    return ir.build_model(bar, {"management": "terraces", "clearing": "clearing_works"}, NICHE, building_types, attributes,
                          restricted=ir.culture_locked(NICHE) if restricted is None else restricted)


def _locations(rows: list[tuple[str, str, float, int | None]]) -> pl.DataFrame:
    return pl.DataFrame(rows, schema={"snapshot_id": pl.String, "slug": pl.String, "development": pl.Float64,
                                      "owner": pl.Int64}, orient="row")


def _buildings(rows: list[tuple[str, str, str, float]]) -> pl.DataFrame:
    return pl.DataFrame(rows, schema={"snapshot_id": pl.String, "location_slug": pl.String, "building_type": pl.String,
                                      "level": pl.Float64}, orient="row")


def _caps(model: ir.RoomModel, rows: list[tuple[str, float]]) -> dict[tuple[str, str], float]:
    frame = _locations([(f"{tag}@{dev}", tag, dev, 1) for tag, dev in rows])
    return {(r["snapshot_id"], r["unit"]): r["cap"] for r in ir.location_caps(model, frame).iter_rows(named=True)}


def test_cap_is_base_terms_and_development_clamped_and_floored() -> None:
    caps = _caps(_model(), [("a", 27.3), ("a", 100.0), ("a", 200.0), ("b", 50.0), ("c", 27.3), ("c", 700.0)])
    # a: 10 + 1 (high fertility) + 0.03 x development, floored, at most 15
    assert caps["a@27.3", SHARED] == 11 and caps["a@100.0", SHARED] == 14 and caps["a@200.0", SHARED] == 15
    # b: 10 - 12 (arid) + 1.5 is below 0: no levels; desert fails the clearing gate: no row at all
    assert caps["b@50.0", SHARED] == 0 and ("b@50.0", SINGLE) not in caps
    # c: 2 + 4 (tropical) + 0.015 x development
    assert caps["c@27.3", SINGLE] == 6 and caps["c@700.0", SINGLE] == 15
    assert caps["a@27.3", SINGLE] == 2


def test_shared_cap_holds_its_members_levels_together_in_levels_and_land() -> None:
    model = _model()
    locations = _locations([("s", "a", 27.3, 1)])
    built = _buildings([("s", "a", "terraces", 4.0), ("s", "a", "terraces_improved", 5.0), ("s", "a", "clearing_works", 1.0)])
    rows = {r["unit"]: r for r in ir.room(model, locations, built).iter_rows(named=True)}
    terraces = rows[SHARED]
    # cap 11 holds the plain and the upgraded levels together
    assert (terraces["built"], terraces["possible"], terraces["total"], terraces["over_cap"]) == (9.0, 2.0, 11.0, 0.0)
    # land at full research: 11 levels of the improved tier (10 each; the hill works' province gate fails here)
    assert (terraces["built_land"], terraces["total_land"], terraces["possible_land"]) == (70.0, 110.0, 40.0)
    clearing = rows[SINGLE]
    assert (clearing["built"], clearing["possible"], clearing["total"]) == (1.0, 1.0, 2.0)
    assert (clearing["built_land"], clearing["possible_land"], clearing["total_land"]) == (5.0, 5.0, 10.0)
    assert ir.world(ir.room(model, locations, built)).row(0, named=True)["total"] == 13.0


def test_levels_above_the_cap_count_as_built_with_nothing_possible() -> None:
    # d at development 0: cap 10; 12 plain levels stand (development fell)
    rows = ir.room(_model(), _locations([("s", "d", 0.0, 1)]), _buildings([("s", "d", "terraces", 12.0)]))
    terraces = rows.filter(pl.col("unit") == SHARED).row(0, named=True)
    assert (terraces["built"], terraces["possible"], terraces["total"], terraces["over_cap"]) == (12.0, 0.0, 12.0, 2.0)
    # 10 levels of the improved tier hold 100; 60 stand
    assert (terraces["built_land"], terraces["total_land"], terraces["possible_land"]) == (60.0, 100.0, 40.0)


def test_best_member_land_follows_the_gates_and_what_stands() -> None:
    model = _model()
    assert model.restricted == {"hill_works"}   # culture-locked
    best = {(r["location_tag"], r["unit"]): r["best_land"] for r in model.locations.iter_rows(named=True)}
    gates = set(model.member_gates.select("location_tag", "building_type").iter_rows())
    assert ("c", "hill_works") in gates and ("a", "hill_works") not in gates and ("b", "clearing_works") not in gates
    # the hill works may stand in c (its culture is not checked) but are culture-locked: the improved tier is the best
    # anyone may build there; unrestricted they would be the best
    assert best["c", SHARED] == 10.0 and best["a", SHARED] == 10.0
    assert {(r["location_tag"], r["unit"]): r["best_land"] for r in _model(set()).locations.iter_rows(named=True)}["c", SHARED] == 15.0
    # standing, they give their land: in c, and in a, where the gates say they cannot stand
    for tag, cap in (("c", 10), ("a", 11)):
        rows = ir.room(model, _locations([("s", tag, 27.3, 1)]), _buildings([("s", tag, "hill_works", 1.0)]))
        terraces = rows.filter(pl.col("unit") == SHARED).row(0, named=True)
        assert (terraces["total"], terraces["built_land"], terraces["total_land"]) == (cap, 15.0, cap * 15.0)
    # a cap whose only members are restricted has levels but no land until one stands
    rows = ir.room(_model({"clearing_works"}), _locations([("s", "a", 27.3, 1)]), _buildings([]))
    clearing = rows.filter(pl.col("unit") == SINGLE).row(0, named=True)
    assert (clearing["total"], clearing["total_land"]) == (2.0, 0.0)


def test_unlocking_advances_are_read_in_the_games_load_order(tmp_path: Path) -> None:
    vanilla, mod = tmp_path / "game", tmp_path / "mod"
    files = {
        vanilla / ir.ADVANCES / "0_age_of_traditions.txt": "general_adv = { unlock_building = a unlock_building = d }",
        vanilla / ir.ADVANCES / "culture_andean.txt": "andean_adv = { potential = { } unlock_building = b }",
        vanilla / ir.ADVANCES / "country_vij.txt": "vij_adv = { unlock_building = c unlock_building = d }",
        vanilla / ir.ADVANCES / "region_iberia.txt": "iberian_adv = { unlock_building = h }",
        # the mod's same-name file replaces vanilla's: b is no longer unlocked there, f is
        mod / ir.ADVANCES / "culture_andean.txt": "andean_adv = { unlock_building = f }",
        # an inject adds to the advance's own file; a replace swaps its unlocks; a plain redefinition after the first
        # (files load in one sorted order) is ignored
        mod / ir.ADVANCES / "pp_adjustments.txt": ("TRY_INJECT:vij_adv = { unlock_building = e }\n"
                                                   "REPLACE:general_adv = { unlock_building = g }\n"
                                                   "andean_adv = { unlock_building = i }\n"),
    }
    for path, text in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    unlocks = ir.unlocking_files([vanilla, mod], set("abcdefghi"))
    assert unlocks == {"c": {"country_vij"}, "d": {"country_vij"}, "e": {"country_vij"}, "f": {"culture_andean"},
                       "g": {"0_age_of_traditions"}, "h": {"region_iberia"}}
    # d lost its general unlock to the replace; a building without an unlocking advance is general
    assert ir.regional(unlocks) == {"c", "d", "e", "f", "h"}
    assert ir.culture_locked({"x": {"lock": ["dominant_culture ?= culture:k"]}, "y": {"gate": [{"province": ["p"]}]},
                              "z": {"gate": [{"culture": ["k"]}]}}) == {"x", "z"}


def test_only_owned_locations_count() -> None:
    locations = _locations([("s", "a", 27.3, 1), ("s", "c", 27.3, None), ("t", "a", 27.3, None), ("t", "c", 27.3, 2)])
    built = _buildings([("s", "c", "clearing_works", 3.0), ("t", "a", "terraces", 4.0), ("t", "c", "clearing_works", 2.0)])
    rows = {(r["snapshot_id"], r["unit"]): r for r in ir.room(_model(), locations, built).iter_rows(named=True)}
    # s: only a (cap 11 terraces, 2 clearing), the unowned c's clearing works left out
    assert (rows["s", SHARED]["total"], rows["s", SINGLE]["total"], rows["s", SINGLE]["built"]) == (11.0, 2.0, 0.0)
    # t: only c (terraces 10, clearing 6 with 2 built); a's terraces are unowned
    assert (rows["t", SHARED]["total"], rows["t", SHARED]["built"]) == (10.0, 0.0)
    assert (rows["t", SINGLE]["built"], rows["t", SINGLE]["possible"]) == (2.0, 4.0)


def test_gate_expression_reads_like_the_setup_check() -> None:
    from prosper_or_perish_constructor.worldbuilder.buildings import gate_matches

    frame = pl.DataFrame({"location_tag": ["a", "b", "c"], "river_level": ["0", "2", "0"],
                          "is_coastal": ["True", "false", "False"], "topography": ["flatland", "hills", "wetlands"]})
    rules = [{"river_level": ["1", "2", "3"]}, {"is_coastal": ["True"], "topography": ["flatland", "wetlands"]}]
    assert frame.filter(ir.gate_expr(rules, set(frame.columns)))["location_tag"].to_list() == ["a", "b"]
    assert [gate_matches(rules, r) for r in frame.iter_rows(named=True)] == [True, True, False]
    # culture is not checked; an attribute the frame lacks fails; no rules hold everywhere
    assert frame.filter(ir.gate_expr([{"culture": ["wu"], "topography": ["hills"]}], set(frame.columns))).height == 1
    assert frame.filter(ir.gate_expr([{"soil_type": ["loam"]}], set(frame.columns))).height == 0
    assert frame.filter(ir.gate_expr([], set(frame.columns))).height == 3


# --- the built mod ------------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def built():
    if not (MOD_ROOT / "in_game/common/script_values/pp_wb_building_caps.txt").is_file():
        pytest.skip("mod not built")
    from prosper_or_perish_constructor.worldbuilder.contract import load_config, load_contract

    try:
        contract = load_contract(load_config(ROOT, ROOT / "constructor.toml").handover)
    except FileNotFoundError:
        pytest.skip("no World Builder handover")
    return ir.load_model(ROOT, ROOT / "constructor.toml"), contract


def test_mod_caps_are_the_handover_caps_at_its_development(built) -> None:
    """Every (location, World Builder class) the handover gives a cap: the model's cap of the class's unit at the
    handover's start development and at development 100 is the handover's cap_at_start / cap_at_reference_development."""
    from prosper_or_perish_constructor.worldbuilder.contract import load_config

    model, contract = built
    unit_of = dict(model.members.select("building_type", "unit").iter_rows())
    building_map = load_config(ROOT, ROOT / "constructor.toml").building_map
    kinds = pl.DataFrame({"building": list(building_map), "unit": [unit_of[k] for k in building_map.values()]})
    attributes = contract.location_attributes
    passing = pl.concat([
        attributes.filter(ir.gate_expr(json.loads(str(r["gate_json"])), set(attributes.columns)))
        .select("location_tag", pl.lit(str(r["building"])).alias("building"))
        for r in contract.building_types.iter_rows(named=True)])
    rows = (contract.location_buildings.join(passing, on=["location_tag", "building"], how="semi").join(kinds, on="building")
            .join(contract.location_targets.select("location_tag", "development"), on="location_tag"))
    assert rows.height > 100_000
    for column, development in (("cap_at_start", pl.col("development")), ("cap_at_reference_development", pl.lit(100.0))):
        frame = rows.select(pl.concat_str("location_tag", "building", separator="|").alias("snapshot_id"),
                            pl.col("location_tag").alias("slug"), development.alias("development"), "unit", column)
        caps = frame.join(ir.location_caps(model, frame.drop("unit", column)), on=["snapshot_id", "slug", "unit"], how="left")
        wrong = caps.filter(pl.col("cap").fill_null(-1.0) != pl.col(column))
        assert wrong.is_empty(), wrong.head(5)


def test_mod_caps_and_gates_are_the_games_script_values(built) -> None:
    """The game's own max levels and location_potential (start_rules over the built mod) for sanlorenzo, a spread of
    locations and locations where each member may stand, at four developments: the model's cap per unit = the unit's
    equation (clamped, floored) = every member's max level without other levels; the model's member gates = the
    buildings' location_potential (a culture lock given its culture: the model does not check culture)."""
    from prosper_or_perish_constructor.worldbuilder import buildings as wb
    from prosper_or_perish_constructor.worldbuilder.start_rules import Rules, first

    model, contract = built
    rules = Rules(ROOT, ROOT / "constructor.toml")
    coast = ir.setup_sea_coast(MOD_ROOT) or set()
    attributes = {r["location_tag"]: r for r in contract.location_attributes.iter_rows(named=True)}
    tags = sorted(attributes)
    gates = set(model.member_gates.select("location_tag", "building_type").iter_rows())
    standing = {}
    for tag, key in sorted(gates):
        standing.setdefault(key, []).append(tag)
    sample = sorted({"sanlorenzo", *tags[:: len(tags) // 40], *(t for ts in standing.values() for t in ts[:: max(1, len(ts) // 3)][:3])})
    assert attributes["sanlorenzo"]["climate"] == "oceanic" and attributes["sanlorenzo"]["topography"] == "hills"

    def ctx(tag: str, development: float) -> dict:
        a = attributes[tag]
        river = int(a["river_level"] or 0)
        return {
            "location_tag": tag, "development": development, "buildings": {}, "variables": {},
            **{k: wb._game_key(contract, k, a[k]) for k in ("climate", "vegetation", "topography")},
            "static_modifiers": {f"pp_wb_fertility_{a['fertility']}", f"pp_wb_soil_{a['soil_type']}",
                                 *(["pp_wb_coastal"] if tag in coast else [])},
            "modifiers": {"irrigant_cap_modifier": river}, "has_river": river > 0,
            "is_adjacent_to_lake": str(a["is_adjacent_to_lake"]).lower() == "true", "province_definition": a["province"],
        }

    developments = (0.0, 27.3, 100.0, 455.5)
    frame = _locations([(f"{tag}@{dev}", tag, dev, 1) for tag in sample for dev in developments])
    caps = {(r["snapshot_id"], r["unit"]): r["cap"] for r in ir.location_caps(model, frame).iter_rows(named=True)}
    from eu5gameparser.clausewitz.serializer import render_value

    cultures = {}
    for key in (k for unit in model.units for k in unit.members):
        potential = first(rules.buildings[key], "location_potential")
        found = re.search(r"culture:(\w+)", render_value(potential)) if potential is not None else None
        if found:
            cultures[key] = found[1]
    assert {"khmer_baray", "jiangnan_hill_terraces", "jiangnan_canal_network"} <= set(cultures)
    checked = 0
    for tag in sample:
        for development in developments:
            context = ctx(tag, development)
            for unit in model.units:
                game = max(0, math.floor(min(rules.value(unit.equation, context), unit.limit) + 1e-9))
                may = any((tag, key) in gates for key in unit.members)
                assert caps.get((f"{tag}@{development}", unit.equation), 0.0) == (game if may else 0), (tag, development, unit)
                for key in unit.members:
                    body = rules.buildings[key]
                    assert max(0, math.floor(rules.value(first(body, "max_levels"), context) + 1e-9)) == game, (tag, key)
                    if development == developments[0]:
                        culture = {"dominant_culture": cultures[key]} if key in cultures else {}
                        assert rules.test(first(body, "location_potential"), {**context, **culture}) == ((tag, key) in gates), (tag, key)
                        checked += 1
    assert checked >= 15 * 60


def test_regional_members_of_the_mod_count_only_where_they_stand(built) -> None:
    """The members only some countries can build: regional unlocks (incamisana: culture_andean.txt, bund:
    country_vij.txt, polders: culture_netherlands.txt) and culture locks (Khmer baray, the Jiangnan works). The field
    management tiers unlock in the mod's own general advances."""
    from prosper_or_perish_constructor.cap_tooltips import game_root
    from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

    model, _ = built
    keys = {k for unit in model.units for k in unit.members}
    unlocks = ir.unlocking_files([game_root(vanilla_root(ROOT, ROOT / "constructor.toml")), MOD_ROOT], keys)
    assert unlocks["incamisana"] == {"culture_andean"} and unlocks["bund"] == {"country_vij"}
    assert unlocks["field_management_improved"] == {"pp_field_management_improved"}
    assert model.restricted == {"incamisana", "bund", "polders", "khmer_baray", "jiangnan_hill_terraces",
                                "jiangnan_canal_network"}


def test_incamisana_does_not_lift_the_land_of_a_water_control_location(built) -> None:
    """Every location where the incamisana (7.5 land per level, Andean advance) may stand is valued at the general
    water works' 5 per level; only where an incamisana stands does its land count."""
    model, contract = built
    water = "pp_wb_cap_water_control_shared"
    land = dict(model.members.select("building_type", "land").iter_rows())
    assert land["incamisana"] == 7.5 and land["irrigation_systems"] == 5.0
    incamisana = model.member_gates.filter(pl.col("building_type") == "incamisana").select("location_tag")
    best = model.locations.filter(pl.col("unit") == water).join(incamisana, on="location_tag", how="semi")
    assert best.height > 10_000 and best["best_land"].unique().to_list() == [5.0]
    europe = contract.location_attributes.filter(pl.col("super_region") == "europe").select("location_tag")
    tag = sorted(best.join(europe, on="location_tag", how="semi")["location_tag"].to_list())[0]
    locations = _locations([("s", tag, 200.0, 1), ("t", tag, 200.0, 1)])
    rows = ir.room(model, locations, _buildings([("t", tag, "incamisana", 1.0)])).filter(pl.col("unit") == water)
    without, standing = (rows.filter(pl.col("snapshot_id") == s).row(0, named=True) for s in ("s", "t"))
    cap = without["total"]
    assert cap >= 1 and without["total_land"] == cap * 5.0 and standing["total_land"] == cap * 7.5


def test_report_chart_and_tile_show_built_possible_and_total(tmp_path: Path) -> None:
    from test_run_report import _trade_run

    from prosper_or_perish_constructor import run_report as rr
    from prosper_or_perish_constructor.run_report_charts import build_payload

    run = _trade_run()
    locations = _locations([("s1", "a", 27.3, 1), ("s2", "a", 100.0, 1), ("s2", "c", 27.3, None)])
    built = _buildings([("s1", "a", "terraces", 4.0), ("s2", "a", "terraces", 6.0), ("s2", "a", "terraces_improved", 4.0)])
    run.improvements = ir.room(_model(), locations, built)
    chart = {c["key"]: c for c in build_payload(run)["charts"]}["improvements"]
    assert chart["section"] == "buildings" and [v["label"] for v in chart["views"]] == ["Levels", "Land", "Share built by cap"]
    levels, land, share = ({s["name"]: [p[1] for p in s["data"]] for s in v["option"]["series"]} for v in chart["views"])
    # s1: terraces 4 of 11, clearing 0 of 2; s2: terraces 10 of 14, clearing 0 of 3
    assert levels == {"Built": [4.0, 10.0], "Still possible": [9.0, 7.0], "Possible in total": [13.0, 17.0]}
    # land in millions of people: s2 terraces 6 x 5 + 4 x 10 = 70 of 14 x 10 = 140, clearing 0 of 3 x 5
    assert land["Built"][1] == pytest.approx(0.07) and land["Possible in total"][1] == pytest.approx(0.155)
    assert share["World"][1] == pytest.approx(1000 / 17, rel=1e-3) and share["Terraces"][1] == pytest.approx(1000 / 14, rel=1e-3)
    assert "Built 10 of 17 levels (59%) at the last save, 31% at the first." in chart["caption"]
    page = rr.write_page(run, tmp_path, [], build_payload(run)).read_text(encoding="utf-8")
    assert "Land improvements built" in page and "10 of 17 levels · 31% in 1337" in page
