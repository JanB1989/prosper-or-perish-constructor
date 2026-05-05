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
    _write_tiny_notebook_dataset(repo / "graphs" / "savegame_notebooks" / "data")
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
        "pm_slot_latest",
        "pm_slot_ts",
        "pm_latest_distribution_by_slot",
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
    assert "slot_label" in namespace["pm_slot_latest"].columns
    assert "year" in namespace["pm_slot_ts"].columns
    assert "consumption_label" in namespace["good_consumption_latest"].columns
    assert "year" in namespace["good_consumption_over_time"].columns


def _write_tiny_notebook_dataset(root: Path) -> None:
    dims = root / "dims"
    facts = root / "facts"
    dims.mkdir(parents=True)
    facts.mkdir()
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
    pl.DataFrame([snapshot]).write_parquet(root / "snapshots.parquet")
    pl.DataFrame(
        [
            {
                "good_code": 0,
                "good_id": "wheat",
                "good_label": "Wheat",
                "goods_category": "food",
            }
        ]
    ).write_parquet(dims / "goods.parquet")
    pl.DataFrame(
        [
            {
                "market_code": 0,
                "market_id": 1,
                "center_location_id": 10,
                "market_center_slug": "london",
                "market_label": "London",
            }
        ]
    ).write_parquet(dims / "markets.parquet")
    pl.DataFrame(
        [
            {
                "location_code": 0,
                "location_id": 10,
                "slug": "london",
                "location_label": "London",
                "province_slug": "london_province",
                "area": "london_area",
                "area_label": "London Area",
                "region": "england",
                "region_label": "England",
                "macro_region": "western_europe",
                "macro_region_label": "Western Europe",
                "super_region": "europe",
                "super_region_label": "Europe",
                "country_tag": "ENG",
                "country_label": "England",
            }
        ]
    ).write_parquet(dims / "locations.parquet")
    pl.DataFrame([{"country_code": 0, "country_tag": "ENG", "country_label": "England"}]).write_parquet(dims / "countries.parquet")
    pl.DataFrame([{"building_type_code": 0, "building_type": "cookery", "building_label": "Cookery"}]).write_parquet(dims / "building_types.parquet")
    pl.DataFrame(
        [
            {
                "production_method_code": 0,
                "production_method": "pm_cook",
                "production_method_label": "Cooking",
                "production_method_building": "cookery",
                "production_method_group": "cookery:0",
                "production_method_group_index": 0,
                "slot_label": "Slot 1",
            }
        ]
    ).write_parquet(dims / "production_methods.parquet")

    _write_fact(
        facts,
        "locations",
        [
            {
                **snapshot,
                "development": 1.0,
                "control": 0.8,
                "tax": 0.5,
                "total_population": 100.0,
                "market_code": 0,
                "location_code": 0,
                "region_code": 0,
            }
        ],
    )
    _write_fact(
        facts,
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
                "good_code": 0,
                "market_code": 0,
            }
        ],
    )
    _write_fact(
        facts,
        "market_food",
        [
            {
                **snapshot,
                "food": 50.0,
                "food_max": 100.0,
                "food_price": 1.0,
                "food_balance": 2.0,
                "population": 100.0,
                "market_code": 0,
            }
        ],
    )
    _write_fact(
        facts,
        "buildings",
        [
            {
                **snapshot,
                "level": 1.0,
                "employment": 10.0,
                "last_months_profit": 2.0,
                "market_code": 0,
                "location_code": 0,
                "building_type_code": 0,
                "building_code": 0,
            }
        ],
    )
    _write_fact(
        facts,
        "building_methods",
        [
            {
                **snapshot,
                "market_code": 0,
                "location_code": 0,
                "building_type_code": 0,
                "building_code": 0,
                "production_method_code": 0,
            }
        ],
    )
    _write_good_fact(
        facts,
        "market_good_bucket_flows",
        [
            {
                **snapshot,
                "direction": "demand",
                "bucket": "Building",
                "save_column": "demanded_Building",
                "amount": 3.0,
                "good_code": 0,
                "market_code": 0,
            }
        ],
    )
    _write_good_fact(
        facts,
        "rgo_flows",
        [
            {
                **snapshot,
                "raw_material": "wheat",
                "direction": "output",
                "allocated_amount": 4.0,
                "good_code": 0,
                "market_code": 0,
                "location_code": 0,
            }
        ],
    )
    _write_good_fact(
        facts,
        "production_method_good_flows",
        [
            {
                **snapshot,
                "direction": "input",
                "allocated_amount": 2.0,
                "level_sum": 1.0,
                "good_code": 0,
                "market_code": 0,
                "location_code": 0,
                "building_type_code": 0,
                "building_code": 0,
                "production_method_code": 0,
            }
        ],
    )


def _write_fact(facts: Path, table: str, rows: list[dict[str, object]]) -> None:
    path = facts / table / "playthrough_id=aaa" / "s1.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(rows, infer_schema_length=None).write_parquet(path)


def _write_good_fact(facts: Path, table: str, rows: list[dict[str, object]]) -> None:
    path = facts / table / "playthrough_id=aaa" / "good_code=0" / "s1.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(rows, infer_schema_length=None).write_parquet(path)
