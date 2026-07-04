from __future__ import annotations

from io import BytesIO
from pathlib import Path

import numpy as np
import polars as pl
from PIL import Image

from prosper_or_perish_constructor import savegame_maps


class FakeNotebookData:
    def __init__(
        self,
        *,
        locations: pl.DataFrame,
        location_dim: pl.DataFrame,
        assets: savegame_maps.SavegameMapAssets,
        buildings: pl.DataFrame | None = None,
        countries: pl.DataFrame | None = None,
        market_food: pl.DataFrame | None = None,
        market_dim: pl.DataFrame | None = None,
        country_dim: pl.DataFrame | None = None,
    ):
        self._locations = locations
        self._location_dim = location_dim
        self._buildings = buildings if buildings is not None else pl.DataFrame()
        self._countries = countries if countries is not None else pl.DataFrame()
        self._market_food = market_food if market_food is not None else pl.DataFrame()
        self._market_dim = market_dim if market_dim is not None else pl.DataFrame()
        self._country_dim = country_dim if country_dim is not None else pl.DataFrame()
        self.map_assets = assets
        self.playthrough = "run_1"

    def table(self, name: str) -> pl.DataFrame:
        if name == "locations":
            return self._locations
        if name == "buildings":
            return self._buildings
        if name == "countries":
            return self._countries
        if name == "market_food":
            return self._market_food
        return pl.DataFrame()

    def dim(self, name: str) -> pl.DataFrame:
        if name == "locations":
            return self._location_dim
        if name == "markets":
            return self._market_dim
        if name == "countries":
            return self._country_dim
        return pl.DataFrame()


def test_population_map_delta_keeps_absolute_thousand_values(tmp_path: Path) -> None:
    data = _fake_data(tmp_path, include_missing_geometry=False)

    result = savegame_maps.population_map(
        data,
        scope="super_region",
        name="asia",
        comparison="delta",
        baseline_date=None,
        width=160,
    )

    assert len(result.frames) == 2
    assert result.baseline_date == "1342.4.1"
    assert result.mapped_locations == 2
    values = {
        (row["slug"], row["date_sort"]): row["population_delta"]
        for row in result.frame_data.select("slug", "date_sort", "population_delta").iter_rows(named=True)
    }
    assert values[("alpha", 13420401)] == 0
    assert values[("bravo", 13420401)] == 0
    assert values[("alpha", 13470401)] == 5
    assert values[("bravo", 13470401)] == -10


def test_population_map_accepts_integer_baseline_date(tmp_path: Path) -> None:
    data = _fake_data(tmp_path, include_missing_geometry=False)

    result = savegame_maps.population_map(
        data,
        scope="super_region",
        name="asia",
        comparison="delta",
        baseline_date=13470401,
        width=160,
    )

    assert result.baseline_date == "1347.4.1"
    values = {
        (row["slug"], row["date_sort"]): row["population_delta"]
        for row in result.frame_data.select("slug", "date_sort", "population_delta").iter_rows(named=True)
    }
    assert values[("alpha", 13420401)] == -5
    assert values[("bravo", 13420401)] == 10


def test_population_map_reports_missing_geometry_locations(tmp_path: Path) -> None:
    data = _fake_data(tmp_path, include_missing_geometry=True)

    result = savegame_maps.population_map(data, scope="super_region", name="asia", width=160)

    assert result.missing_geometry_locations == 1
    assert result.mapped_locations == 2


def test_population_map_current_uses_absolute_population_scale(tmp_path: Path) -> None:
    data = _fake_data(tmp_path, include_missing_geometry=False)

    result = savegame_maps.population_map(
        data,
        scope="super_region",
        name="asia",
        comparison="absolute",
        width=160,
    )

    assert len(result.frames) == 2
    assert result.comparison == "current"
    assert result.baseline_date == ""
    assert result.value_column == "population_map_value"
    assert result.value_bounds == (0.0, 2000.0)
    values = {
        (row["slug"], row["date_sort"]): row["population_map_value"]
        for row in result.frame_data.select("slug", "date_sort", "population_map_value").iter_rows(named=True)
    }
    assert values[("alpha", 13420401)] == 0.0
    assert values[("bravo", 13420401)] == 10.0
    assert values[("alpha", 13470401)] == 5.0
    assert values[("bravo", 13470401)] == 0.0


def test_population_map_current_accepts_fixed_absolute_bounds(tmp_path: Path) -> None:
    data = _fake_data(tmp_path, include_missing_geometry=False)

    result = savegame_maps.population_map(
        data,
        scope="super_region",
        name="asia",
        comparison="current",
        absolute_bounds=(0, 2000),
        width=160,
    )

    assert result.value_bounds == (0.0, 2000.0)


def test_population_map_current_preserves_actual_values_above_color_bounds(tmp_path: Path) -> None:
    base = _fake_data(tmp_path, include_missing_geometry=False)
    locations = base._locations.with_columns(
        pl.when((pl.col("location_code") == 1) & (pl.col("date_sort") == 13470401))
        .then(2500.0)
        .otherwise(pl.col("total_population"))
        .alias("total_population")
    )
    data = FakeNotebookData(
        locations=locations,
        location_dim=base._location_dim,
        assets=base.map_assets,
        buildings=base._buildings,
    )

    result = savegame_maps.population_map(
        data,
        scope="super_region",
        name="asia",
        comparison="current",
        absolute_bounds=(0, 2000),
        width=160,
    )

    value = (
        result.frame_data.filter((pl.col("slug") == "alpha") & (pl.col("date_sort") == 13470401))
        .select("population_map_value")
        .item()
    )
    assert value == 2500.0
    assert result.value_bounds == (0.0, 2000.0)


def test_population_map_current_keeps_nulls_as_no_data(tmp_path: Path) -> None:
    base = _fake_data(tmp_path, include_missing_geometry=False)
    locations = base._locations.with_columns(
        pl.when((pl.col("location_code") == 2) & (pl.col("date_sort") == 13470401))
        .then(None)
        .otherwise(pl.col("total_population"))
        .alias("total_population")
    )
    data = FakeNotebookData(
        locations=locations,
        location_dim=base._location_dim,
        assets=base.map_assets,
        buildings=base._buildings,
    )

    result = savegame_maps.population_map(data, scope="super_region", name="asia", comparison="current", width=160)
    frame = result.frame_data.filter(pl.col("date_sort") == 13470401)
    value = frame.filter(pl.col("slug") == "bravo").select("population_map_value").item()
    legend = savegame_maps._frame_legend(
        frame,
        value_column="population_map_value",
        title="Population",
        date="1347",
        unit="population_thousands",
    )
    rows = dict(legend.rows)

    assert value is None
    assert rows["Locations"] == "1"
    assert rows["No data"] == "1"
    assert rows["Total"] == "5.0k"


def test_building_levels_current_defaults_to_fixed_absolute_scale(tmp_path: Path) -> None:
    data = _fake_data(tmp_path, include_missing_geometry=False)

    result = savegame_maps.building_levels_map(data, scope="super_region", name="asia", mode="current", width=160)

    assert result.value_bounds == (0.0, 400.0)


def test_population_absolute_log_scale_maps_low_values_visibly() -> None:
    norm = savegame_maps.Log1pNorm(vmin=0.0, vmax=2000.0)

    assert float(norm(0.0)) == 0.0
    assert np.isclose(float(norm(2000.0)), 1.0)
    assert float(norm(10.0)) > 10.0 / 2000.0
    assert savegame_maps._normalize_population_absolute_scale("linear") == "linear"
    assert savegame_maps._normalize_population_absolute_scale("log") == "log1p"
    assert savegame_maps._colorbar_tick_values(norm, unit="population_thousands") == [2000.0, 1000.0, 100.0, 10.0, 0.0]


def test_population_map_name_none_renders_world(tmp_path: Path) -> None:
    data = _fake_data(tmp_path, include_missing_geometry=False)

    result = savegame_maps.population_map(data, scope="super_region", name=None, width=160)

    assert result.name == "World"
    assert result.mapped_locations == 3
    assert len(result.frames) == 2
    assert set(result.frame_data.get_column("slug").unique().to_list()) == {"alpha", "bravo", "charlie"}


def test_world_population_legend_includes_super_region_stats(tmp_path: Path) -> None:
    data = _fake_data(tmp_path, include_missing_geometry=False)
    result = savegame_maps.population_map(data, scope="super_region", name=None, comparison="delta", width=160)
    frame = result.frame_data.filter(pl.col("date_sort") == 13470401)

    legend = savegame_maps._frame_legend(
        frame,
        value_column="population_delta",
        title="Population change",
        date="1347",
        context=(("Baseline", "1342"),),
        unit="population_thousands",
        signed=True,
    )

    assert ("Asia", "-5.0k", "-2.5k", "-2.5k", "-10k", "+5.0k") in legend.region_rows
    assert ("Europe", "+10k", "+10k", "+10k", "+10k", "+10k") in legend.region_rows


def test_world_population_absolute_legend_includes_super_region_totals(tmp_path: Path) -> None:
    data = _fake_data(tmp_path, include_missing_geometry=False)
    result = savegame_maps.population_map(data, scope="super_region", name=None, comparison="current", width=160)
    frame = result.frame_data.filter(pl.col("date_sort") == 13470401)

    legend = savegame_maps._frame_legend(
        frame,
        value_column="population_map_value",
        title="Population",
        date="1347.4.1",
        unit="population_thousands",
    )

    assert ("Asia", "5.0k", "2.5k", "2.5k", "0", "5.0k") in legend.region_rows
    assert ("Europe", "30k", "30k", "30k", "30k", "30k") in legend.region_rows


def test_world_population_absolute_legend_includes_super_region_pop_distribution(tmp_path: Path) -> None:
    base = _fake_data(tmp_path, include_missing_geometry=False)
    data = FakeNotebookData(
        locations=_locations_with_population_distribution(base._locations),
        location_dim=base._location_dim,
        assets=base.map_assets,
        buildings=base._buildings,
    )
    result = savegame_maps.population_map(data, scope="super_region", name=None, comparison="current", width=160)
    frame = result.frame_data.filter(pl.col("date_sort") == 13470401)

    legend = savegame_maps._frame_legend(
        frame,
        value_column="population_map_value",
        title="Population",
        date="1347.4.1",
        unit="population_thousands",
        include_population_distribution=True,
    )

    rows = {row.region: row for row in legend.population_distribution_rows}
    asia = rows["Asia"]
    assert asia.employment == "75.0%"
    assert asia.buckets == (
        ("Slv", "5.0%", "5.0%"),
        ("Tri", "0%", "0%"),
        ("Pea", "10.0%", "30.0%"),
        ("Lab", "5.0%", "20.0%"),
        ("Sol", "0%", "0%"),
        ("Bur", "0%", "5.0%"),
        ("Clg", "0%", "0%"),
        ("Nob", "0%", "0%"),
    )
    assert savegame_maps._population_distribution_line("Unemp", asia.buckets, value_index=1) == (
        "Unemp: Slv 5.0%  Tri 0%  Pea 10.0%  Lab 5.0%  Sol 0%  Bur 0%  Clg 0%  Nob 0%"
    )


def test_world_scope_excludes_ocean_super_regions() -> None:
    frame = pl.DataFrame(
        [
            {"slug": "alpha", "super_region": "asia", "macro_region": "east_asia", "region": "north_china"},
            {
                "slug": "ocean",
                "super_region": "atlantic_ocean_continent",
                "macro_region": "north_atlantic_ocean_sub_continent",
                "region": "north_atlantic_ocean_region",
            },
            {"slug": "island", "super_region": "oceania", "macro_region": "pacific_islands", "region": "polynesia_region"},
        ]
    )

    filtered, label = savegame_maps._filter_scope(frame, "super_region", None)

    assert label == "World"
    assert filtered.get_column("slug").to_list() == ["alpha", "island"]


def test_population_map_frame_includes_legend_stats_panel(tmp_path: Path) -> None:
    data = _fake_data(tmp_path, include_missing_geometry=False)

    result = savegame_maps.population_map(data, scope="super_region", name="asia", width=160)

    image = Image.open(BytesIO(result.frames[0].png))
    assert image.width > 160
    assert image.height >= 480

    frame = result.frame_data.filter(pl.col("date_sort") == 13470401)
    legend = savegame_maps._frame_legend(
        frame,
        value_column="population_map_value",
        title="Population",
        date="1347",
        unit="population_thousands",
    )
    rows = dict(legend.rows)
    assert rows["Date"] == "1347"
    assert rows["Locations"] == "2"
    assert rows["Total"] == "5.0k"
    assert rows["Mean"] == "2.5k"
    assert rows["Median"] == "2.5k"
    assert rows["Min"] == "0"
    assert rows["Max"] == "5.0k"


def test_population_map_widget_constructs_playback_controls(tmp_path: Path) -> None:
    data = _fake_data(tmp_path, include_missing_geometry=False)
    result = savegame_maps.population_map(data, scope="super_region", name="asia", width=160)

    widget = savegame_maps.population_map_widget(result, interval_ms=250)

    assert widget is not None
    assert len(widget.children) == 4


def test_save_population_map_animation_writes_webp_and_overwrites(tmp_path: Path) -> None:
    data = _fake_data(tmp_path, include_missing_geometry=False)
    result = savegame_maps.population_map(data, scope="super_region", name="asia", width=160)
    path = tmp_path / "population_change.webp"

    first = savegame_maps.save_population_map_animation(result, path=path, duration_ms=250)
    second = savegame_maps.save_population_map_animation(result, path=path, duration_ms=500)

    assert first.path == path
    assert first.format == "webp"
    assert first.frames == 2
    assert second.path == path
    assert path.exists()
    assert path.stat().st_size > 0


def test_save_population_map_animation_can_enforce_webp_size_cap(tmp_path: Path) -> None:
    data = _fake_data(tmp_path, include_missing_geometry=False)
    result = savegame_maps.population_map(data, scope="super_region", name="asia", width=160)
    path = tmp_path / "population_current.webp"

    export = savegame_maps.save_population_map_animation(
        result,
        path=path,
        duration_ms=250,
        quality=92,
        lossless=False,
        max_bytes=1_000_000,
    )

    assert export.path == path
    assert path.stat().st_size <= 1_000_000


def test_save_population_map_animation_writes_gif_fallback(tmp_path: Path) -> None:
    data = _fake_data(tmp_path, include_missing_geometry=False)
    result = savegame_maps.population_map(data, scope="super_region", name="asia", width=160)
    path = tmp_path / "population_change.gif"

    export = savegame_maps.save_population_map_animation(result, path=path, duration_ms=250)

    assert export.path == path
    assert export.format == "gif"
    assert export.frames == 2
    assert path.exists()
    assert path.stat().st_size > 0


def test_save_map_viewer_writes_html_and_frame_files(tmp_path: Path) -> None:
    data = _fake_data(tmp_path, include_missing_geometry=False)
    result = savegame_maps.population_map(data, scope="super_region", name="asia", width=160)
    food_price = savegame_maps.food_price_map(data, scope="super_region", name="asia", width=160)
    political = savegame_maps.political_map(
        data,
        scope="super_region",
        name="asia",
        width=160,
        country_colors={"ENG": "#ff0000", "SCO": "#00ff00", "FRA": "#0000ff"},
    )
    html_path = tmp_path / "savegame_maps.html"

    export = savegame_maps.save_map_viewer(
        [("Population current", result), ("Food price current", food_price), ("Political current", political)],
        path=html_path,
        frame_dir="viewer_frames",
        width=220,
    )

    text = html_path.read_text(encoding="utf-8")
    assert export.path == html_path
    assert export.frames == 6
    assert 'id="frameSlider"' in text
    assert 'id="playButton"' in text
    assert "Population current" in text
    assert "Food price current" in text
    assert "Political current" in text
    assert len(list((tmp_path / "viewer_frames" / "population_current").glob("*.webp"))) == 2
    assert len(list((tmp_path / "viewer_frames" / "food_price_current").glob("*.webp"))) == 2
    assert len(list((tmp_path / "viewer_frames" / "political_current").glob("*.webp"))) == 2


def test_development_map_from_gamestart_uses_point_delta(tmp_path: Path) -> None:
    data = _fake_data(tmp_path, include_missing_geometry=False)

    result = savegame_maps.development_map(
        data,
        scope="super_region",
        name="asia",
        mode="from_gamestart",
        delta_bounds=(-10, 10),
        width=160,
    )

    assert len(result.frames) == 2
    assert result.mode == "from_gamestart"
    assert result.baseline_date == "1342.4.1"
    assert result.value_bounds == (-10, 10)
    values = {
        (row["slug"], row["date_sort"]): (row["development_delta"], row["development_map_value"])
        for row in result.frame_data.select("slug", "date_sort", "development_delta", "development_map_value").iter_rows(named=True)
    }
    assert values[("alpha", 13420401)] == (0.0, 0.0)
    assert values[("bravo", 13420401)] == (0.0, 0.0)
    assert values[("alpha", 13470401)] == (5.0, 5.0)
    assert values[("bravo", 13470401)] == (20.0, 10.0)


def test_development_map_current_defaults_to_global_selected_max(tmp_path: Path) -> None:
    data = _fake_data(tmp_path, include_missing_geometry=False)

    result = savegame_maps.development_map(
        data,
        scope="super_region",
        name="asia",
        mode="current",
        width=160,
    )

    assert len(result.frames) == 2
    assert result.mode == "current"
    assert result.baseline_date == ""
    assert result.value_bounds == (0.0, 100.0)
    values = {
        (row["slug"], row["date_sort"]): row["development_map_value"]
        for row in result.frame_data.select("slug", "date_sort", "development_map_value").iter_rows(named=True)
    }
    assert values[("alpha", 13420401)] == 10.0
    assert values[("bravo", 13420401)] == 80.0
    assert values[("alpha", 13470401)] == 15.0
    assert values[("bravo", 13470401)] == 100.0


def test_development_map_widget_and_export(tmp_path: Path) -> None:
    data = _fake_data(tmp_path, include_missing_geometry=False)
    result = savegame_maps.development_map(data, scope="super_region", name="asia", mode="current", width=160)

    widget = savegame_maps.development_map_widget(result, interval_ms=250)
    export = savegame_maps.save_development_map_animation(
        result,
        path=tmp_path / "development_current.webp",
        duration_ms=250,
    )

    assert widget is not None
    assert len(widget.children) == 4
    assert export.path.exists()
    assert export.frames == 2


def test_building_levels_map_from_gamestart_and_current(tmp_path: Path) -> None:
    data = _fake_data(tmp_path, include_missing_geometry=False)

    changed = savegame_maps.building_levels_map(
        data,
        scope="super_region",
        name="asia",
        mode="from_gamestart",
        delta_bounds=(-5, 5),
        width=160,
    )
    current = savegame_maps.building_levels_map(
        data,
        scope="super_region",
        name="asia",
        mode="current",
        absolute_bounds=(0, 500),
        width=160,
    )

    assert len(changed.frames) == 2
    assert changed.value_bounds == (-5, 5)
    changed_values = {
        (row["slug"], row["date_sort"]): row["building_levels_map_value"]
        for row in changed.frame_data.select("slug", "date_sort", "building_levels_map_value").iter_rows(named=True)
    }
    assert changed_values[("alpha", 13420401)] == 0.0
    assert changed_values[("alpha", 13470401)] == 3.0
    assert changed_values[("bravo", 13470401)] == 5.0
    assert len(current.frames) == 2
    assert current.value_bounds == (0.0, 500.0)
    current_values = {
        (row["slug"], row["date_sort"]): row["building_levels_map_value"]
        for row in current.frame_data.select("slug", "date_sort", "building_levels_map_value").iter_rows(named=True)
    }
    assert current_values[("alpha", 13420401)] == 2.0
    assert current_values[("bravo", 13470401)] == 8.0


def test_food_price_map_colors_locations_by_current_market_price(tmp_path: Path) -> None:
    data = _fake_data(tmp_path, include_missing_geometry=False)

    result = savegame_maps.food_price_map(
        data,
        scope="super_region",
        name="asia",
        width=160,
    )

    assert len(result.frames) == 2
    assert result.mode == "current"
    assert result.value_column == "food_price_map_value"
    assert result.value_label == "food price"
    assert result.value_bounds == savegame_maps.DEFAULT_FOOD_PRICE_BOUNDS
    values = {
        (row["slug"], row["date_sort"]): row["food_price_map_value"]
        for row in result.frame_data.select("slug", "date_sort", "food_price_map_value").iter_rows(named=True)
    }
    assert values[("alpha", 13420401)] == 0.05
    assert values[("bravo", 13420401)] == 0.15
    assert values[("alpha", 13470401)] == 0.10
    assert values[("bravo", 13470401)] == 0.20


def test_political_map_colors_locations_by_owner_country(tmp_path: Path) -> None:
    data = _fake_data(tmp_path, include_missing_geometry=False)

    result = savegame_maps.political_map(
        data,
        scope="super_region",
        name=None,
        width=160,
        country_colors={"ENG": "#ff0000", "SCO": "#00ff00", "FRA": "#0000ff"},
    )

    assert len(result.frames) == 2
    assert result.value_column == "country_color_int"
    assert result.value_label == "owner country"
    values = {
        (row["slug"], row["date_sort"]): row["country_color_int"]
        for row in result.frame_data.select("slug", "date_sort", "country_color_int").iter_rows(named=True)
    }
    assert values[("alpha", 13420401)] == 0xFF0000
    assert values[("bravo", 13420401)] == 0x00FF00
    assert values[("bravo", 13470401)] == 0xFF0000

    legend = savegame_maps._political_frame_legend(
        result.frame_data.filter(pl.col("date_sort") == 13470401),
        date="1347",
    )
    assert ("Locations", "3") in legend.rows
    assert ("Countries", "2") in legend.rows
    assert ("England", "2", "#ff0000") in legend.swatch_rows


def test_political_map_uses_formed_country_fixed_color(tmp_path: Path) -> None:
    base = _fake_data(tmp_path, include_missing_geometry=False)
    locations = base._locations.with_columns(
        pl.when((pl.col("location_code") == 2) & (pl.col("date_sort") == 13470401))
        .then(pl.lit("WOL"))
        .otherwise(pl.col("country_tag"))
        .alias("country_tag")
    )
    countries = pl.DataFrame(
        [
            {
                "snapshot_id": "s2",
                "playthrough_id": "run_1",
                "date_sort": 13470401,
                "country_tag": "WOL",
                "country_name": "PRU",
            }
        ]
    )
    data = FakeNotebookData(
        locations=locations,
        location_dim=base._location_dim,
        assets=base.map_assets,
        buildings=base._buildings,
        countries=countries,
        market_food=base._market_food,
        market_dim=base._market_dim,
    )

    result = savegame_maps.political_map(
        data,
        scope="super_region",
        name=None,
        width=160,
        country_colors={
            "ENG": "#ff0000",
            "WOL": "#00ff00",
            "PRU": "#111111",
            "FRA": "#0000ff",
        },
    )

    bravo = result.frame_data.filter(
        (pl.col("slug") == "bravo") & (pl.col("date_sort") == 13470401)
    ).row(0, named=True)
    assert bravo["country_tag"] == "WOL"
    assert bravo["current_country_name"] == "PRU"
    assert bravo["political_color_tag"] == "PRU"
    assert bravo["country_color_int"] == 0x111111


def test_political_map_resolves_encoded_country_dimension(tmp_path: Path) -> None:
    base = _fake_data(tmp_path, include_missing_geometry=False)
    locations = base._locations.drop("country_tag", "country_name").with_columns(
        pl.when(pl.col("location_code") == 3)
        .then(3)
        .when((pl.col("location_code") == 2) & (pl.col("date_sort") == 13420401))
        .then(2)
        .otherwise(1)
        .alias("country_code")
    )
    countries = pl.DataFrame(
        [
            {"country_code": 1, "country_tag": "ENG", "country_name": "England"},
            {"country_code": 2, "country_tag": "SCO", "country_name": "Scotland"},
            {"country_code": 3, "country_tag": "FRA", "country_name": "France"},
        ]
    )
    data = FakeNotebookData(
        locations=locations,
        location_dim=base._location_dim,
        assets=base.map_assets,
        buildings=base._buildings,
        market_food=base._market_food,
        market_dim=base._market_dim,
        country_dim=countries,
    )

    result = savegame_maps.political_map(
        data,
        scope="super_region",
        name="asia",
        width=160,
        country_colors={"ENG": "#ff0000", "SCO": "#00ff00", "FRA": "#0000ff"},
    )

    rows = result.frame_data.select("slug", "date_sort", "country_tag", "country_label").to_dicts()
    assert {"slug": "bravo", "date_sort": 13420401, "country_tag": "SCO", "country_label": "Scotland"} in rows
    assert {"slug": "bravo", "date_sort": 13470401, "country_tag": "ENG", "country_label": "England"} in rows


def test_political_map_tints_subjects_from_overlord_color(tmp_path: Path) -> None:
    base = _fake_data(tmp_path, include_missing_geometry=False)
    countries = pl.DataFrame(
        [
            {
                "snapshot_id": snapshot_id,
                "playthrough_id": "run_1",
                "date_sort": date_sort,
                "country_tag": "ENG",
                "country_name": "England",
                "subject_type": "",
                "overlord_tag": "",
                "overlord_name": "",
                "is_subject": False,
                "is_colony": False,
            }
            for snapshot_id, date_sort in (("s1", 13420401), ("s2", 13470401))
        ]
        + [
            {
                "snapshot_id": "s1",
                "playthrough_id": "run_1",
                "date_sort": 13420401,
                "country_tag": "SCO",
                "country_name": "Scotland",
                "subject_type": "vassal",
                "overlord_tag": "ENG",
                "overlord_name": "England",
                "is_subject": True,
                "is_colony": False,
            },
            {
                "snapshot_id": "s1",
                "playthrough_id": "run_1",
                "date_sort": 13420401,
                "country_tag": "FRA",
                "country_name": "France",
                "subject_type": "colonial_nation",
                "overlord_tag": "ENG",
                "overlord_name": "England",
                "is_subject": True,
                "is_colony": True,
            },
            {
                "snapshot_id": "s2",
                "playthrough_id": "run_1",
                "date_sort": 13470401,
                "country_tag": "FRA",
                "country_name": "France",
                "subject_type": "colonial_nation",
                "overlord_tag": "ENG",
                "overlord_name": "England",
                "is_subject": True,
                "is_colony": True,
            },
        ]
    )
    data = FakeNotebookData(
        locations=base._locations,
        location_dim=base._location_dim,
        assets=base.map_assets,
        buildings=base._buildings,
        countries=countries,
        market_food=base._market_food,
        market_dim=base._market_dim,
    )

    result = savegame_maps.political_map(
        data,
        scope="super_region",
        name=None,
        width=160,
        country_colors={"ENG": "#ff0000", "SCO": "#00ff00", "FRA": "#0000ff"},
    )

    bravo = result.frame_data.filter((pl.col("slug") == "bravo") & (pl.col("date_sort") == 13420401)).row(0, named=True)
    assert bravo["country_tag"] == "SCO"
    assert bravo["political_color_tag"] == "ENG"
    assert bravo["subject_type"] == "vassal"
    assert bravo["country_color_int"] != 0x00FF00
    assert bravo["country_color_int"] != 0xFF0000
    assert (bravo["country_color_int"] >> 16) > (bravo["country_color_int"] & 0xFF)

    legend = savegame_maps._political_frame_legend(
        result.frame_data.filter(pl.col("date_sort") == 13420401),
        date="1342",
    )
    assert ("Subjects", "2") in legend.rows
    assert ("Colonies", "1") in legend.rows
    assert any(label == "Scotland (vassal of England)" for label, _locations, _color in legend.swatch_rows)


def test_load_country_color_map_includes_formable_country_colors(tmp_path: Path) -> None:
    vanilla = tmp_path / "vanilla"
    named_colors = vanilla / "game" / "main_menu" / "common" / "named_colors"
    formables = vanilla / "game" / "in_game" / "common" / "formable_countries"
    named_colors.mkdir(parents=True)
    formables.mkdir(parents=True)
    (named_colors / "colors.txt").write_text(
        "colors = { map_PRU = rgb { 1 2 3 } }\n",
        encoding="utf-8",
    )
    (formables / "countries.txt").write_text(
        "PRU_f = { tag = PRU name = PRU flag = PRU color = map_PRU }\n",
        encoding="utf-8",
    )
    load_order = tmp_path / "load_order.toml"
    load_order.write_text(
        f'[paths]\nvanilla_root = "{vanilla.as_posix()}"\n\n[profiles]\nvanilla = ["vanilla"]\n',
        encoding="utf-8",
    )
    savegame_maps._load_country_color_map_cached.cache_clear()

    colors = savegame_maps.load_country_color_map(load_order_path=load_order, profile="vanilla")

    assert colors["PRU"] == (1, 2, 3)
    assert colors["pru"] == (1, 2, 3)


def test_show_building_levels_map_can_skip_widget_display(tmp_path: Path) -> None:
    data = _fake_data(tmp_path, include_missing_geometry=False)

    result = savegame_maps.show_building_levels_map(
        data,
        scope="super_region",
        name="asia",
        mode="current",
        width=160,
        display_widget=False,
        display_diagnostics=False,
    )

    assert result.widget is None
    assert len(result.frames) == 2


def test_load_packed_locations_uses_nearest_neighbor(tmp_path: Path) -> None:
    path = tmp_path / "locations.png"
    Image.fromarray(
        np.array(
            [
                [[255, 0, 0], [0, 255, 0]],
                [[0, 0, 255], [255, 255, 0]],
            ],
            dtype=np.uint8,
        ),
        "RGB",
    ).save(path)

    packed, source_width, source_height = savegame_maps._load_packed_locations(path, map_width=4)

    assert (source_width, source_height) == (2, 2)
    assert packed.shape == (4, 4)
    assert int(packed[0, 0]) == 0xFF0000
    assert int(packed[0, 2]) == 0x00FF00
    assert int(packed[2, 0]) == 0x0000FF
    assert int(packed[2, 2]) == 0xFFFF00


def _fake_data(tmp_path: Path, *, include_missing_geometry: bool) -> FakeNotebookData:
    assets = _fake_assets(tmp_path)
    locations = pl.DataFrame(
        [
            _location_row("s1", "1342.4.1", 13420401, 1342, 1, 0.0, development=10.0),
            _location_row("s1", "1342.4.1", 13420401, 1342, 2, 10.0, development=80.0),
            _location_row("s1", "1342.4.1", 13420401, 1342, 3, 20.0, development=25.0),
            _location_row("s2", "1347.4.1", 13470401, 1347, 1, 5.0, development=15.0),
            _location_row("s2", "1347.4.1", 13470401, 1347, 2, 0.0, development=100.0),
            _location_row("s2", "1347.4.1", 13470401, 1347, 3, 30.0, development=40.0),
        ]
        + (
            [
                _location_row("s1", "1342.4.1", 13420401, 1342, 4, 1.0, development=30.0),
                _location_row("s2", "1347.4.1", 13470401, 1347, 4, 2.0, development=35.0),
            ]
            if include_missing_geometry
            else []
        )
    )
    location_dim = pl.DataFrame(
        [
            _dim_row(1, "alpha", "asia", "Asia"),
            _dim_row(2, "bravo", "asia", "Asia"),
            _dim_row(3, "charlie", "europe", "Europe"),
        ]
        + ([_dim_row(4, "delta", "asia", "Asia")] if include_missing_geometry else [])
    )
    buildings = pl.DataFrame(
        [
            _building_row("s1", "1342.4.1", 13420401, 1342, 1, 1.0),
            _building_row("s1", "1342.4.1", 13420401, 1342, 1, 1.0),
            _building_row("s1", "1342.4.1", 13420401, 1342, 2, 1.0),
            _building_row("s2", "1347.4.1", 13470401, 1347, 1, 2.0),
            _building_row("s2", "1347.4.1", 13470401, 1347, 1, 3.0),
            _building_row("s2", "1347.4.1", 13470401, 1347, 2, 8.0),
        ]
    )
    market_food = pl.DataFrame(
        [
            _market_food_row("s1", "1342.4.1", 13420401, 1342, 10, 0.05),
            _market_food_row("s1", "1342.4.1", 13420401, 1342, 20, 0.15),
            _market_food_row("s2", "1347.4.1", 13470401, 1347, 10, 0.10),
            _market_food_row("s2", "1347.4.1", 13470401, 1347, 20, 0.20),
        ]
    )
    market_dim = pl.DataFrame(
        [
            {"market_code": 10, "market_label": "Alpha Market"},
            {"market_code": 20, "market_label": "Bravo Market"},
        ]
    )
    return FakeNotebookData(
        locations=locations,
        location_dim=location_dim,
        assets=assets,
        buildings=buildings,
        market_food=market_food,
        market_dim=market_dim,
    )


def _locations_with_population_distribution(locations: pl.DataFrame) -> pl.DataFrame:
    pop_types = ("slaves", "tribesmen", "peasants", "laborers", "soldiers", "burghers", "clergy", "nobles")
    values: dict[str, dict[tuple[int, int], float]] = {
        "total_population": {
            (1, 13470401): 60.0,
            (2, 13470401): 40.0,
            (3, 13470401): 50.0,
        },
        "rgo_employed": {
            (1, 13470401): 40.0,
            (2, 13470401): 20.0,
            (3, 13470401): 25.0,
        },
        "unemployed_total": {
            (1, 13470401): 10.0,
            (2, 13470401): 10.0,
            (3, 13470401): 25.0,
        },
        "unemployed_slaves": {(1, 13470401): 5.0},
        "employed_slaves": {(1, 13470401): 5.0},
        "unemployed_peasants": {(1, 13470401): 5.0, (2, 13470401): 5.0},
        "employed_peasants": {(1, 13470401): 20.0, (2, 13470401): 10.0},
        "unemployed_laborers": {(2, 13470401): 5.0},
        "employed_laborers": {(1, 13470401): 15.0, (2, 13470401): 5.0},
        "employed_burghers": {(2, 13470401): 5.0},
    }
    columns = ["rgo_employed", "unemployed_total"]
    columns.extend(f"{prefix}_{pop_type}" for pop_type in pop_types for prefix in ("unemployed", "employed"))

    def case_expr(column: str) -> pl.Expr:
        expr = pl.col(column).cast(pl.Float64) if column in locations.columns else pl.lit(0.0)
        for (location_code, date_sort), value in values.get(column, {}).items():
            expr = (
                pl.when((pl.col("location_code") == location_code) & (pl.col("date_sort") == date_sort))
                .then(value)
                .otherwise(expr)
            )
        return expr.alias(column)

    return locations.with_columns([case_expr("total_population"), *(case_expr(column) for column in columns)])


def _fake_assets(tmp_path: Path) -> savegame_maps.SavegameMapAssets:
    packed = np.array(
        [
            [0xFF0000, 0xFF0000, 0x00FF00, 0x00FF00],
            [0x0000FF, 0x0000FF, 0x000000, 0x000000],
        ],
        dtype=np.uint32,
    )
    geometry = pl.DataFrame(
        [
            _geometry_row("alpha", "ff0000", 0, 1, 0, 0),
            _geometry_row("bravo", "00ff00", 2, 3, 0, 0),
            _geometry_row("charlie", "0000ff", 0, 1, 1, 1),
        ]
    )
    return savegame_maps.SavegameMapAssets(
        locations_png_path=tmp_path / "locations.png",
        baseline_path=tmp_path / "baseline.parquet",
        geometry_cache_path=None,
        geometry=geometry,
        packed_locations=packed,
        map_width=4,
        map_height=2,
        source_width=4,
        source_height=2,
        scale_x=1.0,
        scale_y=1.0,
    )


def _location_row(
    snapshot_id: str,
    date: str,
    date_sort: int,
    year: int,
    location_code: int,
    population: float,
    *,
    development: float = 0.0,
    country_tag: str | None = None,
) -> dict[str, object]:
    tag = country_tag or _owner_tag(location_code, date_sort)
    return {
        "snapshot_id": snapshot_id,
        "playthrough_id": "run_1",
        "date": date,
        "date_sort": date_sort,
        "year": year,
        "location_code": location_code,
        "market_code": 10 if location_code in {1, 3, 4} else 20,
        "country_tag": tag,
        "country_name": {"ENG": "England", "SCO": "Scotland", "FRA": "France"}.get(tag, tag),
        "total_population": population,
        "development": development,
    }


def _owner_tag(location_code: int, date_sort: int) -> str:
    if location_code == 3:
        return "FRA"
    if location_code == 2 and date_sort == 13420401:
        return "SCO"
    return "ENG"


def _market_food_row(
    snapshot_id: str,
    date: str,
    date_sort: int,
    year: int,
    market_code: int,
    food_price: float,
) -> dict[str, object]:
    return {
        "snapshot_id": snapshot_id,
        "playthrough_id": "run_1",
        "date": date,
        "date_sort": date_sort,
        "year": year,
        "market_code": market_code,
        "food_price": food_price,
    }


def _building_row(snapshot_id: str, date: str, date_sort: int, year: int, location_code: int, level: float) -> dict[str, object]:
    return {
        "snapshot_id": snapshot_id,
        "playthrough_id": "run_1",
        "date": date,
        "date_sort": date_sort,
        "year": year,
        "location_code": location_code,
        "level": level,
    }


def _dim_row(location_code: int, slug: str, super_region: str, super_region_label: str) -> dict[str, object]:
    return {
        "location_code": location_code,
        "slug": slug,
        "location_label": slug.title(),
        "super_region": super_region,
        "super_region_label": super_region_label,
    }


def _geometry_row(tag: str, color: str, min_x: int, max_x: int, min_y: int, max_y: int) -> dict[str, object]:
    return {
        "location_tag": tag,
        "map_color_rgb": color,
        "geometry_status": "ok",
        "bbox_min_x": min_x,
        "bbox_max_x": max_x,
        "bbox_min_y": min_y,
        "bbox_max_y": max_y,
    }
