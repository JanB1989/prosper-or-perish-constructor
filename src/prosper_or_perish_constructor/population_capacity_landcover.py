"""LUH2/PNV source extraction and location-capacity land-cover bridge.

The official LUH2 historical state file is more than six gigabytes.  This
module reads it through HTTP byte ranges and freezes only the requested annual
slice.  Ordinary builds consume the frozen slice and never access the network.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path
import tarfile
from typing import Any

import h5py
import numpy as np
import polars as pl
import requests
from scipy.io import netcdf_file
import urllib3


LANDCOVER_SCHEMA_VERSION = "pp-location-landcover-capacity-v1"
LUH2_DATASET = "LUH2 v2h baseline"
LUH2_URL = "https://luh.umd.edu/LUH2/LUH2_v2h/states.nc"
LUH2_CONTENT_LENGTH = 6_212_694_984
LUH2_ETAG = '"1724e33c8-53ec386d1e240"'
LUH2_START_YEAR = 850
LUH2_END_YEAR = 2015
LUH2_VARIABLES = (
    "primf",
    "primn",
    "secdf",
    "secdn",
    "urban",
    "c3ann",
    "c4ann",
    "c3per",
    "c4per",
    "c3nfx",
    "pastr",
    "range",
)
PNV_URL = (
    "https://sage-public-files.s3.amazonaws.com/global-potential-vegetation/"
    "potveg_nc.tar.gz"
)
PNV_ARCHIVE_SHA256 = "d4d98a15c9da9bba88a17f037fedf239b37da17d917081ea2320d8748cd0b70a"
PNV_FOREST_CLASSES = frozenset(range(1, 9))


@dataclass(frozen=True)
class LandcoverPaths:
    root: Path
    luh2_slice: Path
    pnv_archive: Path
    pnv_netcdf: Path
    source_manifest: Path


def landcover_paths(root: Path) -> LandcoverPaths:
    root = Path(root)
    return LandcoverPaths(
        root=root,
        luh2_slice=root / "luh2" / "states_1300_v2.npz",
        pnv_archive=root / "sage_pnv" / "potveg_nc.tar.gz",
        pnv_netcdf=root / "sage_pnv" / "vegtype_5min.nc",
        source_manifest=root / "landcover_source_manifest.json",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class _HttpRangeReader(io.RawIOBase):
    """Seekable cached reader used by h5py's file-object driver."""

    def __init__(
        self,
        url: str,
        *,
        size: int,
        block_size: int = 8 * 1024 * 1024,
        verify_tls: bool = True,
    ) -> None:
        super().__init__()
        self.url = url
        self.size = int(size)
        self.block_size = int(block_size)
        self.verify_tls = verify_tls
        self.position = 0
        self.session = requests.Session()
        self._blocks: dict[int, bytes] = {}

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.position

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_SET:
            position = offset
        elif whence == io.SEEK_CUR:
            position = self.position + offset
        elif whence == io.SEEK_END:
            position = self.size + offset
        else:
            raise ValueError(f"unsupported seek mode: {whence}")
        if position < 0:
            raise ValueError("negative seek position")
        self.position = min(int(position), self.size)
        return self.position

    def _block(self, block_index: int) -> bytes:
        cached = self._blocks.get(block_index)
        if cached is not None:
            return cached
        start = block_index * self.block_size
        stop = min(self.size, start + self.block_size) - 1
        response = self.session.get(
            self.url,
            headers={"Range": f"bytes={start}-{stop}"},
            timeout=120,
            verify=self.verify_tls,
        )
        response.raise_for_status()
        expected = stop - start + 1
        if len(response.content) != expected:
            raise ValueError(
                f"range response length mismatch for {start}-{stop}: "
                f"expected {expected}, got {len(response.content)}"
            )
        self._blocks[block_index] = response.content
        return response.content

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = self.size - self.position
        remaining = min(int(size), self.size - self.position)
        output = bytearray()
        while remaining > 0:
            block_index = self.position // self.block_size
            offset = self.position % self.block_size
            block = self._block(block_index)
            take = min(remaining, len(block) - offset)
            if take <= 0:
                break
            output.extend(block[offset : offset + take])
            self.position += take
            remaining -= take
        return bytes(output)

    def readinto(self, buffer: Any) -> int:
        data = self.read(len(buffer))
        buffer[: len(data)] = data
        return len(data)


def _download(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".part")
    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        with temporary.open("wb") as handle:
            for block in response.iter_content(1024 * 1024):
                if block:
                    handle.write(block)
    temporary.replace(target)


def _fetch_pnv(paths: LandcoverPaths) -> dict[str, Any]:
    if not paths.pnv_archive.is_file():
        _download(PNV_URL, paths.pnv_archive)
    archive_hash = _sha256(paths.pnv_archive)
    if archive_hash != PNV_ARCHIVE_SHA256:
        raise ValueError(
            "SAGE PNV archive checksum mismatch: "
            f"expected {PNV_ARCHIVE_SHA256}, got {archive_hash}"
        )
    if not paths.pnv_netcdf.is_file():
        paths.pnv_netcdf.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(paths.pnv_archive, "r:gz") as archive:
            member = archive.getmember("vegtype_5min.nc")
            source = archive.extractfile(member)
            if source is None:
                raise ValueError("SAGE archive does not contain vegtype_5min.nc")
            temporary = paths.pnv_netcdf.with_suffix(".nc.part")
            with source, temporary.open("wb") as output:
                while block := source.read(1024 * 1024):
                    output.write(block)
            temporary.replace(paths.pnv_netcdf)
    return {
        "url": PNV_URL,
        "archive_sha256": archive_hash,
        "netcdf_sha256": _sha256(paths.pnv_netcdf),
        "forest_classes": sorted(PNV_FOREST_CLASSES),
    }


def _fetch_luh2_slice(paths: LandcoverPaths, *, year: int) -> dict[str, Any]:
    if not LUH2_START_YEAR <= year <= LUH2_END_YEAR:
        raise ValueError(
            f"LUH2 year must be in {LUH2_START_YEAR}..{LUH2_END_YEAR}: {year}"
        )
    target = (
        paths.luh2_slice
        if year == 1300
        else paths.luh2_slice.with_name(f"states_{year}_v2.npz")
    )
    if not target.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        # The official LUH2 host currently serves an incomplete TLS chain.
        # Integrity is captured by the immutable ETag, byte length, and frozen
        # extracted-slice hash rather than silently downloading the whole file.
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        reader = _HttpRangeReader(
            LUH2_URL,
            size=LUH2_CONTENT_LENGTH,
            verify_tls=False,
        )
        with h5py.File(reader, "r") as source:
            expected_shape = (LUH2_END_YEAR - LUH2_START_YEAR + 1, 720, 1440)
            if tuple(source["primf"].shape) != expected_shape:
                raise ValueError(
                    f"unexpected LUH2 state shape: {source['primf'].shape}"
                )
            year_index = year - LUH2_START_YEAR
            payload: dict[str, np.ndarray] = {
                "lat": np.asarray(source["lat"][:], dtype=np.float64),
                "lon": np.asarray(source["lon"][:], dtype=np.float64),
                "year": np.asarray([year], dtype=np.int32),
            }
            for variable in LUH2_VARIABLES:
                values = np.asarray(source[variable][year_index], dtype=np.float32)
                invalid = ~np.isfinite(values) | (values < 0.0) | (values > 1.0)
                values[invalid] = 0.0
                payload[variable] = values
        temporary = target.with_suffix(".npz.part")
        with temporary.open("wb") as handle:
            np.savez_compressed(handle, **payload)
        temporary.replace(target)
    paths = LandcoverPaths(
        root=paths.root,
        luh2_slice=target,
        pnv_archive=paths.pnv_archive,
        pnv_netcdf=paths.pnv_netcdf,
        source_manifest=paths.source_manifest,
    )
    with np.load(paths.luh2_slice) as frozen:
        frozen_year = int(frozen["year"][0])
        variables = sorted(name for name in frozen.files if name not in {"lat", "lon", "year"})
    if frozen_year != year or variables != sorted(LUH2_VARIABLES):
        raise ValueError("frozen LUH2 slice does not match the requested source contract")
    return {
        "dataset": LUH2_DATASET,
        "url": LUH2_URL,
        "content_length": LUH2_CONTENT_LENGTH,
        "etag": LUH2_ETAG,
        "year": year,
        "variables": variables,
        "slice_path": str(paths.luh2_slice),
        "slice_sha256": _sha256(paths.luh2_slice),
        "tls_verification": "disabled_for_official_host_incomplete_chain",
    }


def fetch_landcover_sources(root: Path, *, year: int = 1300) -> dict[str, Any]:
    """Fetch and freeze the explicit LUH2 year slice and SAGE PNV source."""

    paths = landcover_paths(root)
    pnv = _fetch_pnv(paths)
    luh2 = _fetch_luh2_slice(paths, year=year)
    manifest = {
        "schema_version": LANDCOVER_SCHEMA_VERSION,
        "luh2": luh2,
        "sage_pnv": pnv,
    }
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.source_manifest.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _regular_grid_indices(values: np.ndarray, coordinates: np.ndarray) -> np.ndarray:
    coordinates = np.asarray(coordinates, dtype=np.float64)
    values = np.asarray(values, dtype=np.float64)
    if coordinates.size < 2:
        raise ValueError("regular grid requires at least two coordinates")
    step = float(coordinates[1] - coordinates[0])
    if step == 0.0:
        raise ValueError("regular grid has a zero coordinate step")
    indices = np.rint((values - coordinates[0]) / step).astype(np.int64)
    return np.clip(indices, 0, coordinates.size - 1)


def _load_pnv(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    with netcdf_file(path, "r", mmap=False) as source:
        latitude = np.asarray(source.variables["latitude"][:], dtype=np.float64)
        longitude = np.asarray(source.variables["longitude"][:], dtype=np.float64)
        vegetation = np.asarray(source.variables["vegtype"][0, 0], dtype=np.float32)
    return latitude, longitude, vegetation


def _aligned_pnv_forest_share(
    pnv_forest: np.ndarray,
    pnv_lat: np.ndarray,
    pnv_lon: np.ndarray,
    luh_lat: np.ndarray,
    luh_lon: np.ndarray,
) -> np.ndarray:
    aligned = pnv_forest
    if np.sign(pnv_lat[1] - pnv_lat[0]) != np.sign(luh_lat[1] - luh_lat[0]):
        aligned = aligned[::-1]
        pnv_lat = pnv_lat[::-1]
    if np.sign(pnv_lon[1] - pnv_lon[0]) != np.sign(luh_lon[1] - luh_lon[0]):
        aligned = aligned[:, ::-1]
        pnv_lon = pnv_lon[::-1]
    if aligned.shape != (luh_lat.size * 3, luh_lon.size * 3):
        raise ValueError(
            "SAGE PNV and LUH2 grids do not have the expected 3:1 alignment: "
            f"{aligned.shape} versus {(luh_lat.size, luh_lon.size)}"
        )
    grouped = aligned.reshape(luh_lat.size, 3, luh_lon.size, 3)
    return grouped.mean(axis=(1, 3), dtype=np.float64)


def _placed_forest_fraction(
    historical_forest: np.ndarray,
    potential_forest: np.ndarray,
    coarse_potential_share: np.ndarray,
) -> np.ndarray:
    historical = np.clip(historical_forest, 0.0, 1.0)
    coarse = np.clip(coarse_potential_share, 0.0, 1.0)
    potential = np.clip(potential_forest, 0.0, 1.0)
    on_potential = np.divide(
        historical,
        coarse,
        out=np.zeros_like(historical),
        where=coarse > 1e-12,
    )
    outside_potential = np.divide(
        historical - coarse,
        1.0 - coarse,
        out=np.zeros_like(historical),
        where=coarse < 1.0 - 1e-12,
    )
    return np.where(
        historical <= coarse,
        potential * np.clip(on_potential, 0.0, 1.0),
        potential + (1.0 - potential) * np.clip(outside_potential, 0.0, 1.0),
    )


def _load_crop_yield_indices(
    *,
    crop_samples_root: Path,
    crop_labels_path: Path,
) -> pl.DataFrame:
    """Resolve the best historically available rainfed yield at every sample."""

    sample_paths = sorted(Path(crop_samples_root).glob("*_rainfed.parquet"))
    if not sample_paths:
        raise FileNotFoundError(
            f"no GAEZ rainfed sample parquets found under {crop_samples_root}"
        )
    history = (
        pl.scan_parquet(crop_labels_path)
        .filter(pl.col("water_mode") == "rainfed")
        .group_by("location_tag", "crop")
        .agg(
            *(
                pl.col(f"historical_availability_{quantile}")
                .max()
                .fill_null(0.0)
                .clip(0.0, 1.0)
                .alias(f"_availability_{quantile}")
                for quantile in ("p10", "p50", "p90")
            )
        )
    )
    yields = pl.concat(
        [
            pl.scan_parquet(path).select(
                "location_tag",
                "sample_index",
                "crop",
                pl.col("production_density_kg_dm_total_ha")
                .cast(pl.Float64)
                .fill_null(0.0)
                .clip(lower_bound=0.0)
                .alias("_production_density"),
                pl.col("sample_is_land").fill_null(False),
            )
            for path in sample_paths
        ],
        how="vertical_relaxed",
    )
    return (
        yields.join(history, on=["location_tag", "crop"], how="left")
        .with_columns(
            *(
                (
                    pl.col("_production_density")
                    * pl.col(f"_availability_{quantile}").fill_null(0.0)
                ).alias(f"_crop_yield_index_{quantile}")
                for quantile in ("p10", "p50", "p90")
            )
        )
        .group_by("location_tag", "sample_index")
        .agg(
            *(
                pl.col(f"_crop_yield_index_{quantile}")
                .max()
                .alias(f"crop_yield_index_{quantile}")
                for quantile in ("p10", "p50", "p90")
            ),
            pl.col("sample_is_land").any().alias("sample_is_land"),
        )
        .collect()
    )


def build_landcover_capacity_artifact(
    *,
    source_root: Path,
    sample_points_path: Path,
    crop_samples_root: Path,
    crop_labels_path: Path,
    candidates_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    """Intersect LUH2/PNV and GAEZ suitability before location aggregation."""

    paths = landcover_paths(source_root)
    crop_sample_paths = sorted(Path(crop_samples_root).glob("*_rainfed.parquet"))
    required = (
        paths.source_manifest,
        paths.luh2_slice,
        paths.pnv_netcdf,
        sample_points_path,
        crop_labels_path,
        candidates_path,
    )
    missing = [str(path) for path in required if not Path(path).is_file()]
    if missing:
        raise FileNotFoundError("missing landcover build inputs: " + ", ".join(missing))
    if not crop_sample_paths:
        raise FileNotFoundError(
            f"no GAEZ rainfed sample parquets found under {crop_samples_root}"
        )

    manifest = json.loads(paths.source_manifest.read_text(encoding="utf-8"))
    if _sha256(paths.luh2_slice) != manifest["luh2"]["slice_sha256"]:
        raise ValueError("LUH2 slice does not match its source manifest")
    if _sha256(paths.pnv_netcdf) != manifest["sage_pnv"]["netcdf_sha256"]:
        raise ValueError("SAGE PNV NetCDF does not match its source manifest")

    with np.load(paths.luh2_slice) as source:
        luh = {name: np.asarray(source[name]) for name in source.files}
    pnv_lat, pnv_lon, pnv_vegetation = _load_pnv(paths.pnv_netcdf)
    pnv_classes = np.where(
        np.isfinite(pnv_vegetation) & (np.abs(pnv_vegetation) < 1_000.0),
        np.rint(pnv_vegetation),
        -9999.0,
    ).astype(np.int16)
    pnv_forest_grid = np.isin(
        pnv_classes,
        np.asarray(sorted(PNV_FOREST_CLASSES), dtype=np.int16),
    ).astype(np.float64)
    pnv_coarse_share = _aligned_pnv_forest_share(
        pnv_forest_grid,
        pnv_lat,
        pnv_lon,
        luh["lat"],
        luh["lon"],
    )

    sample_source = pl.read_parquet(sample_points_path)
    longitude_column = (
        "physical_sample_lon"
        if "physical_sample_lon" in sample_source.columns
        else "calibrated_lon"
    )
    latitude_column = (
        "physical_sample_lat"
        if "physical_sample_lat" in sample_source.columns
        else "calibrated_lat"
    )
    crop_yields = _load_crop_yield_indices(
        crop_samples_root=crop_samples_root,
        crop_labels_path=crop_labels_path,
    )
    samples = (
        sample_source.select(
            "location_tag",
            "sample_index",
            pl.col(longitude_column).alias("physical_lon"),
            pl.col(latitude_column).alias("physical_lat"),
            "sample_weight",
        )
        .join(crop_yields, on=["location_tag", "sample_index"], how="left")
        .with_columns(
            *(pl.col(f"crop_yield_index_{quantile}").fill_null(0.0) for quantile in ("p10", "p50", "p90")),
            pl.col("sample_is_land").fill_null(False),
        )
    )
    latitude = samples["physical_lat"].to_numpy()
    longitude = samples["physical_lon"].to_numpy()
    luh_y = _regular_grid_indices(latitude, luh["lat"])
    luh_x = _regular_grid_indices(longitude, luh["lon"])
    pnv_y = _regular_grid_indices(latitude, pnv_lat)
    pnv_x = _regular_grid_indices(longitude, pnv_lon)

    primary_forest = luh["primf"][luh_y, luh_x].astype(np.float64)
    secondary_forest = luh["secdf"][luh_y, luh_x].astype(np.float64)
    historical_forest = np.clip(primary_forest + secondary_forest, 0.0, 1.0)
    potential_forest = pnv_forest_grid[pnv_y, pnv_x]
    coarse_potential = pnv_coarse_share[luh_y, luh_x]
    placed_forest = _placed_forest_fraction(
        historical_forest,
        potential_forest,
        coarse_potential,
    )
    pasture = np.clip(luh["pastr"][luh_y, luh_x], 0.0, 1.0).astype(np.float64)
    cropland = np.clip(
        luh["c3ann"][luh_y, luh_x]
        + luh["c4ann"][luh_y, luh_x]
        + luh["c3per"][luh_y, luh_x]
        + luh["c4per"][luh_y, luh_x]
        + luh["c3nfx"][luh_y, luh_x],
        0.0,
        1.0,
    ).astype(np.float64)
    urban = np.clip(luh["urban"][luh_y, luh_x], 0.0, 1.0).astype(np.float64)
    managed = np.clip(
        urban + cropland + pasture,
        0.0,
        1.0,
    ).astype(np.float64)
    rangeland = np.clip(luh["range"][luh_y, luh_x], 0.0, 1.0).astype(np.float64)
    open_natural = np.clip(
        luh["primn"][luh_y, luh_x] + luh["secdn"][luh_y, luh_x],
        0.0,
        1.0,
    ).astype(np.float64)

    samples = samples.with_columns(
        pl.Series("_primary_forest", primary_forest),
        pl.Series("_secondary_forest", secondary_forest),
        pl.Series("_historical_forest", historical_forest),
        pl.Series("_placed_forest", placed_forest),
        pl.Series("_potential_forest", potential_forest),
        pl.Series("_managed", managed),
        pl.Series("_cropland", cropland),
        pl.Series("_urban", urban),
        pl.Series("_pasture", pasture),
        pl.Series("_rangeland", rangeland),
        pl.Series("_open_natural", open_natural),
    )
    weighted_columns = (
        "_primary_forest",
        "_secondary_forest",
        "_historical_forest",
        "_placed_forest",
        "_potential_forest",
        "_managed",
        "_cropland",
        "_urban",
        "_pasture",
        "_rangeland",
        "_open_natural",
    )
    aggregate_expressions: list[pl.Expr] = [
        pl.col("sample_weight").sum().alias("_weight"),
        pl.col("sample_is_land").cast(pl.Float64).mean().alias("_sample_coverage"),
    ]
    for quantile in ("p10", "p50", "p90"):
        yield_weight = pl.col("sample_weight") * pl.col(
            f"crop_yield_index_{quantile}"
        )
        aggregate_expressions.extend(
            (
                yield_weight.sum().alias(f"_crop_yield_weight_{quantile}"),
                (yield_weight * pl.col("_placed_forest"))
                .sum()
                .alias(f"_forest_crop_yield_weight_{quantile}"),
            )
        )
    aggregate_expressions.extend(
        (pl.col("sample_weight") * pl.col(column)).sum().alias(f"{column}_weighted")
        for column in weighted_columns
    )
    location = samples.group_by("location_tag").agg(*aggregate_expressions).with_columns(
        pl.col("_sample_coverage").fill_null(0.0).alias(
            "landcover_coverage_fraction"
        ),
        *(
            pl.when(pl.col(f"_crop_yield_weight_{quantile}") > 0.0)
            .then(
                pl.col(f"_forest_crop_yield_weight_{quantile}")
                / pl.col(f"_crop_yield_weight_{quantile}")
            )
            .otherwise(0.0)
            .clip(0.0, 1.0)
            .alias(f"forest_crop_yield_share_{quantile}")
            for quantile in ("p10", "p50", "p90")
        ),
        *(
            pl.when(pl.col("_weight") > 0.0)
            .then(pl.col(f"{column}_weighted") / pl.col("_weight"))
            .otherwise(0.0)
            .clip(0.0, 1.0)
            .alias(
                {
                    "_primary_forest": "primary_forest_fraction_1300",
                    "_secondary_forest": "secondary_forest_fraction_1300",
                    "_historical_forest": "luh2_forest_fraction_1300",
                    "_placed_forest": "forest_fraction_1300",
                    "_potential_forest": "potential_forest_fraction",
                    "_managed": "managed_land_fraction_1300",
                    "_cropland": "cropland_fraction_1300",
                    "_urban": "urban_fraction_1300",
                    "_pasture": "pasture_fraction_1300",
                    "_rangeland": "rangeland_fraction_1300",
                    "_open_natural": "open_natural_fraction_1300",
                }[column]
            )
            for column in weighted_columns
        ),
    ).with_columns(
        pl.col("forest_crop_yield_share_p50").alias(
            "forest_crop_suitability_share"
        ),
        (1.0 - pl.col("forest_crop_yield_share_p50"))
        .clip(0.0, 1.0)
        .alias("open_crop_suitability_share"),
        pl.col("open_natural_fraction_1300").alias(
            "luh2_nonforest_fraction_1300"
        ),
        pl.col("forest_fraction_1300").alias("allocated_woodland_fraction"),
    )

    candidates = pl.read_parquet(candidates_path)
    needed = {
        "location_tag",
        "area_km2",
        *(f"rainfed_crop_capacity_people_{q}" for q in ("p10", "p50", "p90")),
        *(f"livestock_capacity_people_{q}" for q in ("p10", "p50", "p90")),
        *(f"wild_capacity_people_{q}" for q in ("p10", "p50", "p90")),
        *(f"wild_density_people_per_km2_{q}" for q in ("p10", "p50", "p90")),
    }
    missing_columns = needed.difference(candidates.columns)
    if missing_columns:
        raise ValueError(
            "location candidates are missing landcover inputs: "
            + ", ".join(sorted(missing_columns))
        )
    for stem in (
        "rainfed_crop_capacity_people",
        "livestock_capacity_people",
        "wild_capacity_people",
        "wild_density_people_per_km2",
    ):
        ordered = np.sort(
            candidates.select(
                f"{stem}_p10", f"{stem}_p50", f"{stem}_p90"
            ).to_numpy(),
            axis=1,
        )
        candidates = candidates.with_columns(
            *(pl.Series(f"{stem}_{quantile}", ordered[:, index]) for index, quantile in enumerate(("p10", "p50", "p90")))
        )
    output = location.join(
        candidates.select(sorted(needed)),
        on="location_tag",
        how="inner",
    )
    capacity_expressions: list[pl.Expr] = []
    for quantile in ("p10", "p50", "p90"):
        crop = pl.col(f"rainfed_crop_capacity_people_{quantile}").cast(pl.Float64)
        forest_crop_share = pl.col(f"forest_crop_yield_share_{quantile}")
        livestock = pl.col(f"livestock_capacity_people_{quantile}").cast(pl.Float64)
        wild = pl.col(f"wild_capacity_people_{quantile}").cast(pl.Float64)
        wild_density = pl.col(f"wild_density_people_per_km2_{quantile}").cast(
            pl.Float64
        )
        grazing_total = pl.col("rangeland_fraction_1300") + pl.col(
            "pasture_fraction_1300"
        )
        extensive_share = pl.when(grazing_total > 0.0).then(
            pl.col("rangeland_fraction_1300") / grazing_total
        ).otherwise(0.0)
        displaced_wild = pl.min_horizontal(
            wild,
            pl.col("area_km2")
            * pl.col("forest_fraction_1300")
            * wild_density,
        )
        clearing_gross = crop * forest_crop_share
        # Extensive livestock is allocated only to the mutually exclusive
        # rangeland/pasture account above, so forest clearing displaces none of
        # that retained component. Keep the zero explicit in the artifact.
        displaced_livestock = pl.lit(0.0)
        capacity_expressions.extend(
            (
                (crop * (1.0 - forest_crop_share)).alias(
                    f"open_rainfed_capacity_people_{quantile}"
                ),
                (livestock * extensive_share.clip(0.0, 1.0)).alias(
                    f"extensive_livestock_capacity_people_{quantile}"
                ),
                wild.alias(f"retained_wild_capacity_people_{quantile}"),
                (
                    clearing_gross - displaced_wild - displaced_livestock
                )
                .clip(lower_bound=0.0)
                .alias(f"clearing_increment_capacity_people_{quantile}"),
                clearing_gross.alias(
                    f"clearing_gross_crop_capacity_people_{quantile}"
                ),
                displaced_wild.alias(
                    f"clearing_displaced_wild_capacity_people_{quantile}"
                ),
                displaced_livestock.alias(
                    f"clearing_displaced_livestock_capacity_people_{quantile}"
                ),
            )
        )
    output = output.with_columns(*capacity_expressions)
    for stem in (
        "open_rainfed_capacity_people",
        "extensive_livestock_capacity_people",
        "retained_wild_capacity_people",
        "clearing_increment_capacity_people",
        "clearing_gross_crop_capacity_people",
        "clearing_displaced_wild_capacity_people",
        "clearing_displaced_livestock_capacity_people",
    ):
        columns = [f"{stem}_{quantile}" for quantile in ("p10", "p50", "p90")]
        ordered = np.sort(output.select(columns).to_numpy(), axis=1)
        output = output.with_columns(
            *(pl.Series(column, ordered[:, index]) for index, column in enumerate(columns))
        )
    crop_contracts: dict[str, list[str]] = {}
    for path in crop_sample_paths:
        contracts = (
            pl.read_parquet(path, columns=["source_contract_hash"])[
                "source_contract_hash"
            ]
            .drop_nulls()
            .unique()
            .sort()
            .to_list()
        )
        crop_contracts[path.name] = [str(value) for value in contracts]
    build_contract = {
        "schema_version": LANDCOVER_SCHEMA_VERSION,
        "landcover_source_manifest": manifest,
        "inputs": {
            "sample_points_path": str(sample_points_path),
            "sample_points_sha256": _sha256(sample_points_path),
            "crop_labels_path": str(crop_labels_path),
            "crop_labels_sha256": _sha256(crop_labels_path),
            "candidates_path": str(candidates_path),
            "candidates_sha256": _sha256(candidates_path),
            "crop_samples_root": str(crop_samples_root),
            "crop_sample_contracts": crop_contracts,
        },
    }
    source_hash = hashlib.sha256(
        json.dumps(build_contract, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    build_manifest_path = output_path.with_suffix(".build.json")
    build_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    build_manifest_path.write_text(
        json.dumps(build_contract, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    output = output.select(
        "location_tag",
        "primary_forest_fraction_1300",
        "secondary_forest_fraction_1300",
        "luh2_forest_fraction_1300",
        "forest_fraction_1300",
        "potential_forest_fraction",
        "managed_land_fraction_1300",
        "cropland_fraction_1300",
        "urban_fraction_1300",
        "pasture_fraction_1300",
        "rangeland_fraction_1300",
        "open_natural_fraction_1300",
        "luh2_nonforest_fraction_1300",
        *(f"forest_crop_yield_share_{q}" for q in ("p10", "p50", "p90")),
        "forest_crop_suitability_share",
        "open_crop_suitability_share",
        "allocated_woodland_fraction",
        "landcover_coverage_fraction",
        *(f"open_rainfed_capacity_people_{q}" for q in ("p10", "p50", "p90")),
        *(f"extensive_livestock_capacity_people_{q}" for q in ("p10", "p50", "p90")),
        *(f"retained_wild_capacity_people_{q}" for q in ("p10", "p50", "p90")),
        *(f"clearing_increment_capacity_people_{q}" for q in ("p10", "p50", "p90")),
        *(f"clearing_gross_crop_capacity_people_{q}" for q in ("p10", "p50", "p90")),
        *(f"clearing_displaced_wild_capacity_people_{q}" for q in ("p10", "p50", "p90")),
        *(f"clearing_displaced_livestock_capacity_people_{q}" for q in ("p10", "p50", "p90")),
    ).with_columns(
        (
            pl.col("luh2_forest_fraction_1300")
            + pl.col("open_natural_fraction_1300")
            + pl.col("managed_land_fraction_1300")
            + pl.col("rangeland_fraction_1300")
        ).alias("land_allocation_sum_1300"),
        pl.lit(int(manifest["luh2"]["year"])).alias("landcover_year"),
        pl.lit(source_hash).alias("landcover_source_hash"),
        pl.when(pl.col("landcover_coverage_fraction") >= 0.95)
        .then(pl.lit("complete"))
        .otherwise(pl.lit("partial"))
        .alias("landcover_status"),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.write_parquet(output_path)
    audit = audit_landcover_capacity_artifact(
        artifact_path=output_path,
        expected_locations=candidates.height,
        source_root=source_root,
    )
    audit_path = output_path.with_suffix(".audit.json")
    audit_path.write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return audit | {
        "artifact_path": str(output_path),
        "audit_path": str(audit_path),
        "build_manifest_path": str(build_manifest_path),
    }


def audit_landcover_capacity_artifact(
    *,
    artifact_path: Path,
    expected_locations: int | None = None,
    source_root: Path | None = None,
) -> dict[str, Any]:
    """Validate coverage, bounded fractions, monotonic bands, and hashes."""

    frame = pl.read_parquet(artifact_path)
    issues: list[str] = []
    if expected_locations is not None and frame.height != expected_locations:
        issues.append(
            f"location count mismatch: expected {expected_locations}, got {frame.height}"
        )
    if frame["location_tag"].n_unique() != frame.height:
        issues.append("location_tag is not unique")
    fraction_columns = [
        column
        for column in frame.columns
        if column.endswith("_fraction_1300")
        or column.endswith("_suitability_share")
        or column
        in {
            "allocated_woodland_fraction",
            "landcover_coverage_fraction",
            "potential_forest_fraction",
        }
    ]
    for column in fraction_columns:
        invalid = frame.filter(
            pl.col(column).is_null()
            | ~pl.col(column).is_finite()
            | (pl.col(column) < -1e-9)
            | (pl.col(column) > 1.0 + 1e-9)
        ).height
        if invalid:
            issues.append(f"{column} has {invalid} invalid fractions")
    allocation_overflow = float(
        frame.select(
            (pl.col("land_allocation_sum_1300") - 1.0)
            .clip(lower_bound=0.0)
            .max()
            .alias("overflow")
        ).item()
    )
    if allocation_overflow > 2e-5:
        issues.append(
            "LUH2 mutually exclusive allocation overflow is "
            f"{allocation_overflow:.6g}"
        )
    for stem in (
        "open_rainfed_capacity_people",
        "extensive_livestock_capacity_people",
        "retained_wild_capacity_people",
        "clearing_increment_capacity_people",
        "clearing_gross_crop_capacity_people",
        "clearing_displaced_wild_capacity_people",
        "clearing_displaced_livestock_capacity_people",
    ):
        invalid = frame.filter(
            (pl.col(f"{stem}_p10") > pl.col(f"{stem}_p50") + 1e-8)
            | (pl.col(f"{stem}_p50") > pl.col(f"{stem}_p90") + 1e-8)
            | (pl.col(f"{stem}_p10") < -1e-8)
        ).height
        if invalid:
            issues.append(f"{stem} has {invalid} non-monotone or negative rows")
    for quantile in ("p10", "p50", "p90"):
        invalid_clearing = frame.filter(
            pl.col(f"clearing_increment_capacity_people_{quantile}")
            > pl.col(f"clearing_gross_crop_capacity_people_{quantile}") + 1e-8
        ).height
        if invalid_clearing:
            issues.append(
                f"clearing {quantile} exceeds gross crop support in "
                f"{invalid_clearing} rows"
            )
    source_hashes = frame["landcover_source_hash"].drop_nulls().unique().to_list()
    if len(source_hashes) != 1 or not isinstance(source_hashes[0], str):
        issues.append("landcover source hash is not singular")
    source_year = int(frame["landcover_year"].min())
    if source_year != 1300 or int(frame["landcover_year"].max()) != 1300:
        issues.append("landcover artifact does not exclusively use year 1300")
    source_hashes_valid: bool | None = None
    if source_root is not None:
        paths = landcover_paths(source_root)
        if not paths.source_manifest.is_file():
            issues.append("landcover source manifest is missing")
            source_hashes_valid = False
        else:
            manifest = json.loads(paths.source_manifest.read_text(encoding="utf-8"))
            build_manifest_path = artifact_path.with_suffix(".build.json")
            if build_manifest_path.is_file():
                build_contract = json.loads(
                    build_manifest_path.read_text(encoding="utf-8")
                )
                manifest_hash = hashlib.sha256(
                    json.dumps(
                        build_contract,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest()
                build_inputs = build_contract["inputs"]
                input_hash_checks = []
                for prefix in ("sample_points", "crop_labels", "candidates"):
                    input_path = Path(build_inputs[f"{prefix}_path"])
                    input_hash_checks.append(
                        input_path.is_file()
                        and _sha256(input_path)
                        == build_inputs[f"{prefix}_sha256"]
                    )
                crop_root = Path(build_inputs["crop_samples_root"])
                for filename, expected_contracts in build_inputs[
                    "crop_sample_contracts"
                ].items():
                    crop_path = crop_root / filename
                    if not crop_path.is_file():
                        input_hash_checks.append(False)
                        continue
                    actual_contracts = (
                        pl.read_parquet(
                            crop_path,
                            columns=["source_contract_hash"],
                        )["source_contract_hash"]
                        .drop_nulls()
                        .unique()
                        .sort()
                        .to_list()
                    )
                    input_hash_checks.append(
                        [str(value) for value in actual_contracts]
                        == expected_contracts
                    )
            else:
                manifest_hash = ""
                input_hash_checks = [False]
                issues.append("landcover build manifest is missing")
            checks = (
                int(manifest["luh2"]["year"]) == 1300,
                _sha256(paths.luh2_slice) == manifest["luh2"]["slice_sha256"],
                _sha256(paths.pnv_archive)
                == manifest["sage_pnv"]["archive_sha256"],
                _sha256(paths.pnv_netcdf)
                == manifest["sage_pnv"]["netcdf_sha256"],
                source_hashes == [manifest_hash],
                all(input_hash_checks),
            )
            source_hashes_valid = all(checks)
            if not source_hashes_valid:
                issues.append("landcover source hashes or selected year are stale")
    return {
        "schema_version": LANDCOVER_SCHEMA_VERSION,
        "artifact_path": str(artifact_path),
        "artifact_sha256": _sha256(artifact_path),
        "locations": frame.height,
        "landcover_year": source_year,
        "source_hashes_valid": source_hashes_valid,
        "complete_coverage_locations": frame.filter(
            pl.col("landcover_status") == "complete"
        ).height,
        "mean_coverage_fraction": float(frame["landcover_coverage_fraction"].mean()),
        "mean_forest_fraction_1300": float(frame["forest_fraction_1300"].mean()),
        "mean_potential_forest_fraction": float(
            frame["potential_forest_fraction"].mean()
        ),
        "max_land_allocation_overflow": allocation_overflow,
        "mean_unallocated_land_fraction": float(
            frame.select(
                (1.0 - pl.col("land_allocation_sum_1300"))
                .clip(0.0, 1.0)
                .mean()
            ).item()
        ),
        "issues": issues,
        "passed": not issues,
    }
