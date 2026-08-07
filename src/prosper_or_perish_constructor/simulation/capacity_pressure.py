"""Population-capacity pressure bands (abundant / available / overpopulation)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from eu5gameparser.domain.static_modifiers import load_static_modifier_data

ABUNDANT_FREE_LAND = "abundant_free_land"
AVAILABLE_FREE_LAND = "available_free_land"
OVERPOPULATION = "overpopulation"

CAPACITY_PRESSURE_MODIFIERS = (
    ABUNDANT_FREE_LAND,
    AVAILABLE_FREE_LAND,
    OVERPOPULATION,
)

# Fill ratio thresholds: abundant < 10%, available in [10%, 100%], overpopulation > 100%.
ABUNDANT_FILL_MAX = 0.10
AVAILABLE_FILL_MAX = 1.0
# Vanilla / PP: abundant also requires absolute population below 10 (10k people in game units).
ABUNDANT_POPULATION_MAX = 10.0

POPULATION_CAPACITY_COLUMN = "local_population_capacity"
LOCAL_MONTHLY_FOOD_KEY = "local_monthly_food"
LOCAL_POPULATION_GROWTH_KEY = "local_population_growth"


@dataclass(frozen=True)
class CapacityPressureBand:
    """One exclusive capacity-pressure static modifier and its parsed effect baselines."""

    name: str
    effects: Mapping[str, float]

    def get(self, key: str, default: float = 0.0) -> float:
        return float(self.effects.get(key, default) or 0.0)


def load_capacity_pressure_baselines(
    *,
    profile: str,
    load_order_path: str | Path,
) -> dict[str, CapacityPressureBand]:
    """Load the three capacity-pressure static modifiers from the constructor profile."""
    static = load_static_modifier_data(profile=profile, load_order_path=load_order_path)
    bands: dict[str, CapacityPressureBand] = {}
    for name in CAPACITY_PRESSURE_MODIFIERS:
        entry = static._by_name.get(name)
        if entry is None:
            raise ValueError(f"missing static modifier {name!r}")
        effects: dict[str, float] = {}
        for key, value in dict(entry.modifiers).items():
            if isinstance(value, bool):
                continue
            try:
                effects[str(key)] = float(value)
            except (TypeError, ValueError):
                continue
        bands[name] = CapacityPressureBand(name=name, effects=effects)
    return bands


def capacity_fill_ratio(population: float, capacity: float) -> float:
    """``population / capacity``; ``0`` when both empty, ``inf`` when pop>0 and capacity<=0."""
    pop = max(float(population), 0.0)
    cap = float(capacity)
    if cap > 0.0:
        return pop / cap
    if pop > 0.0:
        return float("inf")
    return 0.0


def capacity_pressure_strength(
    population: float,
    capacity: float,
) -> tuple[str | None, float]:
    """Return ``(modifier_name, strength)`` for the exclusive capacity-pressure band.

    - ``abundant_free_land``: fill in ``[0, 0.10)`` and population ``< 10``;
      strength ``1 - fill`` (in ``[0, 1]``).
    - ``available_free_land``: fill in ``[0.10, 1.0]``;
      strength ``1 - fill`` (in ``[0, 1]``).
    - ``overpopulation``: fill ``> 1.0``;
      strength ``fill - 1`` (1.0 at 2× capacity, uncapped above that).
    """
    pop = max(float(population), 0.0)
    cap = float(capacity)
    if not (cap > 0.0):
        return None, 0.0

    fill = pop / cap
    if fill > AVAILABLE_FILL_MAX:
        return OVERPOPULATION, fill - 1.0
    if fill >= ABUNDANT_FILL_MAX:
        return AVAILABLE_FREE_LAND, 1.0 - fill
    if pop < ABUNDANT_POPULATION_MAX:
        return ABUNDANT_FREE_LAND, 1.0 - fill
    return None, 0.0


def capacity_pressure_strength_arrays(
    population: np.ndarray,
    capacity: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Vectorized exclusive band strengths.

    Returns masks ``(abundant, available, overpopulation)`` and a single ``strength``
    array (0 where no band applies).
    """
    pop = np.maximum(np.asarray(population, dtype=np.float64), 0.0)
    cap = np.asarray(capacity, dtype=np.float64)
    strength = np.zeros(pop.shape, dtype=np.float64)
    abundant = np.zeros(pop.shape, dtype=bool)
    available = np.zeros(pop.shape, dtype=bool)
    overpopulation = np.zeros(pop.shape, dtype=bool)

    valid = cap > 0.0
    if not np.any(valid):
        return abundant, available, overpopulation, strength

    fill = np.zeros(pop.shape, dtype=np.float64)
    fill[valid] = pop[valid] / cap[valid]

    over_mask = valid & (fill > AVAILABLE_FILL_MAX)
    avail_mask = valid & (fill >= ABUNDANT_FILL_MAX) & (fill <= AVAILABLE_FILL_MAX)
    abund_mask = valid & (fill < ABUNDANT_FILL_MAX) & (pop < ABUNDANT_POPULATION_MAX)

    overpopulation[over_mask] = True
    available[avail_mask] = True
    abundant[abund_mask] = True

    strength[over_mask] = fill[over_mask] - 1.0
    strength[avail_mask] = 1.0 - fill[avail_mask]
    strength[abund_mask] = 1.0 - fill[abund_mask]
    return abundant, available, overpopulation, strength


def food_consumption_modifier_keys(effects: Mapping[str, float]) -> tuple[str, ...]:
    """Keys like ``local_peasants_food_consumption`` present on a modifier."""
    return tuple(
        sorted(
            key
            for key in effects
            if key.startswith("local_") and key.endswith("_food_consumption")
        )
    )


def scaled_effect(baseline: float, strength: float) -> float:
    return float(baseline) * float(strength)


def merge_capacity_pressure_effects(
    bands: Mapping[str, CapacityPressureBand],
    *,
    active_name: str | None,
    strength: float,
) -> dict[str, float]:
    """Scale all effects of the active band by ``strength`` (empty if none)."""
    if active_name is None or strength == 0.0:
        return {}
    band = bands[active_name]
    return {key: scaled_effect(value, strength) for key, value in band.effects.items()}
