import json
import subprocess
from pathlib import Path

import polars as pl

from prosper_or_perish_constructor import run_report as rr


def _fake_report(root: Path, playthrough: str, name: str) -> Path:
    report = root / playthrough
    (report / "maps").mkdir(parents=True)
    (report / "maps" / "political.png").write_bytes(b"png")
    (report / "index.html").write_text('<meta property="og:image" content="maps/political.png">', encoding="utf-8")
    (report / "report.json").write_text(
        json.dumps({"playthrough_id": playthrough, "name": name, "years": [1337, 1400], "saves": 3}), encoding="utf-8"
    )
    return report


def _bare_site(tmp_path: Path) -> str:
    bare = tmp_path / "site.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    seed = tmp_path / "seed"
    subprocess.run(["git", "init", "-q", "-b", "main", str(seed)], check=True)
    (seed / "index.html").write_text("soon", encoding="utf-8")
    subprocess.run(["git", "-C", str(seed), "add", "."], check=True)
    subprocess.run(["git", "-C", str(seed), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"], check=True)
    subprocess.run(["git", "-C", str(seed), "push", "-q", str(bare), "main"], check=True)
    return f"file://{bare}"


def test_publish_keeps_newest_runs_in_one_commit(tmp_path: Path) -> None:
    remote = _bare_site(tmp_path)
    reports = tmp_path / "reports"
    for playthrough, name in (("run_a", "First run"), ("run_b", "Second run")):
        plan = rr.prepare_publish(
            _fake_report(reports, playthrough, name), site_repo="Someone/runs", work_root=tmp_path / "work",
            keep=1, remote=remote,
        )
        rr.push_publish(plan)

    assert plan.url == "https://someone.github.io/runs/"
    assert [r["playthrough_id"] for r in plan.runs] == ["run_b"]
    assert plan.dropped == ["run_a"]
    check = tmp_path / "check"
    subprocess.run(["git", "clone", "-q", remote, str(check)], check=True)
    log = subprocess.run(["git", "-C", str(check), "log", "--oneline"], capture_output=True, text=True, check=True)
    assert len(log.stdout.splitlines()) == 1
    assert sorted(p.name for p in (check / "runs").iterdir() if p.is_dir()) == ["run_b"]
    index = (check / "runs" / "index.html").read_text(encoding="utf-8")
    assert "Second run" in index and "First run" not in index
    page = (check / "runs" / "run_b" / "index.html").read_text(encoding="utf-8")
    assert 'content="https://someone.github.io/runs/runs/run_b/maps/political.png"' in page
    assert '<meta name="robots" content="noindex">' in page


def test_wip_replaces_the_root_and_keeps_the_runs(tmp_path: Path) -> None:
    remote = _bare_site(tmp_path)
    reports = tmp_path / "reports"
    rr.push_publish(
        rr.prepare_publish(_fake_report(reports, "run_a", "First run"), site_repo="Someone/preview",
                           work_root=tmp_path / "work", remote=remote)
    )
    docs = tmp_path / "docs"
    (docs / "examples").mkdir(parents=True)
    (docs / "index.html").write_text("<html><head><title>Docs</title></head><body><h1>Docs</h1></body></html>", encoding="utf-8")
    (docs / "examples" / "explorer.html").write_text("<html><head></head><body>x</body></html>", encoding="utf-8")
    for commit in ("abc1234", "def5678"):
        plan = rr.prepare_wip(docs, site_repo="Someone/preview", work_root=tmp_path / "work", branch="0.10",
                              commit=commit, dirty=False, remote=remote)
        rr.push_publish(plan)
    # a later run publish keeps the WIP docs at the root
    rr.push_publish(
        rr.prepare_publish(_fake_report(tmp_path / "reports2", "run_b", "Second run"), site_repo="Someone/preview",
                           work_root=tmp_path / "work", remote=remote)
    )

    check = tmp_path / "check"
    subprocess.run(["git", "clone", "-q", remote, str(check)], check=True)
    log = subprocess.run(["git", "-C", str(check), "log", "--oneline"], capture_output=True, text=True, check=True)
    assert len(log.stdout.splitlines()) == 1
    root = (check / "index.html").read_text(encoding="utf-8")
    assert "Work in progress</b>: 0.10 @ def5678" in root and "abc1234" not in root
    assert '<meta name="robots" content="noindex">' in (check / "examples" / "explorer.html").read_text(encoding="utf-8")
    assert sorted(p.name for p in (check / "runs").iterdir() if p.is_dir()) == ["run_a", "run_b"]


def test_summary_and_investment_map_read_the_building_investment() -> None:
    import polars as pl

    snapshots = pl.DataFrame({"snapshot_id": ["s1", "s2"], "date": ["1337.4.1", "1340.4.1"], "year": [1337, 1340],
                              "date_sort": [13370401, 13400401], "playthrough_name": [None, None]})
    locations = pl.DataFrame({"snapshot_id": ["s1", "s1", "s2", "s2"], "slug": ["york", "paris"] * 2,
                              "country_tag": ["ENG", "FRA"] * 2, "owner": [1, 2] * 2,
                              "total_population": [10.0, 20.0, 12.0, 22.0], "unemployed_total": [0.0] * 4})
    countries = pl.DataFrame({"snapshot_id": ["s2"] * 3, "country_tag": ["ENG", "FRA", "ENG"],
                              "country_name": ["England", "France", "Pretender"], "population": [12.0, 22.0, 12.0],
                              "owned_locations_count": [1, 1, 0], "gold": [5.0, 6.0, 0.0], "is_subject": [False] * 3})
    run = rr.RunData("run", "Run", snapshots, locations, pl.DataFrame(), pl.DataFrame(), countries, pl.DataFrame())
    run.investment_by_location = pl.DataFrame({"snapshot_id": ["s1", "s2"], "slug": ["york", "york"],
                                               "investment": [100.0, 250.0]})
    run.investment_by_category = pl.DataFrame({"snapshot_id": ["s1", "s2"], "investment_category": ["crafts"] * 2,
                                               "investment": [100.0, 250.0]})
    run.investment_by_country = pl.DataFrame({"snapshot_id": ["s2"], "country_tag": ["ENG"], "investment": [250.0]})
    run.building_levels = pl.DataFrame({"snapshot_id": ["s1"], "slug": ["york"], "levels": [2.0]})

    summary = rr._summary(run)
    assert (summary["investment_first"], summary["investment_last"]) == (100.0, 250.0)
    leaders = {r["country_name"]: r["investment"] for r in summary["leaders"]}
    assert leaders == {"France": None, "England": 250.0}  # the landless pretender is left out

    values = rr._investment_values(run, locations.filter(pl.col("snapshot_id") == "s2"))
    assert dict(values.iter_rows()) == {"york": 250.0, "paris": 0.0}


def test_scales_map_values_into_the_colour_ramp() -> None:
    import numpy as np

    scale = rr.Scale("diverging", -1.0, 1.0, rr._ramp(rr.DIVERGING), [])
    positions = scale.position(np.array([-2.0, -1.0, 0.0, 1.0, 5.0]))
    assert positions.tolist() == [0.0, 0.0, 0.5, 1.0, 1.0]
    colours = scale.colours(np.array([np.nan, 0.0]))
    assert tuple(colours[0]) == rr.LAND_NODATA


def test_symlog_scale_is_symmetric_and_logarithmic_in_the_absolute_change() -> None:
    import numpy as np
    import polars as pl
    import pytest

    scale = rr.Scale("symlog", 10.0, 10_000.0, rr._ramp(rr.DIVERGING), [])
    t = scale.position(np.array([-1e6, -10_000.0, -990.0, 0.0, 990.0, 10_000.0, 1e6]))
    assert t[3] == 0.5 and t[0] == 0.0 and t[-1] == 1.0
    assert t[1] == pytest.approx(0.0) and t[5] == pytest.approx(1.0)
    assert t[4] - 0.5 == pytest.approx(0.5 - t[2])  # same distance both ways
    # 990 gold = 1 + 990/10 = 100 -> 2 of the 3 decades (log10 1001) from the middle
    assert t[4] == pytest.approx(0.5 + 0.5 * 2 / np.log10(1001))

    frames = pl.DataFrame({"value": [-5_000.0, -50.0, 0.0, 20.0, 200.0, 2_000.0, 20_000.0, None]})
    built = rr._symlog_scale(frames)
    assert built.kind == "symlog" and built.low > 0 and built.high > built.low
    labels = [label for _, label in built.ticks]
    assert "0" in labels and any(label.startswith("+") for label in labels) and any(label.startswith("-") for label in labels)


def _trade_run():
    """Two saves, two markets (Paris, London), one ocean pseudo-region location, a landless pretender."""
    snapshots = pl.DataFrame({"snapshot_id": ["s1", "s2"], "date": ["1337.4.1", "1347.4.1"], "year": [1337, 1347],
                              "date_sort": [13370401, 13470401], "playthrough_name": [None, None]})
    loc = {
        "slug": ["paris", "london", "atlantis"], "country_tag": ["FRA", "ENG", None], "owner": [2, 1, None],
        "market_id": [1, 2, None], "super_region": ["europe", "europe", "atlantic_ocean_continent"],
        "macro_region": ["western_europe", "british_isles", "north_atlantic_ocean_sub_continent"],
        "development": [10.0, 8.0, 0.0], "possible_tax": [5.0, 3.0, 0.0],
    }
    rows = []
    for snapshot, scale in (("s1", 1.0), ("s2", 1.5)):
        for i in range(3):
            pop = [100.0, 50.0, 1.0][i] * scale
            rows.append({"snapshot_id": snapshot, **{k: v[i] for k, v in loc.items()}, "total_population": pop,
                         "unemployed_total": pop * 0.6, "unemployed_peasants": pop * 0.4,
                         **{f"population_{p}": (pop * 0.7 if p == "peasants" else pop * 0.3 / 7) for p in rr.POP_TYPES}})
    locations = pl.DataFrame(rows)
    countries = pl.DataFrame({
        "snapshot_id": ["s1", "s1", "s2", "s2", "s2"], "country_id": [1, 2, 1, 2, 3],
        "country_tag": ["ENG", "FRA", "ENG", "FRA", "FRA"], "country_name": ["ENG", "FRA", "GBR", "FRA", "FRA"],
        "population": [50.0, 100.0, 75.0, 150.0, None], "owned_locations_count": [1, 1, 1, 1, 0],
        "gold": [1.0, 2.0, 3.0, 4.0, 0.0], "is_subject": [False] * 5, "overlord_tag": [None] * 5, "overlord_name": [None] * 5,
    })
    goods = []
    for snapshot in ("s1", "s2"):
        goods += [
            # Paris makes cloth and sends it to London; London is short of wheat
            {"snapshot_id": snapshot, "market_id": 1, "good_id": "cloth", "group": "produced", "price": 3.0, "default_price": 3.0,
             "supply": 10.0, "demand": 10.0, "production": 10.0, "imports": 0.0, "exports": 4.0, "burgher_trade": 0.0},
            {"snapshot_id": snapshot, "market_id": 2, "good_id": "cloth", "group": "produced", "price": 4.5, "default_price": 3.0,
             "supply": 4.0, "demand": 4.0, "production": 0.0, "imports": 4.0, "exports": 0.0, "burgher_trade": 0.0},
            {"snapshot_id": snapshot, "market_id": 2, "good_id": "wheat", "group": "farming", "price": 2.0, "default_price": 1.0,
             "supply": 5.0, "demand": 10.0, "production": 5.0, "imports": 0.0, "exports": 0.0, "burgher_trade": 0.0},
        ]
    market_goods = pl.DataFrame(goods)
    markets = pl.DataFrame({"snapshot_id": ["s1", "s1", "s2", "s2"], "market_id": [1, 2, 1, 2],
                            "center_slug": ["paris", "london", "paris", "london"]})
    trades = pl.DataFrame({"snapshot_id": ["s1", "s2"], "from_market": [1, 1], "to_market": [2, 2], "good_id": ["cloth", "cloth"],
                           "amount": [4.0, 4.0], "country_id": [2, 2]})
    economy = pl.DataFrame({"snapshot_id": ["s1", "s1", "s2", "s2"], "country_id": [1, 2, 1, 2],
                            "income": [10.0, 20.0, 40.0, 30.0], "expense": [5.0, 5.0, 5.0, 5.0]})
    levels = pl.DataFrame({"snapshot_id": ["s1", "s2"], "slug": ["paris", "paris"], "levels": [2.0, 3.0]})
    by_category = pl.DataFrame({"snapshot_id": ["s1", "s2"], "building_category": ["crafts"] * 2, "levels": [2.0, 3.0]})
    return rr.RunData("run", "Run", snapshots, locations, levels, by_category, countries, market_goods, markets,
                      trades, economy, rr.Labels(goods={"cloth": "Cloth", "wheat": "Wheat"}))


def test_payload_splits_peasants_filters_regions_and_ranks_countries() -> None:
    from prosper_or_perish_constructor.run_report_charts import build_payload

    payload = build_payload(_trade_run())
    charts = {c["key"]: c for c in payload["charts"]}
    stack = {s["name"]: s["data"] for s in charts["population_by_type"]["views"][0]["option"]["series"]}
    # Paris + London + the islet, last save: 226.5k people, 70 % peasants, 40 % of the people without a job
    assert stack["Subsistence peasants"][-1][1] == round(226.5 * 0.4 / 1000, 6)
    assert stack["Peasants"][-1][1] == round(226.5 * 0.3 / 1000, 6)
    assert charts["population_by_type"]["views"][0]["option"]["xAxis"]["type"] == "time"  # stacks along y
    regions = [s["name"] for s in charts["population_by_region"]["views"][0]["option"]["series"]]
    assert regions == ["Western Europe", "British Isles"]  # no ocean pseudo-region
    unemployment = {s["name"]: s["data"] for s in charts["unemployment"]["views"][0]["option"]["series"]}
    assert unemployment["World"][-1][1] == 40.0
    countries = [s["name"] for s in charts["countries_population"]["views"][0]["option"]["series"]]
    assert countries == ["Fra", "Gbr"]  # largest first, the landless pretender never counts
    income = [s["name"] for s in charts["countries_income"]["views"][0]["option"]["series"]]
    assert income == ["Gbr", "Fra"]
    goods = charts["price_heatmap"]["views"][0]["option"]["yAxis"]["data"]
    assert goods == ["Wheat", "Cloth"]  # farming before manufactured


def test_trade_tables_show_market_flows_and_routes() -> None:
    from prosper_or_perish_constructor.run_report_charts import build_payload

    tables = {t["key"]: t for t in build_payload(_trade_run())["tables"]}
    markets = tables["markets"]
    column = {c["key"]: i for i, c in enumerate(markets["columns"])}
    rows = {r[column["market"]]: r for r in markets["rows"][-1]}
    assert rows["Paris"][column["exports"]] == 12.0 and rows["Paris"][column["net"]] == 12.0
    assert rows["London"][column["imports"]] == 12.0 and rows["London"][column["top_imports"]] == "Cloth 12"
    assert rows["London"][column["top_unmet"]] == "Wheat 5.0"
    goods = tables["goods"]
    gcol = {c["key"]: i for i, c in enumerate(goods["columns"])}
    wheat = next(r for r in goods["rows"][-1] if r[gcol["good"]] == "Wheat")
    assert wheat[gcol["unmet"]] == 50.0 and wheat[gcol["short"]] == 1 and wheat[gcol["shortages"]] == "London 5.0"
    route = tables["routes"]["rows"][-1][0]
    assert route[:3] == ["Paris", "London", "Cloth"] and route[4] == 12.0


def test_trade_maps_draw_routes_over_market_borders(tmp_path: Path) -> None:
    import shutil

    import numpy as np
    import pytest

    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg missing")
    index = np.full((20, 40), -1, dtype=np.int32)
    index[4:16, 4:18] = 0  # paris
    index[4:16, 18:30] = 1  # london
    index[4:16, 30:34] = 2  # atlantis, no market
    canvas = rr.MapCanvas(index=index, tags=["paris", "london", "atlantis"], width=40, height=20,
                          tag_index={"paris": 0, "london": 1, "atlantis": 2})
    run = _trade_run()
    raster = rr._market_raster(canvas, run.locations.filter(pl.col("snapshot_id") == "s1"))
    assert raster[5, 5] == 1 and raster[5, 20] == 2 and raster[5, 31] == -1 and raster[0, 0] == -2
    borders = rr._market_borders(raster)
    assert borders[5, 18] and not borders[5, 30] and not borders[3, 5]
    maps = rr.render_trade_maps(run, canvas, tmp_path, fps=2, log=lambda _: None)
    assert [m["key"] for m in maps] == ["trade_routes", "trade_balance"]
    assert all((tmp_path / f"{m['key']}.mp4").stat().st_size > 0 for m in maps)


def test_routes_over_the_map_edge_take_the_short_way() -> None:
    import numpy as np

    base = np.zeros((20, 100, 3), dtype=np.uint8)
    # a thick route from x=95 to x=5 crosses the right edge: nothing in the middle of the map
    out = rr._draw_trade(base, [(95.0, 10.0, 1.0, 5.0, 10.0, 1.0, 4.0, (255, 255, 255, 255))], [])
    assert out[:, 40:60].max() == 0
    assert out[:, 90:].max() > 0 and out[:, :10].max() > 0


def test_page_embeds_charts_and_tables(tmp_path: Path) -> None:
    from prosper_or_perish_constructor.run_report_charts import build_payload

    run = _trade_run()
    page = rr.write_page(run, tmp_path, [], build_payload(run)).read_text(encoding="utf-8")
    assert "echarts" in page and "id=report-data" in page
    assert "Unemployment" in page and "Imported share" in page and "<h2 id=trade>" in page
    assert "NaN" not in page.split("id=report-data")[1].split("</script>")[0]
