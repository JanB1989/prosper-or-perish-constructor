"""NumPy-backed location state and monthly tick (hot path)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

import numpy as np
import polars as pl

from prosper_or_perish_constructor.simulation.capacity_pressure import (
    ABUNDANT_FREE_LAND,
    AVAILABLE_FREE_LAND,
    LOCAL_MONTHLY_FOOD_KEY,
    LOCAL_POPULATION_GROWTH_KEY,
    OVERPOPULATION,
    POPULATION_CAPACITY_COLUMN,
    CapacityPressureBand,
    capacity_pressure_strength_arrays,
)
from prosper_or_perish_constructor.simulation.food import (
    FOOD_COLUMN,
    attach_peasant_employment_state,
    pop_food_consumption_modifier_column,
)
from prosper_or_perish_constructor.simulation.modifiers import (
    LOCATION_RANK_COLUMN,
    TRACKED_MODIFIER_KEYS,
    SimulationModifierContext,
)
from prosper_or_perish_constructor.simulation.population import (
    EMPLOYED_PEASANTS_COLUMN,
    MONTHS_PER_YEAR,
    PEASANT_EMPLOYMENT_COLUMN,
    PEASANTS_COLUMN,
    POPULATION_PREFIX,
    TOTAL_POPULATION_COLUMN,
    UNEMPLOYED_PEASANTS_COLUMN,
    YEARLY_GROWTH_COLUMN,
)
from prosper_or_perish_constructor.simulation.prosperity import (
    DEVELOPMENT_COLUMN,
    DEVELOPMENT_MAX,
    LOCAL_MONTHLY_DEVELOPMENT_KEY,
    LOCAL_MONTHLY_DEVELOPMENT_MODIFIER_KEY,
    LOCAL_POPULATION_GROWTH_KEY as PROSPERITY_POP_GROWTH_KEY,
    PROSPERITY_COLUMN,
    PROSPERITY_FULL_SCALE,
    PROSPERITY_MAX,
    ProsperityBaselines,
)

_GROWTH_KEY = YEARLY_GROWTH_COLUMN


@dataclass
class NumPyLocationState:
    """In-memory location columns for fast month stepping."""

    location_tag: np.ndarray
    province: np.ndarray
    location_rank: np.ndarray
    food: np.ndarray
    total_population: np.ndarray
    population: dict[str, np.ndarray]
    extras_float: dict[str, np.ndarray] = field(default_factory=dict)
    extras_str: dict[str, np.ndarray] = field(default_factory=dict)

    # Precomputed tick inputs (stable unless ranks/context change)
    province_codes: np.ndarray = field(repr=False, default_factory=lambda: np.array([], dtype=np.int32))
    province_labels: np.ndarray = field(repr=False, default_factory=lambda: np.array([], dtype=object))
    rank_population_growth: np.ndarray = field(repr=False, default_factory=lambda: np.zeros(0))
    # (pop_array, base_rate, static_food_consumption_mod or None, pop_type)
    pop_terms: list[tuple[np.ndarray, float, np.ndarray | None, str]] = field(
        repr=False, default_factory=list
    )
    peasant_employment: np.ndarray = field(repr=False, default_factory=lambda: np.zeros(0))
    unemployed_peasants: np.ndarray = field(repr=False, default_factory=lambda: np.zeros(0))
    employed_peasants: np.ndarray = field(repr=False, default_factory=lambda: np.zeros(0))
    population_capacity: np.ndarray = field(repr=False, default_factory=lambda: np.zeros(0))
    capacity_pressure: Mapping[str, CapacityPressureBand] = field(default_factory=dict)
    # pop_type -> band_name -> baseline local_<type>_food_consumption
    capacity_food_consumption: dict[str, dict[str, float]] = field(default_factory=dict)
    capacity_monthly_food: dict[str, float] = field(default_factory=dict)
    capacity_population_growth: dict[str, float] = field(default_factory=dict)
    prosperity: np.ndarray = field(repr=False, default_factory=lambda: np.zeros(0))
    development: np.ndarray = field(repr=False, default_factory=lambda: np.zeros(0))
    prosperity_baselines: ProsperityBaselines | None = None
    food_growth_population_baseline: float = 0.0
    food_growth_prosperity_baseline: float = 0.0
    growth_cap_years: float = 2.0
    subsistence_agriculture: float = 0.0
    food_decay_rate: float = 0.01
    n_provinces: int = 0

    @property
    def n(self) -> int:
        return int(self.location_tag.shape[0])

    def tick_months(self, months: int = 1) -> None:
        if months < 0:
            raise ValueError(f"months must be non-negative: {months}")
        for _ in range(months):
            self.tick_one_month()

    def tick_one_month(self) -> None:
        """One month: prosperity effects → food → growth/dev → prosperity update → decay."""
        n = self.n
        if n == 0:
            return

        self._rebalance_peasant_employment()

        # Prosperity scale from current state (0..100 → 0..1). Devastation ignored.
        prosperity_scale = np.clip(self.prosperity / PROSPERITY_FULL_SCALE, 0.0, 1.0)
        baselines = self.prosperity_baselines

        abundant, available, overpopulated, strength = capacity_pressure_strength_arrays(
            self.total_population,
            self.population_capacity,
        )
        capacity_growth = self._scaled_band_effect(
            abundant,
            available,
            overpopulated,
            strength,
            self.capacity_population_growth,
        )
        monthly_food = self._scaled_band_effect(
            abundant,
            available,
            overpopulated,
            strength,
            self.capacity_monthly_food,
        )

        consumption = np.zeros(n, dtype=np.float64)
        for pop, rate, static_modifier, pop_type in self.pop_terms:
            capacity_mod = self._scaled_band_effect(
                abundant,
                available,
                overpopulated,
                strength,
                self.capacity_food_consumption.get(pop_type, {}),
            )
            prosperity_food = 0.0
            if baselines is not None:
                prosperity_food = baselines.food_consumption_effect(pop_type)
            prosperity_mod = prosperity_scale * prosperity_food
            if static_modifier is None:
                modifier = capacity_mod + prosperity_mod
            else:
                modifier = static_modifier + capacity_mod + prosperity_mod
            effective_rate = np.maximum(rate * (1.0 + modifier), 0.0)
            consumption += pop * effective_rate

        production = self.unemployed_peasants * self.subsistence_agriculture + monthly_food
        self._apply_province_food_net(production=production, consumption=consumption)

        # Food-growth buff uses stored food / population consumption only (decay is not consumption).
        prov_food = np.zeros(self.n_provinces, dtype=np.float64)
        prov_cons = np.zeros(self.n_provinces, dtype=np.float64)
        np.add.at(prov_food, self.province_codes, self.food)
        np.add.at(prov_cons, self.province_codes, consumption)

        months_stored = np.zeros(self.n_provinces, dtype=np.float64)
        np.divide(prov_food, prov_cons, out=months_stored, where=prov_cons > 0.0)
        scale_years = np.clip(months_stored / MONTHS_PER_YEAR, 0.0, self.growth_cap_years)
        scale_at_loc = scale_years[self.province_codes]

        prosperity_pop_growth = np.zeros(n, dtype=np.float64)
        if baselines is not None:
            prosperity_pop_growth = prosperity_scale * baselines.get_effect(PROSPERITY_POP_GROWTH_KEY)

        yearly = (
            self.rank_population_growth
            + self.food_growth_population_baseline * scale_at_loc
            + capacity_growth
            + prosperity_pop_growth
        )
        mult = np.power(1.0 + yearly, 1.0 / MONTHS_PER_YEAR)
        for pop in self.population.values():
            pop *= mult
        self.total_population *= mult
        self._rebalance_peasant_employment()

        self._apply_prosperity_development(prosperity_scale)
        self._update_prosperity_state(scale_at_loc=scale_at_loc, prosperity_scale=prosperity_scale)

        # Spoilage after the buff read: reduces stock, does not count as consumption.
        self._apply_food_decay()

    def _apply_prosperity_development(self, prosperity_scale: np.ndarray) -> None:
        """Apply prosperity-scaled monthly development: add * (1 + modifier)."""
        baselines = self.prosperity_baselines
        if baselines is None or self.development.shape[0] != self.n:
            return
        monthly = prosperity_scale * baselines.get_effect(LOCAL_MONTHLY_DEVELOPMENT_KEY)
        modifier = prosperity_scale * baselines.get_effect(LOCAL_MONTHLY_DEVELOPMENT_MODIFIER_KEY)
        self.development = np.clip(
            self.development + monthly * (1.0 + modifier),
            0.0,
            DEVELOPMENT_MAX,
        )
        self.extras_float[DEVELOPMENT_COLUMN] = self.development

    def _update_prosperity_state(
        self,
        *,
        scale_at_loc: np.ndarray,
        prosperity_scale: np.ndarray,
    ) -> None:
        """Income from base + food storage, then fractional decay; clamp to [0, 100]."""
        baselines = self.prosperity_baselines
        if baselines is None or self.prosperity.shape[0] != self.n:
            return
        # Modifier rates are 0..1 fractions of full prosperity per month → points on 0..100.
        income_frac = (
            baselines.base_monthly_prosperity
            + self.food_growth_prosperity_baseline * scale_at_loc
        )
        self.prosperity = self.prosperity + income_frac * PROSPERITY_FULL_SCALE
        decay_frac = baselines.global_prosperity_decay + baselines.local_prosperity_decay * prosperity_scale
        decay_frac = np.clip(decay_frac, 0.0, 1.0)
        self.prosperity = self.prosperity * (1.0 - decay_frac)
        self.prosperity = np.clip(self.prosperity, 0.0, PROSPERITY_MAX)
        self.extras_float[PROSPERITY_COLUMN] = self.prosperity

    @staticmethod
    def _scaled_band_effect(
        abundant: np.ndarray,
        available: np.ndarray,
        overpopulated: np.ndarray,
        strength: np.ndarray,
        baselines: Mapping[str, float],
    ) -> np.ndarray:
        """Apply exclusive band baselines × strength into a location-sized array."""
        out = np.zeros(strength.shape, dtype=np.float64)
        if not baselines:
            return out
        abundant_base = float(baselines.get(ABUNDANT_FREE_LAND, 0.0) or 0.0)
        available_base = float(baselines.get(AVAILABLE_FREE_LAND, 0.0) or 0.0)
        over_base = float(baselines.get(OVERPOPULATION, 0.0) or 0.0)
        if abundant_base:
            out[abundant] = strength[abundant] * abundant_base
        if available_base:
            out[available] = strength[available] * available_base
        if over_base:
            out[overpopulated] = strength[overpopulated] * over_base
        return out

    def _rebalance_peasant_employment(self) -> None:
        """Fill fixed peasant jobs first; remainder is unemployed subsistence labor."""
        peasants = self.population.get(PEASANTS_COLUMN)
        if peasants is None:
            self.employed_peasants = np.zeros(self.n, dtype=np.float64)
            self.unemployed_peasants = np.zeros(self.n, dtype=np.float64)
        else:
            jobs = self.peasant_employment
            employed = np.minimum(np.maximum(peasants, 0.0), np.maximum(jobs, 0.0))
            self.employed_peasants = employed
            self.unemployed_peasants = np.maximum(peasants, 0.0) - employed
        self.extras_float[PEASANT_EMPLOYMENT_COLUMN] = self.peasant_employment
        self.extras_float[EMPLOYED_PEASANTS_COLUMN] = self.employed_peasants
        self.extras_float[UNEMPLOYED_PEASANTS_COLUMN] = self.unemployed_peasants

    def _apply_food_decay(self) -> None:
        """Destroy a fraction of currently stored food (per location stock)."""
        rate = float(self.food_decay_rate)
        if rate <= 0.0:
            return
        if rate >= 1.0:
            self.food = np.zeros_like(self.food)
            return
        self.food *= 1.0 - rate

    def _apply_province_food_net(
        self,
        *,
        production: np.ndarray,
        consumption: np.ndarray,
    ) -> None:
        """Province food += production − consumption, floored at 0; redistribute to locations."""
        old_prov = np.zeros(self.n_provinces, dtype=np.float64)
        prod_prov = np.zeros(self.n_provinces, dtype=np.float64)
        cons_prov = np.zeros(self.n_provinces, dtype=np.float64)
        np.add.at(old_prov, self.province_codes, self.food)
        np.add.at(prod_prov, self.province_codes, production)
        np.add.at(cons_prov, self.province_codes, consumption)
        new_prov = np.maximum(0.0, old_prov + prod_prov - cons_prov)

        scale = np.zeros(self.n_provinces, dtype=np.float64)
        positive_old = old_prov > 0.0
        scale[positive_old] = new_prov[positive_old] / old_prov[positive_old]
        self.food = self.food * scale[self.province_codes]

        zero_old = ~positive_old
        if not np.any(zero_old):
            return

        zero_mask = zero_old[self.province_codes]
        self.food[zero_mask] = 0.0
        for province_idx in np.flatnonzero(zero_old & (new_prov > 0.0)):
            loc = self.province_codes == province_idx
            prod = production[loc]
            prod_sum = float(prod.sum())
            if prod_sum > 0.0:
                self.food[loc] = new_prov[province_idx] * (prod / prod_sum)
            else:
                count = int(loc.sum())
                self.food[loc] = new_prov[province_idx] / count

    def to_polars(self) -> pl.DataFrame:
        data: dict[str, object] = {
            "location_tag": self.location_tag,
            "province": self.province,
            LOCATION_RANK_COLUMN: self.location_rank,
            FOOD_COLUMN: self.food,
            TOTAL_POPULATION_COLUMN: self.total_population,
            PEASANT_EMPLOYMENT_COLUMN: self.peasant_employment,
            EMPLOYED_PEASANTS_COLUMN: self.employed_peasants,
            UNEMPLOYED_PEASANTS_COLUMN: self.unemployed_peasants,
            POPULATION_CAPACITY_COLUMN: self.population_capacity,
            PROSPERITY_COLUMN: self.prosperity,
            DEVELOPMENT_COLUMN: self.development,
        }
        for name, values in self.population.items():
            data[name] = values
        for name, values in self.extras_float.items():
            if name in data:
                continue
            data[name] = values
        for name, values in self.extras_str.items():
            data[name] = values
        frame = pl.DataFrame(data)
        return frame.select(sorted(frame.columns))


def _capacity_effect_lookup(
    capacity_pressure: Mapping[str, CapacityPressureBand],
    key: str,
) -> dict[str, float]:
    return {
        name: band.get(key, 0.0)
        for name, band in capacity_pressure.items()
    }


def numpy_state_from_polars(
    locations: pl.DataFrame,
    context: SimulationModifierContext,
) -> NumPyLocationState:
    """Build a NumPy state view from a Polars location frame + modifier context."""
    if locations.height == 0:
        raise ValueError("cannot build numpy state from empty locations frame")
    if "province" not in locations.columns:
        raise ValueError("missing province column")
    if LOCATION_RANK_COLUMN not in locations.columns and "rank" not in locations.columns:
        raise ValueError(f"missing {LOCATION_RANK_COLUMN} (or rank) column")

    frame = attach_peasant_employment_state(locations)
    if FOOD_COLUMN not in frame.columns:
        frame = frame.with_columns(pl.lit(0.0).alias(FOOD_COLUMN))
    if LOCATION_RANK_COLUMN not in frame.columns:
        frame = frame.with_columns(pl.col("rank").alias(LOCATION_RANK_COLUMN))
    if TOTAL_POPULATION_COLUMN not in frame.columns:
        pop_cols = [c for c in frame.columns if c.startswith(POPULATION_PREFIX)]
        if not pop_cols:
            raise ValueError("no population columns on locations frame")
        frame = frame.with_columns(pl.sum_horizontal(pop_cols).alias(TOTAL_POPULATION_COLUMN))
    if POPULATION_CAPACITY_COLUMN not in frame.columns:
        frame = frame.with_columns(pl.lit(0.0).alias(POPULATION_CAPACITY_COLUMN))
    if PROSPERITY_COLUMN not in frame.columns:
        frame = frame.with_columns(pl.lit(0.0).alias(PROSPERITY_COLUMN))
    if DEVELOPMENT_COLUMN not in frame.columns:
        frame = frame.with_columns(pl.lit(0.0).alias(DEVELOPMENT_COLUMN))

    location_tag = frame["location_tag"].to_numpy() if "location_tag" in frame.columns else np.arange(frame.height)
    province = frame["province"].cast(pl.String).fill_null("").to_numpy()
    location_rank = frame[LOCATION_RANK_COLUMN].cast(pl.String).fill_null("").to_numpy()
    food = frame[FOOD_COLUMN].fill_null(0.0).cast(pl.Float64).to_numpy().astype(np.float64, copy=True)
    total_population = (
        frame[TOTAL_POPULATION_COLUMN].fill_null(0.0).cast(pl.Float64).to_numpy().astype(np.float64, copy=True)
    )
    population_capacity = (
        frame[POPULATION_CAPACITY_COLUMN]
        .fill_null(0.0)
        .cast(pl.Float64)
        .to_numpy()
        .astype(np.float64, copy=True)
    )
    prosperity = (
        frame[PROSPERITY_COLUMN].fill_null(0.0).cast(pl.Float64).to_numpy().astype(np.float64, copy=True)
    )
    development = (
        frame[DEVELOPMENT_COLUMN].fill_null(0.0).cast(pl.Float64).to_numpy().astype(np.float64, copy=True)
    )

    population: dict[str, np.ndarray] = {}
    for column in frame.columns:
        if column.startswith(POPULATION_PREFIX):
            population[column] = (
                frame[column].fill_null(0.0).cast(pl.Float64).to_numpy().astype(np.float64, copy=True)
            )
    if not population:
        raise ValueError("no population_* columns matched")

    reserved = {
        "location_tag",
        "province",
        LOCATION_RANK_COLUMN,
        "rank",
        FOOD_COLUMN,
        TOTAL_POPULATION_COLUMN,
        POPULATION_CAPACITY_COLUMN,
        PROSPERITY_COLUMN,
        DEVELOPMENT_COLUMN,
        *population,
        *TRACKED_MODIFIER_KEYS,
        "food_consumption",
        "months_stored",
        "food_growth_scale_years",
        PEASANT_EMPLOYMENT_COLUMN,
        EMPLOYED_PEASANTS_COLUMN,
        UNEMPLOYED_PEASANTS_COLUMN,
    }
    extras_float: dict[str, np.ndarray] = {}
    extras_str: dict[str, np.ndarray] = {}
    for column in frame.columns:
        if column in reserved or column.startswith("src__"):
            continue
        series = frame[column]
        dtype = series.dtype
        if dtype in (pl.Float32, pl.Float64, pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64):
            extras_float[column] = series.fill_null(0.0).cast(pl.Float64).to_numpy().astype(np.float64, copy=True)
        elif dtype == pl.Boolean:
            extras_float[column] = series.fill_null(False).cast(pl.Float64).to_numpy().astype(np.float64, copy=True)
        else:
            extras_str[column] = series.cast(pl.String).fill_null("").to_numpy()

    province_labels, province_codes = np.unique(province, return_inverse=True)
    province_codes = province_codes.astype(np.int32, copy=False)

    rank_map = {
        str(row[LOCATION_RANK_COLUMN]): float(row.get(_GROWTH_KEY, 0.0) or 0.0)
        for row in context.rank_baselines.to_dicts()
    }
    rank_population_growth = np.array(
        [rank_map.get(str(rank), 0.0) for rank in location_rank],
        dtype=np.float64,
    )

    capacity_pressure = dict(context.capacity_pressure)
    capacity_food_consumption: dict[str, dict[str, float]] = {}
    pop_terms: list[tuple[np.ndarray, float, np.ndarray | None, str]] = []
    for pop_type, rate in sorted(context.pop_food_rates.items()):
        column = f"{POPULATION_PREFIX}{pop_type}"
        if column not in population:
            continue
        modifier_column = pop_food_consumption_modifier_column(pop_type)
        modifier = None
        if modifier_column in frame.columns:
            modifier = (
                frame[modifier_column]
                .fill_null(0.0)
                .cast(pl.Float64)
                .to_numpy()
                .astype(np.float64, copy=True)
            )
            extras_float.pop(modifier_column, None)
        elif modifier_column in extras_float:
            modifier = extras_float.pop(modifier_column)
        pop_terms.append((population[column], float(rate), modifier, pop_type))
        capacity_food_consumption[pop_type] = _capacity_effect_lookup(
            capacity_pressure,
            modifier_column,
        )
    if not pop_terms:
        raise ValueError("no population_* columns matched pop_food_rates")

    peasant_employment = (
        frame[PEASANT_EMPLOYMENT_COLUMN]
        .fill_null(0.0)
        .cast(pl.Float64)
        .to_numpy()
        .astype(np.float64, copy=True)
    )
    employed_peasants = (
        frame[EMPLOYED_PEASANTS_COLUMN]
        .fill_null(0.0)
        .cast(pl.Float64)
        .to_numpy()
        .astype(np.float64, copy=True)
    )
    unemployed_peasants = (
        frame[UNEMPLOYED_PEASANTS_COLUMN]
        .fill_null(0.0)
        .cast(pl.Float64)
        .to_numpy()
        .astype(np.float64, copy=True)
    )

    return NumPyLocationState(
        location_tag=np.asarray(location_tag),
        province=np.asarray(province),
        location_rank=np.asarray(location_rank),
        food=food,
        total_population=total_population,
        population=population,
        extras_float=extras_float,
        extras_str=extras_str,
        province_codes=province_codes,
        province_labels=province_labels,
        rank_population_growth=rank_population_growth,
        pop_terms=pop_terms,
        peasant_employment=peasant_employment,
        employed_peasants=employed_peasants,
        unemployed_peasants=unemployed_peasants,
        population_capacity=population_capacity,
        prosperity=prosperity,
        development=development,
        prosperity_baselines=context.prosperity,
        capacity_pressure=capacity_pressure,
        capacity_food_consumption=capacity_food_consumption,
        capacity_monthly_food=_capacity_effect_lookup(capacity_pressure, LOCAL_MONTHLY_FOOD_KEY),
        capacity_population_growth=_capacity_effect_lookup(
            capacity_pressure, LOCAL_POPULATION_GROWTH_KEY
        ),
        food_growth_population_baseline=float(
            context.food_growth_baselines.get(_GROWTH_KEY, 0.0)
        ),
        food_growth_prosperity_baseline=float(
            context.prosperity.food_growth_monthly_prosperity
            if context.prosperity is not None
            else context.food_growth_baselines.get("local_monthly_prosperity", 0.0)
        ),
        growth_cap_years=float(context.growth_cap_years),
        subsistence_agriculture=float(context.subsistence_agriculture),
        food_decay_rate=float(context.food_decay_rate),
        n_provinces=int(province_labels.shape[0]),
    )


def column_array(state: NumPyLocationState, column: str) -> np.ndarray:
    """Resolve a state column name to a NumPy array."""
    if column == "location_tag":
        return state.location_tag
    if column == "province":
        return state.province
    if column == LOCATION_RANK_COLUMN:
        return state.location_rank
    if column == FOOD_COLUMN:
        return state.food
    if column == TOTAL_POPULATION_COLUMN:
        return state.total_population
    if column == POPULATION_CAPACITY_COLUMN:
        return state.population_capacity
    if column == PROSPERITY_COLUMN:
        return state.prosperity
    if column == DEVELOPMENT_COLUMN:
        return state.development
    if column == PEASANT_EMPLOYMENT_COLUMN:
        return state.peasant_employment
    if column == EMPLOYED_PEASANTS_COLUMN:
        return state.employed_peasants
    if column == UNEMPLOYED_PEASANTS_COLUMN:
        return state.unemployed_peasants
    if column in state.population:
        return state.population[column]
    if column in state.extras_float:
        return state.extras_float[column]
    if column in state.extras_str:
        return state.extras_str[column]
    raise KeyError(column)
