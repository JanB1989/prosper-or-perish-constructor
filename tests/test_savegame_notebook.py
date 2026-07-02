from __future__ import annotations

import json
from pathlib import Path
import re

import polars as pl
import pytest
from PIL import Image

from prosper_or_perish_constructor import savegame_notebook


class FakePriceData:
    playthrough = "run_1"

    def __init__(self) -> None:
        self.snapshots = pl.DataFrame(
            [
                _snapshot("s1", 1337, 1, 1),
                _snapshot("s2", 1338, 1, 1),
                _snapshot("s3", 1339, 1, 1),
            ]
        )
        self._market_food = pl.DataFrame(
            [
                _food_row("s1", 1337, 1, 1, 1, 1.0, 5.0, 10.0),
                _food_row("s2", 1338, 1, 1, 1, 3.0, 4.0, 10.0),
                _food_row("s3", 1339, 1, 1, 1, 5.0, 3.0, 10.0),
                _food_row("s1", 1337, 1, 1, 2, 2.0, 9.0, 10.0),
                _food_row("s2", 1338, 1, 1, 2, 2.0, 9.0, 10.0),
                _food_row("s3", 1339, 1, 1, 2, 2.0, 9.0, 10.0),
                _food_row("other", 1339, 1, 1, 1, 99.0, 1.0, 10.0, playthrough="other"),
            ]
        )
        self._market_goods = pl.DataFrame(
            [
                _market_good_row("s1", 1337, 1, 1, 1, "victuals", 10.0, 8.0, 2.0, 2.0, 20.0),
                _market_good_row("s2", 1338, 1, 1, 1, "victuals", 10.0, 8.0, 4.0, 2.0, 18.0),
                _market_good_row("s3", 1339, 1, 1, 1, "victuals", 10.0, 8.0, 8.0, 2.0, 16.0),
                _market_good_row("s1", 1337, 1, 1, 2, "victuals", 9.0, 8.0, 3.0, 2.0, 15.0),
                _market_good_row("s2", 1338, 1, 1, 2, "victuals", 9.0, 8.0, 3.0, 2.0, 15.0),
                _market_good_row("s3", 1339, 1, 1, 2, "victuals", 9.0, 8.0, 3.0, 2.0, 15.0),
                _market_good_row("other", 1339, 1, 1, 1, "victuals", 1.0, 0.0, 99.0, 2.0, 0.0, playthrough="other"),
            ]
        )
        self._markets = pl.DataFrame(
            [
                {"market_id": 1, "market_label": "Alpha Market"},
                {"market_id": 2, "market_label": "Beta Market"},
            ]
        )
        self._goods = pl.DataFrame([{"good_id": "victuals", "good_label": "Victuals"}])

    def table(self, name: str) -> pl.DataFrame:
        if name == "market_food":
            return self._market_food
        if name == "market_goods":
            return self._market_goods
        return pl.DataFrame()

    def dim(self, name: str) -> pl.DataFrame:
        if name == "markets":
            return self._markets
        if name == "goods":
            return self._goods
        return pl.DataFrame()


class FakeMarketCodePriceData:
    playthrough = "run_1"

    def __init__(self) -> None:
        self.snapshots = pl.DataFrame(
            [
                _snapshot("s1", 1337, 1, 1),
                _snapshot("s2", 1338, 1, 1),
                _snapshot("s3", 1339, 1, 1),
            ]
        )
        self._market_food = pl.DataFrame(
            [
                _food_code_row("s1", 1337, 1, 1, 10, 1.0, 5.0, 10.0),
                _food_code_row("s2", 1338, 1, 1, 10, 3.0, 4.0, 10.0),
                _food_code_row("s3", 1339, 1, 1, 10, 5.0, 3.0, 10.0),
                _food_code_row("s1", 1337, 1, 1, 20, 2.0, 9.0, 10.0),
                _food_code_row("s2", 1338, 1, 1, 20, 2.0, 9.0, 10.0),
                _food_code_row("s3", 1339, 1, 1, 20, 2.0, 9.0, 10.0),
            ]
        )
        self._markets = pl.DataFrame(
            [
                {"market_code": 10, "market_id": 101, "market_label": "Alpha Market"},
                {"market_code": 20, "market_id": 202, "market_label": "Beta Market"},
            ]
        )

    def table(self, name: str) -> pl.DataFrame:
        if name == "market_food":
            return self._market_food
        return pl.DataFrame()

    def dim(self, name: str) -> pl.DataFrame:
        if name == "markets":
            return self._markets
        return pl.DataFrame()


class FakeGoodsPressureData:
    playthrough = "run_1"

    def __init__(self) -> None:
        self._market_goods = pl.DataFrame(
            [
                _market_good_row("s1", 1337, 1, 1, 1, "wheat", 10.0, 20.0, 4.0, 2.0, 40.0),
                _market_good_row("s1", 1337, 1, 1, 2, "wheat", 5.0, 5.0, 2.0, 2.0, 10.0),
                _market_good_row("s1", 1337, 1, 1, 1, "stone", 30.0, 10.0, 1.0, 1.0, 100.0),
                _market_good_row("s1", 1337, 1, 1, 2, "stone", 15.0, 5.0, 1.0, 1.0, 50.0),
                _market_good_row("s1", 1337, 1, 1, 1, "food_revenue", 9999.0, 0.0, 1.0, 1.0, 0.0),
                _market_good_row("s2", 1338, 1, 1, 1, "wheat", 8.0, 24.0, 5.0, 2.0, 20.0),
                _market_good_row("s2", 1338, 1, 1, 2, "wheat", 4.0, 6.0, 3.0, 2.0, 5.0),
                _market_good_row("s2", 1338, 1, 1, 1, "stone", 20.0, 10.0, 1.0, 1.0, 75.0),
                _market_good_row("s2", 1338, 1, 1, 2, "stone", 10.0, 5.0, 1.0, 1.0, 25.0),
                _market_good_row("other", 1338, 1, 1, 1, "wheat", 100.0, 0.0, 1.0, 1.0, 0.0, playthrough="other"),
            ]
        )
        self._goods = pl.DataFrame(
            [
                {"good_id": "wheat", "good_label": "Wheat"},
                {"good_id": "stone", "good_label": "Stone"},
                {"good_id": "food_revenue", "good_label": "Food Revenue"},
            ]
        )
        self._markets = pl.DataFrame(
            [
                {"market_id": 1, "market_label": "Alpha Market"},
                {"market_id": 2, "market_label": "Beta Market"},
            ]
        )

    def table(self, name: str) -> pl.DataFrame:
        if name == "market_goods":
            return self._market_goods
        return pl.DataFrame()

    def dim(self, name: str) -> pl.DataFrame:
        if name == "goods":
            return self._goods
        if name == "markets":
            return self._markets
        return pl.DataFrame()


def test_food_price_volatility_stats_rank_erratic_markets() -> None:
    result = savegame_notebook.food_price_volatility(FakePriceData(), top_n=1)

    assert result.top_erratic["market_label"].to_list() == ["Alpha Market"]
    alpha = result.stats.filter(pl.col("market_label") == "Alpha Market").to_dicts()[0]
    beta = result.stats.filter(pl.col("market_label") == "Beta Market").to_dicts()[0]

    assert alpha["snapshots"] == 3
    assert alpha["mean_food_price"] == pytest.approx(3.0)
    assert alpha["median_food_price"] == pytest.approx(3.0)
    assert alpha["stddev_food_price"] == pytest.approx((8.0 / 3.0) ** 0.5)
    assert alpha["min_food_price"] == pytest.approx(1.0)
    assert alpha["max_food_price"] == pytest.approx(5.0)
    assert alpha["price_range"] == pytest.approx(4.0)
    assert alpha["mean_abs_price_change"] == pytest.approx(2.0)
    assert alpha["max_abs_price_change"] == pytest.approx(2.0)
    assert alpha["mean_victuals_price"] == pytest.approx(14.0 / 3.0)
    assert alpha["stddev_victuals_price"] == pytest.approx((56.0 / 9.0) ** 0.5)
    assert alpha["victuals_price_range"] == pytest.approx(6.0)
    assert alpha["mean_abs_victuals_price_change"] == pytest.approx(3.0)
    assert alpha["food_to_victuals_lag1_corr"] == pytest.approx(1.0)
    assert alpha["victuals_to_food_lag1_corr"] == pytest.approx(1.0)
    assert beta["stddev_food_price"] == pytest.approx(0.0)
    assert beta["stddev_victuals_price"] == pytest.approx(0.0)
    assert result.top_victuals_erratic["market_label"].to_list() == ["Alpha Market"]

    first_global = result.global_distribution.sort("date_sort").to_dicts()[0]
    assert first_global["mean_food_price"] == pytest.approx(1.5)
    assert first_global["median_food_price"] == pytest.approx(1.5)
    assert first_global["stddev_food_price"] == pytest.approx(0.5)
    assert first_global["mean_victuals_price"] == pytest.approx(2.5)


def test_food_price_volatility_preserves_market_identity_from_market_code() -> None:
    result = savegame_notebook.food_price_volatility(FakeMarketCodePriceData(), top_n=1)

    assert result.top_erratic["market_label"].to_list() == ["Alpha Market"]
    alpha = result.stats.filter(pl.col("market_label") == "Alpha Market").to_dicts()[0]
    beta = result.stats.filter(pl.col("market_label") == "Beta Market").to_dicts()[0]

    assert alpha["market_id"] == 101
    assert alpha["snapshots"] == 3
    assert alpha["stddev_food_price"] == pytest.approx((8.0 / 3.0) ** 0.5)
    assert beta["market_id"] == 202
    assert beta["snapshots"] == 3
    assert beta["stddev_food_price"] == pytest.approx(0.0)


def test_food_price_volatility_can_filter_one_market() -> None:
    result = savegame_notebook.food_price_volatility(FakePriceData(), market_search="alpha")

    assert result.stats["market_label"].to_list() == ["Alpha Market"]
    assert result.market_time_series["market_label"].unique().to_list() == ["Alpha Market"]


def test_save_food_price_volatility_webp_writes_static_webp(tmp_path: Path) -> None:
    result = savegame_notebook.food_price_volatility(FakePriceData(), top_n=2)

    export = savegame_notebook.save_food_price_volatility_webp(
        result,
        path=tmp_path / "food_price_volatility.webp",
        width=640,
    )

    assert export is not None
    assert export.path.is_file()
    assert export.format == "webp"
    assert export.width == 640
    with Image.open(export.path) as image:
        assert image.format == "WEBP"
        assert image.width == 640


def test_save_food_price_volatility_webp_resolves_repo_relative_output_dir_from_notebook_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    notebook_dir = repo / "graphs" / "savegame_notebooks"
    notebook_dir.mkdir(parents=True)
    (repo / "constructor.toml").write_text("", encoding="utf-8")
    monkeypatch.chdir(notebook_dir)
    result = savegame_notebook.food_price_volatility(FakePriceData(), top_n=2)

    export = savegame_notebook.save_food_price_volatility_webp(
        result,
        output_dir=Path("graphs/savegame_notebooks/exports/absolute"),
        width=320,
    )

    assert export is not None
    assert export.path == (
        repo / "graphs" / "savegame_notebooks" / "exports" / "absolute" / "food_price_volatility.webp"
    )
    assert export.path.is_file()
    assert not (notebook_dir / "graphs").exists()


def test_goods_pressure_ranks_shortages_and_selected_good_details() -> None:
    result = savegame_notebook.goods_pressure(FakeGoodsPressureData(), min_global_flow=1.0, top_n=2)

    assert result.selected_good == "wheat"
    assert result.problem_goods["good_id"].to_list()[0] == "wheat"
    assert result.global_shortages["good_id"].to_list()[0] == "wheat"
    assert "food_revenue" not in result.summary["good_id"].to_list()

    latest = result.selected_good_global.sort("date_sort").to_dicts()[-1]
    assert latest["net"] == pytest.approx(-18.0)
    assert latest["balance"] == pytest.approx(latest["net"])
    assert latest["shortage"] == pytest.approx(18.0)
    assert latest["oversupply"] == pytest.approx(0.0)
    assert latest["stockpile_months"] == pytest.approx(25.0 / 30.0)
    assert latest["price_ratio"] == pytest.approx(2.0)

    markets = result.selected_good_markets.to_dicts()
    assert markets[0]["market_label"] == "Alpha Market"
    assert markets[0]["shortage"] == pytest.approx(16.0)
    assert set(result.selected_good_market_time_series["market_label"].unique().to_list()) == {
        "Alpha Market",
        "Beta Market",
    }


def test_goods_pressure_ranks_oversupply_and_resolves_selected_label() -> None:
    result = savegame_notebook.goods_pressure(
        FakeGoodsPressureData(),
        selected_good="Stone",
        rank_mode="oversupply",
        min_global_flow=1.0,
        top_n=2,
    )

    assert result.selected_good == "stone"
    assert result.selected_good_label == "Stone"
    assert result.problem_goods["good_id"].to_list()[0] == "stone"
    latest = result.selected_good_global.sort("date_sort").to_dicts()[-1]
    assert latest["oversupply"] == pytest.approx(15.0)
    assert result.global_oversupply["good_id"].to_list()[0] == "stone"


def test_minimal_savegame_notebook_contains_goods_pressure_cell() -> None:
    notebook = Path(__file__).resolve().parents[1] / "graphs" / "savegame_notebooks" / "savegame_analysis_workbench_minimal.ipynb"
    if not notebook.exists():
        pytest.skip("generated minimal savegame notebook is not present")
    text = notebook.read_text(encoding="utf-8")
    parsed = json.loads(text)
    assert "show_goods_pressure" in text
    assert "selected_good_global" in text
    assert "food_and_victuals_prices" in text
    assert "linked_price_stats" in text
    assert "load_map_assets=True" in text
    assert "show_population(" in text
    assert "show_population_map(" in text
    assert "show_selection" not in text

    for cell in parsed["cells"]:
        if cell.get("cell_type") != "code":
            continue
        lines = [
            line.strip()
            for line in "".join(cell.get("source", [])).splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        if not lines:
            continue
        last_line = lines[-1]
        assert not re.search(r"\.tail\(", last_line), cell.get("id")
        assert not last_line.endswith(".df"), cell.get("id")
        assert last_line not in {"linked_price_stats", "selected_good_global"}, cell.get("id")


def _snapshot(snapshot_id: str, year: int, month: int, day: int) -> dict[str, object]:
    return {
        "snapshot_id": snapshot_id,
        "playthrough_id": "run_1",
        "date": f"{year}.{month}.{day}",
        "year": year,
        "month": month,
        "day": day,
        "date_sort": year * 10000 + month * 100 + day,
    }


def _food_row(
    snapshot_id: str,
    year: int,
    month: int,
    day: int,
    market_id: int,
    food_price: float,
    food: float,
    food_max: float,
    *,
    playthrough: str = "run_1",
) -> dict[str, object]:
    return {
        "snapshot_id": snapshot_id,
        "playthrough_id": playthrough,
        "date": f"{year}.{month}.{day}",
        "year": year,
        "month": month,
        "day": day,
        "date_sort": year * 10000 + month * 100 + day,
        "market_id": market_id,
        "food_price": food_price,
        "food": food,
        "food_max": food_max,
        "food_balance": food - food_max,
    }


def _food_code_row(
    snapshot_id: str,
    year: int,
    month: int,
    day: int,
    market_code: int,
    food_price: float,
    food: float,
    food_max: float,
) -> dict[str, object]:
    row = _food_row(snapshot_id, year, month, day, market_code, food_price, food, food_max)
    row["market_code"] = row.pop("market_id")
    return row


def _market_good_row(
    snapshot_id: str,
    year: int,
    month: int,
    day: int,
    market_id: int,
    good_id: str,
    supply: float,
    demand: float,
    price: float,
    default_price: float,
    stockpile: float,
    *,
    playthrough: str = "run_1",
) -> dict[str, object]:
    return {
        "snapshot_id": snapshot_id,
        "playthrough_id": playthrough,
        "date": f"{year}.{month}.{day}",
        "year": year,
        "month": month,
        "day": day,
        "date_sort": year * 10000 + month * 100 + day,
        "market_id": market_id,
        "good_id": good_id,
        "supply": supply,
        "demand": demand,
        "net": supply - demand,
        "price": price,
        "default_price": default_price,
        "stockpile": stockpile,
    }
