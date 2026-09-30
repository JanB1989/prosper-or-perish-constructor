import json
import subprocess
from pathlib import Path

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
