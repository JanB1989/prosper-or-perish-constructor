"""Pure 1337 location-capacity calibration model and hash-addressed exports."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import polars as pl
import rasterio
from rasterio.transform import from_origin

from prosper_or_perish_constructor.savegame_maps import (
    SavegameMapAssets,
    paint_location_metric_raster,
)


FORMULA_VERSION = "location-capacity-calibration-v1"
QUANTILES = ("p10", "p50", "p90")
GEOTIFF_NODATA = np.float32(-3.4028235e38)


@dataclass(frozen=True)
class LocationCapacityWeights:
    """Resolved parameters for the global formula; capacities remain people."""

    physical_quantile: str = "p50"
    crop_weight: float = 1.0
    livestock_weight: float = 1.0
    wild_weight: float = 1.0
    freshwater_weight: float = 1.0
    marine_weight: float = 1.0
    development_base: float = 0.0
    development_minimum_manageable_cropland_fraction: float = 0.02
    development_crop_points: float = 20.0
    development_crop_saturation_rate: float = 3.0
    development_pasture_points: float = 4.0
    development_minimum: float = 0.0
    development_maximum: float = 100.0
    development_relative: float = 0.0
    global_relative: float = 0.0
    clearing_realization: float = 0.0
    irrigation_scale: float = 1.0
    irrigation_exponent: float = 1.0
    tsetse_weight: float = 0.0
    minimum_capacity_game_units: float = 11.0

    def validate(self) -> None:
        if self.physical_quantile not in QUANTILES:
            raise ValueError(f"physical_quantile must be one of {QUANTILES}")
        finite = {
            key: value
            for key, value in asdict(self).items()
            if key != "physical_quantile"
        }
        invalid = [key for key, value in finite.items() if not math.isfinite(value)]
        if invalid:
            raise ValueError(f"non-finite location-capacity weights: {invalid}")
        nonnegative = (
            "crop_weight",
            "livestock_weight",
            "wild_weight",
            "freshwater_weight",
            "marine_weight",
            "development_minimum_manageable_cropland_fraction",
            "development_crop_saturation_rate",
            "development_pasture_points",
            "clearing_realization",
            "irrigation_scale",
            "irrigation_exponent",
            "tsetse_weight",
            "minimum_capacity_game_units",
        )
        below_zero = [key for key in nonnegative if finite[key] < 0.0]
        if below_zero:
            raise ValueError(f"location-capacity weights must be non-negative: {below_zero}")
        if not 0.0 <= self.clearing_realization <= 1.0:
            raise ValueError("clearing_realization must be in 0..1")
        if not 0.0 <= self.tsetse_weight <= 1.0:
            raise ValueError("tsetse_weight must be in 0..1")
        if self.development_minimum > self.development_maximum:
            raise ValueError("development minimum exceeds development maximum")
        if not -0.5 <= self.global_relative <= 0.0:
            raise ValueError("global_relative must be in -0.5..0.0")


def weights_from_profile(profile: Any) -> LocationCapacityWeights:
    """Use the simulator's parsed values as notebook defaults."""

    formula = profile.capacity_formula
    return LocationCapacityWeights(
        development_base=float(profile.development_base),
        development_minimum_manageable_cropland_fraction=float(
            profile.development_minimum_manageable_cropland_fraction
        ),
        development_crop_points=float(profile.development_cropland_utilization_points),
        development_crop_saturation_rate=float(
            profile.development_cropland_saturation_rate
        ),
        development_pasture_points=float(profile.development_pasture_full_share_points),
        development_minimum=float(profile.development_start_min),
        development_maximum=float(profile.development_start_max),
        development_relative=float(formula.development_relative),
        global_relative=float(formula.global_relative),
        minimum_capacity_game_units=float(profile.min_location_capacity),
    )


def _join_missing(frame: pl.DataFrame, source: pl.DataFrame) -> pl.DataFrame:
    missing = [column for column in source.columns if column not in frame.columns]
    if not missing:
        return frame
    return frame.join(
        source.select("location_tag", *missing),
        on="location_tag",
        how="left",
        validate="1:1",
    )


def prepare_location_capacity_inputs(
    starting_locations: pl.DataFrame,
    candidates: pl.DataFrame,
    landcover: pl.DataFrame,
) -> pl.DataFrame:
    """Join only missing physical columns onto the canonical simulator state."""

    if "location_tag" not in starting_locations.columns:
        raise ValueError("starting locations require location_tag")
    candidate_columns = {
        "location_tag",
        "area_km2",
        "macro_region",
        "super_region",
        "region",
        "province",
        "topography",
        "vegetation",
        "calibrated_lon",
        "calibrated_lat",
        "tsetse_ecological_exposure",
        *(f"freshwater_capacity_people_{q}" for q in QUANTILES),
        *(f"marine_capacity_people_{q}" for q in QUANTILES),
        *(f"irrigation_increment_capacity_people_{q}" for q in QUANTILES),
    }
    missing_candidate = candidate_columns.difference(candidates.columns)
    if missing_candidate:
        raise ValueError(
            "candidate artifact lacks calibration columns: "
            + ", ".join(sorted(missing_candidate))
        )
    frame = _join_missing(
        starting_locations,
        candidates.select(sorted(candidate_columns)),
    )
    frame = _join_missing(frame, landcover)
    required = {
        "location_tag",
        "area_km2",
        "hyde_cropland_area_km2",
        "hyde_pasture_area_km2",
        "hyde_irrigated_area_km2",
        "local_population_capacity",
        *(f"open_rainfed_capacity_people_{q}" for q in QUANTILES),
        *(f"extensive_livestock_capacity_people_{q}" for q in QUANTILES),
        *(f"retained_wild_capacity_people_{q}" for q in QUANTILES),
        *(f"clearing_increment_capacity_people_{q}" for q in QUANTILES),
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(
            "prepared location-capacity inputs are missing: "
            + ", ".join(sorted(missing))
        )
    population_column = next(
        (
            column
            for column in ("profile_start_population", "total_population")
            if column in frame.columns
        ),
        None,
    )
    if population_column is None:
        raise ValueError("starting state has no starting-population column")
    return frame.with_columns(
        pl.col(population_column).cast(pl.Float64).fill_null(0.0).alias(
            "starting_population_game_units"
        )
    )


def evaluate_location_capacity(
    inputs: pl.DataFrame,
    weights: LocationCapacityWeights,
    *,
    people_per_game_unit: float,
) -> pl.DataFrame:
    """Evaluate the candidate formula once for every location.

    The function contains no regional branches or location overrides. HYDE
    population is not read and therefore cannot become a hidden capacity floor.
    """

    weights.validate()
    if not math.isfinite(people_per_game_unit) or people_per_game_unit <= 0.0:
        raise ValueError("people_per_game_unit must be finite and positive")
    q = weights.physical_quantile
    area = pl.col("area_km2").cast(pl.Float64).fill_null(0.0).clip(lower_bound=0.0)
    crop_share = (
        pl.col("hyde_cropland_area_km2").cast(pl.Float64).fill_null(0.0) / area.clip(lower_bound=1e-12)
    ).clip(0.0, 1.0)
    pasture_share = (
        pl.col("hyde_pasture_area_km2").cast(pl.Float64).fill_null(0.0) / area.clip(lower_bound=1e-12)
    ).clip(0.0, 1.0)
    irrigation_evidence_fraction = (
        pl.col("hyde_irrigated_area_km2").cast(pl.Float64).fill_null(0.0)
        / area.clip(lower_bound=1e-12)
    ).clip(0.0, 1.0)
    utilization = crop_share / max(
        weights.development_minimum_manageable_cropland_fraction,
        1e-12,
    )
    development = (
        weights.development_base
        + weights.development_crop_points
        * (1.0 - (-weights.development_crop_saturation_rate * utilization).exp())
        + weights.development_pasture_points * pasture_share
    ).clip(weights.development_minimum, weights.development_maximum)
    tsetse_exposure = pl.col("tsetse_ecological_exposure").cast(pl.Float64).fill_null(0.0).clip(0.0, 1.0)
    crop = pl.col(f"open_rainfed_capacity_people_{q}").cast(pl.Float64).fill_null(0.0)
    livestock = pl.col(f"extensive_livestock_capacity_people_{q}").cast(pl.Float64).fill_null(0.0)
    wild = pl.col(f"retained_wild_capacity_people_{q}").cast(pl.Float64).fill_null(0.0)
    freshwater = pl.col(f"freshwater_capacity_people_{q}").cast(pl.Float64).fill_null(0.0)
    marine = pl.col(f"marine_capacity_people_{q}").cast(pl.Float64).fill_null(0.0)
    clearing_potential = pl.col(f"clearing_increment_capacity_people_{q}").cast(pl.Float64).fill_null(0.0)
    irrigation_potential = pl.col(f"irrigation_increment_capacity_people_{q}").cast(pl.Float64).fill_null(0.0)
    irrigation_fraction = (
        weights.irrigation_scale
        * irrigation_evidence_fraction.pow(weights.irrigation_exponent)
    ).clip(0.0, 1.0)
    crop_contribution = weights.crop_weight * crop
    livestock_contribution = (
        weights.livestock_weight
        * livestock
        * (1.0 - weights.tsetse_weight * tsetse_exposure)
    )
    wild_contribution = weights.wild_weight * wild
    freshwater_contribution = weights.freshwater_weight * freshwater
    marine_contribution = weights.marine_weight * marine
    base = (
        crop_contribution
        + livestock_contribution
        + wild_contribution
        + freshwater_contribution
        + marine_contribution
    )
    clearing = weights.clearing_realization * clearing_potential
    irrigation = irrigation_fraction * irrigation_potential
    capacity_before_development_relative = (
        base + clearing + irrigation
    )
    capacity_before_minimum = (
        capacity_before_development_relative
        * (
            1.0
            + weights.development_relative * development
            + weights.global_relative
        )
    )
    capacity = (
        capacity_before_minimum
    ).clip(lower_bound=weights.minimum_capacity_game_units * people_per_game_unit)
    development_total = (
        capacity_before_minimum - (base + clearing + irrigation)
    ).clip(lower_bound=0.0)
    minimum_floor = (capacity - capacity_before_minimum).clip(lower_bound=0.0)
    starting_population_people = (
        pl.col("starting_population_game_units") * people_per_game_unit
    )
    current_capacity_people = (
        pl.col("local_population_capacity").cast(pl.Float64).fill_null(0.0)
        * people_per_game_unit
    )
    return inputs.with_columns(
        crop.alias("source_open_crop_people"),
        livestock.alias("source_extensive_livestock_people"),
        wild.alias("source_retained_wild_people"),
        freshwater.alias("source_freshwater_people"),
        marine.alias("source_marine_people"),
        clearing_potential.alias("clearing_potential_people"),
        irrigation_potential.alias("irrigation_potential_people"),
        tsetse_exposure.alias("tsetse_exposure"),
        crop_share.alias("hyde_cropland_fraction"),
        pasture_share.alias("hyde_pasture_fraction"),
        irrigation_evidence_fraction.alias("hyde_irrigation_fraction"),
        development.alias("candidate_starting_development"),
        crop_contribution.alias("crop_contribution_people"),
        livestock_contribution.alias("livestock_contribution_people"),
        wild_contribution.alias("wild_contribution_people"),
        freshwater_contribution.alias("freshwater_contribution_people"),
        marine_contribution.alias("marine_contribution_people"),
        base.alias("base_location_potential_people"),
        pl.lit(0.0).alias("development_absolute_contribution_people"),
        development_total.alias("development_total_contribution_people"),
        clearing.alias("clearing_contribution_people"),
        irrigation_fraction.alias("irrigation_realized_fraction"),
        irrigation.alias("irrigation_contribution_people"),
        minimum_floor.alias("minimum_floor_contribution_people"),
        capacity.alias("candidate_capacity_people"),
        (capacity / people_per_game_unit).alias("candidate_capacity_game_units"),
        starting_population_people.alias("starting_population_people"),
        current_capacity_people.alias("current_capacity_people"),
        (capacity - current_capacity_people).alias("candidate_minus_current_people"),
        pl.when(capacity > 0.0)
        .then(starting_population_people / capacity)
        .otherwise(None)
        .alias("population_fill"),
    )


def _weighted_quantile(values: np.ndarray, weights: np.ndarray, quantile: float) -> float:
    valid = np.isfinite(values) & np.isfinite(weights) & (weights >= 0.0)
    values = values[valid]
    weights = weights[valid]
    if values.size == 0:
        return float("nan")
    order = np.argsort(values)
    values = values[order]
    weights = weights[order]
    total = float(weights.sum())
    if total <= 0.0:
        return float(np.quantile(values, quantile))
    cumulative = np.cumsum(weights) / total
    return float(values[min(np.searchsorted(cumulative, quantile), values.size - 1)])


def summarize_location_capacity(
    frame: pl.DataFrame,
    *,
    profile: Any | None = None,
) -> dict[str, Any]:
    capacity = frame["candidate_capacity_people"].to_numpy()
    population = frame["starting_population_people"].to_numpy()
    fill = frame["population_fill"].to_numpy()
    total_capacity = float(np.nansum(capacity))
    total_population = float(np.nansum(population))
    summary: dict[str, Any] = {
        "formula_version": FORMULA_VERSION,
        "locations": frame.height,
        "total_capacity_people": total_capacity,
        "total_starting_population_people": total_population,
        "global_population_fill": total_population / max(total_capacity, 1e-12),
        "location_within_capacity_fraction": float(np.mean(fill <= 1.0)),
        "population_weighted_fill_p10": _weighted_quantile(fill, population, 0.10),
        "population_weighted_fill_p50": _weighted_quantile(fill, population, 0.50),
        "population_weighted_fill_p90": _weighted_quantile(fill, population, 0.90),
        "max_location_capacity_game_units": float(
            frame["candidate_capacity_game_units"].max()
        ),
        "max_population_fill": float(np.nanmax(fill)),
    }
    if profile is not None:
        gates = {
            "minimum_capacity": float(frame["candidate_capacity_game_units"].min())
            >= float(profile.min_location_capacity),
            "maximum_capacity": summary["max_location_capacity_game_units"]
            <= float(profile.max_location_capacity),
            "global_start_capacity_ratio": total_capacity
            / max(total_population, 1e-12)
            >= float(profile.min_global_start_capacity_ratio),
            "locations_within_capacity": summary["location_within_capacity_fraction"]
            >= float(profile.min_start_population_within_capacity_fraction),
            "maximum_fill": summary["max_population_fill"]
            <= float(profile.max_location_capacity_fill),
        }
        summary["sanity_gates"] = gates
        summary["sanity_passed"] = all(gates.values())
    return summary


def macro_region_attribution(frame: pl.DataFrame) -> pl.DataFrame:
    components = (
        "crop_contribution_people",
        "livestock_contribution_people",
        "wild_contribution_people",
        "freshwater_contribution_people",
        "marine_contribution_people",
        "development_total_contribution_people",
        "clearing_contribution_people",
        "irrigation_contribution_people",
        "minimum_floor_contribution_people",
        "candidate_capacity_people",
        "starting_population_people",
    )
    return (
        frame.group_by("macro_region")
        .agg(*(pl.col(column).sum().alias(column) for column in components))
        .with_columns(
            (
                pl.col("starting_population_people")
                / pl.col("candidate_capacity_people").clip(lower_bound=1e-12)
            ).alias("population_fill")
        )
        .sort("candidate_capacity_people", descending=True)
    )


def diagnostic_groups(frame: pl.DataFrame) -> pl.DataFrame:
    """Global-formula diagnostics only; these masks never alter capacity."""

    text = pl.concat_str(
        [
            pl.col(column).cast(pl.String).fill_null("")
            for column in ("location_tag", "macro_region", "super_region", "region", "province")
        ],
        separator=" ",
    ).str.to_lowercase()
    longitude = pl.col("calibrated_lon").cast(pl.Float64)
    latitude = pl.col("calibrated_lat").cast(pl.Float64)
    iceland = (
        longitude.is_between(-26.0, -12.0)
        & latitude.is_between(62.0, 68.0)
    )
    steppe = (
        pl.col("vegetation").cast(pl.String).fill_null("").str.to_lowercase()
        == "grasslands"
    ) & (
        longitude.is_between(25.0, 125.0)
        & latitude.is_between(35.0, 57.0)
    )
    definitions = (
        ("China", text.str.contains("china")),
        ("India", text.str.contains("india")),
        ("Nile / Egypt", text.str.contains("nile|egypt")),
        ("Iceland", iceland),
        ("Major Eurasian steppes", steppe),
        ("Central Africa", text.str.contains("central.africa|congo")),
    )
    rows: list[dict[str, Any]] = []
    for label, condition in definitions:
        subset = frame.filter(condition)
        if subset.is_empty():
            continue
        rows.append(
            {
                "diagnostic": label,
                "locations": subset.height,
                "base_location_potential_people": float(
                    subset["base_location_potential_people"].sum()
                ),
                "candidate_capacity_people": float(
                    subset["candidate_capacity_people"].sum()
                ),
                "starting_population_people": float(
                    subset["starting_population_people"].sum()
                ),
                "population_fill": float(subset["starting_population_people"].sum())
                / max(float(subset["candidate_capacity_people"].sum()), 1e-12),
                "median_base_density_people_per_km2": float(
                    subset.select(
                        (
                            pl.col("base_location_potential_people")
                            / pl.col("area_km2").clip(lower_bound=1e-12)
                        ).median()
                    ).item()
                ),
            }
        )
    return pl.DataFrame(rows)


def _toml_value(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return repr(value)


def _write_weights_toml(
    path: Path,
    weights: LocationCapacityWeights,
    *,
    people_per_game_unit: float,
    source_hashes: Mapping[str, str],
) -> None:
    lines = [
        f"formula_version = {_toml_value(FORMULA_VERSION)}",
        f"people_per_game_unit = {_toml_value(people_per_game_unit)}",
        "",
        "[weights]",
    ]
    lines.extend(f"{key} = {_toml_value(value)}" for key, value in asdict(weights).items())
    lines.extend(("", "[source_hashes]"))
    lines.extend(f"{key} = {_toml_value(value)}" for key, value in sorted(source_hashes.items()))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_metric_geotiff(
    frame: pl.DataFrame,
    *,
    metric: str,
    assets: SavegameMapAssets,
    output_path: Path,
) -> None:
    painted = paint_location_metric_raster(
        assets,
        frame,
        value_column=metric,
        nodata=float(GEOTIFF_NODATA),
    )
    height, width = painted.values.shape
    options: dict[str, Any] = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": "float32",
        "nodata": float(GEOTIFF_NODATA),
        "transform": from_origin(0.0, float(height), 1.0, 1.0),
        "compress": "deflate",
        "predictor": 3,
    }
    if width >= 256 and height >= 256:
        options.update(tiled=True, blockxsize=256, blockysize=256)
    with rasterio.open(output_path, "w", **options) as destination:
        destination.write(painted.values, 1)
        destination.set_band_description(1, metric)
        destination.update_tags(
            coordinate_space="EU5 game-map pixels",
            formula_version=FORMULA_VERSION,
            metric=metric,
        )


def export_location_capacity_run(
    frame: pl.DataFrame,
    weights: LocationCapacityWeights,
    *,
    output_root: Path,
    people_per_game_unit: float,
    summary: Mapping[str, Any],
    source_hashes: Mapping[str, str],
    existing_anchor_results: Iterable[Path] = (),
    assets: SavegameMapAssets | None = None,
    geotiff_layers: Iterable[str] = (),
) -> Path:
    """Write an isolated, reproducible run without mutating accepted inputs."""

    payload = {
        "formula_version": FORMULA_VERSION,
        "people_per_game_unit": people_per_game_unit,
        "weights": asdict(weights),
        "source_hashes": dict(sorted(source_hashes.items())),
    }
    run_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    run_dir = Path(output_root) / f"run-{run_hash[:16]}"
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_weights_toml(
        run_dir / "weights.toml",
        weights,
        people_per_game_unit=people_per_game_unit,
        source_hashes=source_hashes,
    )
    frame.write_parquet(run_dir / "location_capacity.parquet")
    resolved_summary = dict(summary) | {
        "run_hash": run_hash,
        "formula_version": FORMULA_VERSION,
        "source_hashes": dict(source_hashes),
        "resolved_parameters": asdict(weights),
    }
    (run_dir / "summary.json").write_text(
        json.dumps(resolved_summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    anchors: list[pl.DataFrame] = []
    for path in existing_anchor_results:
        if Path(path).is_file():
            anchors.append(
                pl.read_csv(path).with_columns(
                    pl.lit(Path(path).name).alias("source_file"),
                    pl.lit("current_pipeline_evidence").alias("result_scope"),
                )
            )
    if anchors:
        pl.concat(anchors, how="diagonal_relaxed").write_csv(
            run_dir / "anchor_results.csv"
        )
    else:
        diagnostic_groups(frame).write_csv(run_dir / "anchor_results.csv")
    layers = tuple(dict.fromkeys(geotiff_layers))
    if layers and assets is None:
        raise ValueError("GeoTIFF layers require loaded EU5 map assets")
    for metric in layers:
        if metric not in frame.columns:
            raise ValueError(f"unknown GeoTIFF metric: {metric}")
        _write_metric_geotiff(
            frame,
            metric=metric,
            assets=assets,
            output_path=run_dir / f"{metric}.tif",
        )
    return run_dir
