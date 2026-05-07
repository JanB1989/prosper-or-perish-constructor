import json
from pathlib import Path

import matplotlib
import polars as pl


def test_savegame_workbench_notebook_executes_tiny_dataset(
    tmp_path: Path,
    monkeypatch,
) -> None:
    matplotlib.use("Agg")
    repo = tmp_path
    (repo / "constructor.toml").write_text('name = "test"\n', encoding="utf-8")
    _write_tiny_notebook_dataset(repo / "graphs" / "dataset")
    monkeypatch.chdir(repo)

    notebook = json.loads(
        (Path(__file__).resolve().parents[1] / "graphs" / "savegame_notebooks" / "savegame_analysis_workbench.ipynb").read_text(
            encoding="utf-8"
        )
    )
    code_sources = [
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell.get("cell_type") == "code"
    ]
    assert all("def " not in source for source in code_sources)
    assert all("matplotlib.pyplot" not in source for source in code_sources)
    namespace = {"__name__": "__notebook_smoke__"}
    for index, cell in enumerate(notebook["cells"]):
        if cell.get("cell_type") != "code":
            continue
        exec(compile("".join(cell.get("source", [])), f"cell-{index}", "exec"), namespace)

    for name in (
        "population_latest",
        "population_delta",
        "population_ts",
        "goods_global_ts",
        "market_scarcity",
        "source_breakdown",
        "sink_breakdown",
        "good_consumption_latest",
        "good_consumption_over_time",
        "food_rank",
        "food_global",
        "building_latest",
        "pm_adoption",
        "pm_slot_ts",
        "pm_usage_by_slot_over_time",
        "pm_regional_preferences_by_slot",
        "pm_values",
    ):
        assert isinstance(namespace[name], pl.DataFrame)
    assert "region_label" in namespace["population_latest"].columns
    assert "year" in namespace["population_ts"].columns
    assert "good_label" in namespace["goods_global_ts"].columns
    assert "market_label" in namespace["food_rank"].columns
    assert "building_label" in namespace["building_latest"].columns
    assert "slot_label" in namespace["pm_slot_ts"].columns
    assert "buildings" in namespace["pm_slot_ts"].columns
    assert "year" in namespace["pm_slot_ts"].columns
    assert "consumption_label" in namespace["good_consumption_latest"].columns
    assert "year" in namespace["good_consumption_over_time"].columns


def _write_tiny_notebook_dataset(root: Path) -> None:
    tables = root / "tables"
    tables.mkdir(parents=True)
    snapshot = {
        "snapshot_id": "s1",
        "playthrough_id": "aaa",
        "date": "1337.1.1",
        "year": 1337,
        "month": 1,
        "day": 1,
        "date_sort": 13370101,
        "path": "/saves/s1.eu5",
        "source_path": "/saves/s1.eu5",
        "mtime_ns": 1,
        "size": 1,
    }
    pl.DataFrame([snapshot]).write_parquet(root / "manifest.parquet")

    _write_fact(
        tables,
        "locations",
        [
            {
                **snapshot,
                "development": 1.0,
                "control": 0.8,
                "tax": 0.5,
                "total_population": 100.0,
                "market_id": 1,
                "location_id": 10,
                "slug": "london",
                "province_slug": "london_province",
                "area": "london_area",
                "region": "england",
                "macro_region": "western_europe",
                "super_region": "europe",
                "country_tag": "ENG",
            }
        ],
    )
    _write_fact(
        tables,
        "market_goods",
        [
            {
                **snapshot,
                "price": 2.0,
                "default_price": 1.5,
                "supply": 10.0,
                "demand": 8.0,
                "net": 2.0,
                "stockpile": 4.0,
                "good_id": "wheat",
                "good_name": "Wheat",
                "goods_category": "food",
                "market_id": 1,
                "market_center_slug": "london",
            }
        ],
    )
    _write_fact(
        tables,
        "market_food",
        [
            {
                **snapshot,
                "food": 50.0,
                "food_max": 100.0,
                "food_price": 1.0,
                "food_balance": 2.0,
                "population": 100.0,
                "market_id": 1,
                "center_location_id": 10,
                "market_center_slug": "london",
            }
        ],
    )
    _write_fact(
        tables,
        "buildings",
        [
            {
                **snapshot,
                "level": 1.0,
                "employment": 10.0,
                "last_months_profit": 2.0,
                "market_id": 1,
                "location_id": 10,
                "building_type": "cookery",
                "building_id": 100,
            }
        ],
    )
    _write_fact(
        tables,
        "building_methods",
        [
            {
                **snapshot,
                "market_id": 1,
                "location_id": 10,
                "building_type": "cookery",
                "building_id": 100,
                "production_method": "pm_cook",
            }
        ],
    )
    _write_fact(
        tables,
        "market_good_bucket_flows",
        [
            {
                **snapshot,
                "direction": "demand",
                "bucket": "Building",
                "save_column": "demanded_Building",
                "amount": 3.0,
                "good_id": "wheat",
                "good_name": "Wheat",
                "goods_category": "food",
                "market_id": 1,
                "market_center_slug": "london",
            }
        ],
    )
    _write_fact(
        tables,
        "rgo_flows",
        [
            {
                **snapshot,
                "raw_material": "wheat",
                "direction": "output",
                "allocated_amount": 4.0,
                "good_id": "wheat",
                "goods_category": "food",
                "market_id": 1,
                "market_center_slug": "london",
                "location_id": 10,
            }
        ],
    )
    _write_fact(
        tables,
        "production_method_good_flows",
        [
            {
                **snapshot,
                "direction": "input",
                "allocated_amount": 2.0,
                "level_sum": 1.0,
                "good_id": "wheat",
                "goods_category": "food",
                "market_id": 1,
                "market_center_slug": "london",
                "location_id": 10,
                "building_type": "cookery",
                "building_id": 100,
                "production_method": "pm_cook",
            }
        ],
    )


def _write_fact(tables: Path, table: str, rows: list[dict[str, object]]) -> None:
    path = tables / table / "playthrough_id=aaa" / "s1.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(rows, infer_schema_length=None).write_parquet(path)
