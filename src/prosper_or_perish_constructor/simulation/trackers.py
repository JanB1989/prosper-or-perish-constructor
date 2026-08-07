"""Opt-in named trackers for simulation history (computed only when registered)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import numpy as np
import polars as pl

from prosper_or_perish_constructor.simulation.capacity_pressure import POPULATION_CAPACITY_COLUMN
from prosper_or_perish_constructor.simulation.population import TOTAL_POPULATION_COLUMN

if TYPE_CHECKING:
    from prosper_or_perish_constructor.simulation.numpy_engine import NumPyLocationState

AggKind = Literal["sum", "mean", "identity"]

# Virtual derived column: location fill percentage = 100 * pop / capacity.
CAPACITY_FILL_PERCENT_COLUMN = "capacity_fill_percent"


@dataclass(frozen=True)
class TrackerSpec:
    """How to sample one metric from a location state frame."""

    name: str
    group_by: tuple[str, ...]
    column: str
    agg: AggKind = "sum"

    def sample(self, locations: pl.DataFrame, *, tick: int) -> pl.DataFrame:
        frame = locations
        if self.column == CAPACITY_FILL_PERCENT_COLUMN:
            required = {TOTAL_POPULATION_COLUMN, POPULATION_CAPACITY_COLUMN}
            missing = sorted(required - set(locations.columns))
            if missing:
                raise ValueError(
                    f"tracker {self.name!r} missing columns on state: {', '.join(missing)}"
                )
            pop = pl.col(TOTAL_POPULATION_COLUMN).fill_null(0.0).cast(pl.Float64)
            cap = pl.col(POPULATION_CAPACITY_COLUMN).fill_null(0.0).cast(pl.Float64)
            fill = (
                pl.when(cap > 0.0)
                .then(100.0 * pop / cap)
                .otherwise(0.0)
                .alias(CAPACITY_FILL_PERCENT_COLUMN)
            )
            frame = locations.with_columns(fill)

        missing = [column for column in (*self.group_by, self.column) if column not in frame.columns]
        if missing:
            raise ValueError(
                f"tracker {self.name!r} missing columns on state: {', '.join(missing)}"
            )
        tick_expr = pl.lit(int(tick), dtype=pl.UInt32).alias("tick")
        if self.agg == "identity":
            return frame.select(
                tick_expr,
                *[pl.col(column) for column in self.group_by],
                pl.col(self.column).cast(pl.Float64).alias("value"),
            )
        if self.agg == "sum":
            return (
                frame.group_by(list(self.group_by))
                .agg(pl.col(self.column).fill_null(0.0).cast(pl.Float64).sum().alias("value"))
                .with_columns(tick_expr)
                .select("tick", *self.group_by, "value")
            )
        if self.agg == "mean":
            return (
                frame.group_by(list(self.group_by))
                .agg(pl.col(self.column).fill_null(0.0).cast(pl.Float64).mean().alias("value"))
                .with_columns(tick_expr)
                .select("tick", *self.group_by, "value")
            )
        raise ValueError(f"unsupported tracker agg: {self.agg!r}")

    def sample_numpy(self, state: NumPyLocationState, *, tick: int) -> pl.DataFrame:
        """Sample from NumPy state without running a Polars tick pipeline."""
        from prosper_or_perish_constructor.simulation.numpy_engine import column_array

        if self.column == CAPACITY_FILL_PERCENT_COLUMN:
            pop = np.asarray(state.total_population, dtype=np.float64)
            cap = np.asarray(state.population_capacity, dtype=np.float64)
            values = np.zeros(state.n, dtype=np.float64)
            valid = cap > 0.0
            values[valid] = 100.0 * pop[valid] / cap[valid]
        else:
            values = np.asarray(column_array(state, self.column), dtype=np.float64)

        if self.agg == "identity":
            data: dict[str, object] = {"tick": np.full(state.n, int(tick), dtype=np.uint32)}
            for key in self.group_by:
                data[key] = column_array(state, key)
            data["value"] = values
            return pl.DataFrame(data).select("tick", *self.group_by, "value")

        if self.agg in {"sum", "mean"} and self.group_by == ("province",):
            sums = np.zeros(state.n_provinces, dtype=np.float64)
            np.add.at(sums, state.province_codes, values)
            if self.agg == "mean":
                counts = np.zeros(state.n_provinces, dtype=np.float64)
                np.add.at(counts, state.province_codes, 1.0)
                with np.errstate(divide="ignore", invalid="ignore"):
                    means = np.divide(sums, counts, out=np.zeros_like(sums), where=counts > 0.0)
                value = means
            else:
                value = sums
            return pl.DataFrame(
                {
                    "tick": np.full(state.n_provinces, int(tick), dtype=np.uint32),
                    "province": state.province_labels,
                    "value": value,
                }
            ).select("tick", "province", "value")

        if self.agg in {"sum", "mean"}:
            slim = pl.DataFrame(
                {
                    **{key: column_array(state, key) for key in self.group_by},
                    self.column: values,
                }
            )
            # Avoid re-deriving capacity fill in sample(); column already materialized.
            if self.column == CAPACITY_FILL_PERCENT_COLUMN:
                tick_expr = pl.lit(int(tick), dtype=pl.UInt32).alias("tick")
                if self.agg == "mean":
                    return (
                        slim.group_by(list(self.group_by))
                        .agg(pl.col(self.column).mean().alias("value"))
                        .with_columns(tick_expr)
                        .select("tick", *self.group_by, "value")
                    )
                return (
                    slim.group_by(list(self.group_by))
                    .agg(pl.col(self.column).sum().alias("value"))
                    .with_columns(tick_expr)
                    .select("tick", *self.group_by, "value")
                )
            return self.sample(slim, tick=tick)

        raise ValueError(f"unsupported tracker agg: {self.agg!r}")

    def empty_frame(self) -> pl.DataFrame:
        schema: dict[str, pl.DataType] = {"tick": pl.UInt32}
        for column in self.group_by:
            schema[column] = pl.String
        schema["value"] = pl.Float64
        return pl.DataFrame(schema=schema)


# Registry of named trackers. Only evaluated when Simulation.track(...) registers them.
TRACKERS: Mapping[str, TrackerSpec] = {
    "province_total_population": TrackerSpec(
        name="province_total_population",
        group_by=("province",),
        column="total_population",
        agg="sum",
    ),
    "province_average_capacity_fill": TrackerSpec(
        name="province_average_capacity_fill",
        group_by=("province",),
        column=CAPACITY_FILL_PERCENT_COLUMN,
        agg="mean",
    ),
    "province_average_development": TrackerSpec(
        name="province_average_development",
        group_by=("province",),
        column="development",
        agg="mean",
    ),
    "province_average_prosperity": TrackerSpec(
        name="province_average_prosperity",
        group_by=("province",),
        column="prosperity",
        agg="mean",
    ),
    "location_total_population": TrackerSpec(
        name="location_total_population",
        group_by=("location_tag",),
        column="total_population",
        agg="identity",
    ),
    "location_food": TrackerSpec(
        name="location_food",
        group_by=("location_tag",),
        column="food",
        agg="identity",
    ),
    "province_food": TrackerSpec(
        name="province_food",
        group_by=("province",),
        column="food",
        agg="sum",
    ),
}


def require_tracker(name: str) -> TrackerSpec:
    try:
        return TRACKERS[name]
    except KeyError as exc:
        known = ", ".join(sorted(TRACKERS))
        raise KeyError(f"unknown tracker {name!r}; known: {known}") from exc


def list_trackers() -> Sequence[str]:
    return tuple(sorted(TRACKERS))
