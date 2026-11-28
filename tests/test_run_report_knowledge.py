import json
from pathlib import Path
from types import SimpleNamespace

import polars as pl
import pytest

from prosper_or_perish_constructor import run_report_knowledge as rk


def _data() -> rk.KnowledgeData:
    """Tree: a (first age, 10 points), b and c (second age, 20 and 30); x is a country advance outside the tree (5)."""
    jobs = pl.DataFrame({"building_type": ["marketplace", "workshop", "pp_village_school", "library"],
                         "pop_type": ["burghers", "laborers", "clergy", "clergy"], "per_level": [0.1, 1.0, 0.05, 0.1]})
    return rk.KnowledgeData(costs={"a": 10.0, "b": 20.0, "c": 30.0, "x": 5.0}, ages={"a": 0, "b": 1, "c": 1, "x": 0},
                            tree=frozenset({"a", "b", "c"}), age_keys=["age_1_traditions", "age_2_renaissance"], jobs=jobs)


def _dataset(root: Path) -> Path:
    """France (1) owns Paris and Lyon in Western Europe, Atlantis is unowned; a landless pretender (2) holds c."""
    zero = [0.0, 0.0, 0.0]
    columns = {f"{k}_{c}": list(zero) for c in rk.CLASSES for k in ("population", "unemployed")}
    columns.update({"population_burghers": [10.0, 5.0, 0.0], "population_laborers": [20.0, 10.0, 0.0],
                    "unemployed_burghers": [2.0, 1.0, 0.0], "unemployed_laborers": [5.0, 0.0, 0.0]})
    tables = {
        "locations": {"location_id": [1, 2, 3], "owner_country_id": [1, 1, None], "macro_region": ["western_europe", "western_europe", None],
                      "super_region": ["europe", "europe", None], "total_population": [100.0, 50.0, 10.0],
                      "max_raw_material_workers": [2.0, 0.0, 0.0], "rgo_employed": [1.5, 0.0, 0.0], **columns},
        "population": {"location_id": [1, 1, 2, 2, 3], "pop_type": ["burghers", "laborers", "burghers", "laborers", "tribesmen"],
                       "size": [10.0, 20.0, 5.0, 10.0, 10.0], "literacy": [50.0, 2.0, 80.0, 10.0, 0.0]},
        # a closed Marketplace in Lyon: its jobs stay unfilled
        "buildings": {"building_type": ["marketplace", "marketplace", "workshop", "pp_village_school", "library"],
                      "location_id": [1, 2, 1, 1, 3], "level": [3.0, 2.0, 5.0, 2.0, 1.0], "employed": [0.25, None, 4.0, 0.1, 0.1],
                      "open": [True, False, True, True, True]},
        "country_advances": {"country_id": [1, 1, 1, 2], "advance": ["a", "b", "x", "c"]},
        "countries": {"country_id": [1, 2], "country_tag": ["FRA", "PRE"], "country_name": ["France", "Pretender"]},
    }
    dataset = root / "dataset"
    for table, data in tables.items():
        folder = dataset / "tables" / table / "playthrough_id=run"
        folder.mkdir(parents=True)
        pl.DataFrame(data).write_parquet(folder / "s1.parquet")
    return dataset


def _figures(flows: dict[str, pl.DataFrame], data: rk.KnowledgeData, owner: int | None = None) -> dict:
    cells = rk.weighted(flows["cells"], flows["countries"], len(data.age_keys))
    if owner is not None:
        cells = cells.filter(pl.col("owner_country_id") == owner)
    sums = cells.select(pl.col(c).sum() for c in rk.sum_columns(len(data.age_keys))).row(0, named=True)
    return rk.scope_figures(sums, data.tree_totals())


def test_tree_share_counts_tree_advances_only_and_weights_by_owned_people(tmp_path: Path) -> None:
    data = _data()
    assert data.tree_totals() == {"n": 3, "points": 60.0, "ages": [{"n": 1, "points": 10.0}, {"n": 2, "points": 50.0}]}
    flows = rk.save_knowledge(_dataset(tmp_path), "run", "s1", data)
    france = flows["countries"].row(0, named=True)
    assert flows["countries"].height == 1  # the landless pretender is no land owner
    assert france["points"] == 35.0 and france["tree_points"] == 30.0 and france["tree_n"] == 2.0
    world = _figures(flows, data)
    # only France owns land: the world's mean is France's (Atlantis' people own nothing and do not count)
    assert world["tech_share"] == pytest.approx(0.5) and world["tech_held"] == pytest.approx(2.0)
    assert world["tech_held_share"] == pytest.approx(2 / 3) and world["tech_points"] == pytest.approx(35.0)
    assert world["tech_age_0"] == pytest.approx(1.0) and world["tech_age_1"] == pytest.approx(0.4)
    quantiles = rk.weighted_quantiles(pl.DataFrame({"share": [0.2, 0.5, 0.9], "people": [10.0, 30.0, 60.0]}))
    assert quantiles["q10"] == 0.2 and quantiles["q25"] == 0.5 and quantiles["q50"] == 0.9 and quantiles["qmax"] == 0.9


def test_literacy_is_weighted_by_pop_size(tmp_path: Path) -> None:
    data = _data()
    flows = rk.save_knowledge(_dataset(tmp_path), "run", "s1", data)
    world, france = _figures(flows, data), _figures(flows, data, owner=1)
    assert world["lit_burghers"] == pytest.approx((10 * 50 + 5 * 80) / 15)
    assert world["lit_laborers"] == pytest.approx((20 * 2 + 10 * 10) / 30) and world["low_laborers"] == pytest.approx(20 / 30)
    assert world["lit_all"] == pytest.approx(1040 / 55) and world["low_all"] == pytest.approx(30 / 55)  # the tribesmen count
    assert france["lit_all"] == pytest.approx(1040 / 45) and france["low_all"] == pytest.approx(20 / 45)
    assert world["lit_nobles"] is None  # no nobles: no figure


def test_jobs_filled_unfilled_with_a_closed_building_and_the_village_school_share(tmp_path: Path) -> None:
    data = _data()
    flows = rk.save_knowledge(_dataset(tmp_path), "run", "s1", data)
    france = _figures(flows, data, owner=1)
    # Marketplaces 3 + 2 levels x 0.1; the open one has 0.25 workers, the closed one's 0.2 jobs stay unfilled
    assert france["jobs_burghers"] == pytest.approx(0.5) and france["filled_burghers"] == pytest.approx(0.25)
    assert france["unfilled_burghers"] == pytest.approx(0.25) and france["closed_jobs_burghers"] == pytest.approx(0.2)
    assert france["closed_burghers"] == 1.0
    # laborers: the workshop's 5 jobs (4 filled) and the RGO's 2 places (1.5 filled)
    assert france["jobs_laborers"] == pytest.approx(7.0) and france["filled_laborers"] == pytest.approx(5.5)
    assert france["pop_burghers"] == 15.0 and france["idle_burghers"] == 3.0 and france["work_burghers"] == 12.0
    assert france["share_laborers"] == pytest.approx(30 / 150)
    assert france["lv_pp_village_school"] == 2.0 and france["vs_share"] == pytest.approx(0.5)  # Paris of two owned locations
    world = _figures(flows, data)
    assert world["lv_library"] == 1.0 and world["vs_share"] == pytest.approx(0.5)  # unowned Atlantis is no owned location


def test_page_data_per_scope_and_cache(tmp_path: Path) -> None:
    from prosper_or_perish_constructor.run_report import Labels
    from prosper_or_perish_constructor.run_report_knowledge_page import knowledge_page_html

    data = _data()
    dataset = _dataset(tmp_path)
    locations = pl.read_parquet(dataset / "tables" / "locations" / "playthrough_id=run" / "s1.parquet").with_columns(
        pl.lit("s1").alias("snapshot_id"), pl.lit(0.0).alias("unemployed_peasants"))
    run = SimpleNamespace(playthrough_id="run", name="Run x", years=(1337, 1337), labels=Labels(), locations=locations,
                          snapshots=pl.DataFrame({"snapshot_id": ["s1"], "year": [1337], "date": ["1337.4.1"], "date_sort": [13370401]}))
    out, cache = tmp_path / "out", tmp_path / "cache"
    out.mkdir()
    built = rk.build_knowledge_data(run, dataset, out, data, cache=cache, log=lambda _: None)
    assert [s["id"] for s in built["scopes"]] == ["world", "r:western_europe", "r:other", "c:1"]
    assert built["saves"][0]["leaders"][0][0] == "France" and built["saves"][0]["leaders"][0][3] == 0.5

    def payload(name: str) -> dict:
        text = (out / name).read_text(encoding="utf-8")
        return json.loads(text[text.index("=", text.index("]")) + 1:].rstrip().rstrip(";"))

    summary = payload("knowledge/summary.js")
    assert summary["0"]["tech_share"] == [0.5] and summary["1"]["jobs_burghers"] == [0.5]
    assert payload("knowledge/c3.js")["filled_laborers"] == [5.5]
    assert len(list(cache.glob("s1.*/done"))) == 1
    logs: list[str] = []
    rk.build_knowledge_data(run, dataset, out, data, cache=cache, log=logs.append)
    assert "(0 computed, 1 cached)" in logs[0]
    page = knowledge_page_html("Run x", (1337, 1400))
    assert "knowledge/index.js" in page and "knowledge/summary.js" in page and 'name="robots"' in page and "index.html" in page


def test_no_element_id_twice_and_every_chart_draws_into_its_own_box() -> None:
    # 2026-11-28: the Education heading and its chart both had id "schools"; the chart drew into the heading, so the
    # heading lost its text and "Schools over the run" stayed empty
    import re
    from collections import Counter

    from prosper_or_perish_constructor.run_report_knowledge_page import KNOWLEDGE_JS, knowledge_page_html

    html = knowledge_page_html("run", (1342, 1837))
    ids = Counter(re.findall(r"""<[a-z0-9]+[^<>]*?\bid=["']?([A-Za-z0-9_-]+)""", html))
    assert [name for name, n in ids.items() if n > 1] == []
    boxes = set(re.findall(r"""<div id=["']?([A-Za-z0-9_-]+)["']? class=["']?chart""", html))
    drawn = set(re.findall(r"""\blines\('([a-z_]+)'""", KNOWLEDGE_JS))
    assert drawn and drawn <= boxes
