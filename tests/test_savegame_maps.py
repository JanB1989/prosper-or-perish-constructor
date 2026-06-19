from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
from PIL import Image

from prosper_or_perish_constructor import savegame_maps


class FakeNotebookData:
    def __init__(self, *, locations: pl.DataFrame, location_dim: pl.DataFrame, assets: savegame_maps.SavegameMapAssets):
        self._locations = locations
        self._location_dim = location_dim
        self.map_assets = assets
        self.playthrough = "run_1"

    def table(self, name: str) -> pl.DataFrame:
        if name == "locations":
            return self._locations
        return pl.DataFrame()

    def dim(self, name: str) -> pl.DataFrame:
        if name == "locations":
            return self._location_dim
        return pl.DataFrame()


def test_population_map_relative_change_is_clamped_and_handles_zero_baseline(tmp_path: Path) -> None:
    data = _fake_data(tmp_path, include_missing_geometry=False)

    result = savegame_maps.population_map(
        data,
        scope="super_region",
        name="asia",
        baseline_date=None,
        width=160,
    )

    assert len(result.frames) == 2
    assert result.baseline_date == "1342.4.1"
    assert result.mapped_locations == 2
    values = {
        (row["slug"], row["date_sort"]): row["relative_change_pct"]
        for row in result.frame_data.select("slug", "date_sort", "relative_change_pct").iter_rows(named=True)
    }
    assert values[("alpha", 13420401)] == 0
    assert values[("bravo", 13420401)] == 0
    assert values[("alpha", 13470401)] == 300
    assert values[("bravo", 13470401)] == -100


def test_population_map_accepts_integer_baseline_date(tmp_path: Path) -> None:
    data = _fake_data(tmp_path, include_missing_geometry=False)

    result = savegame_maps.population_map(
        data,
        scope="super_region",
        name="asia",
        baseline_date=13470401,
        width=160,
    )

    assert result.baseline_date == "1347.4.1"
    values = {
        (row["slug"], row["date_sort"]): row["relative_change_pct"]
        for row in result.frame_data.select("slug", "date_sort", "relative_change_pct").iter_rows(named=True)
    }
    assert values[("alpha", 13420401)] == -100
    assert values[("bravo", 13420401)] == 300


def test_population_map_reports_missing_geometry_locations(tmp_path: Path) -> None:
    data = _fake_data(tmp_path, include_missing_geometry=True)

    result = savegame_maps.population_map(data, scope="super_region", name="asia", width=160)

    assert result.missing_geometry_locations == 1
    assert result.mapped_locations == 2


def test_population_map_widget_constructs_playback_controls(tmp_path: Path) -> None:
    data = _fake_data(tmp_path, include_missing_geometry=False)
    result = savegame_maps.population_map(data, scope="super_region", name="asia", width=160)

    widget = savegame_maps.population_map_widget(result, interval_ms=250)

    assert widget is not None
    assert len(widget.children) == 4


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
            _location_row("s1", "1342.4.1", 13420401, 1342, 1, 0.0),
            _location_row("s1", "1342.4.1", 13420401, 1342, 2, 10.0),
            _location_row("s1", "1342.4.1", 13420401, 1342, 3, 20.0),
            _location_row("s2", "1347.4.1", 13470401, 1347, 1, 5.0),
            _location_row("s2", "1347.4.1", 13470401, 1347, 2, 0.0),
            _location_row("s2", "1347.4.1", 13470401, 1347, 3, 30.0),
        ]
        + (
            [
                _location_row("s1", "1342.4.1", 13420401, 1342, 4, 1.0),
                _location_row("s2", "1347.4.1", 13470401, 1347, 4, 2.0),
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
    return FakeNotebookData(locations=locations, location_dim=location_dim, assets=assets)


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


def _location_row(snapshot_id: str, date: str, date_sort: int, year: int, location_code: int, population: float) -> dict[str, object]:
    return {
        "snapshot_id": snapshot_id,
        "playthrough_id": "run_1",
        "date": date,
        "date_sort": date_sort,
        "year": year,
        "location_code": location_code,
        "total_population": population,
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
