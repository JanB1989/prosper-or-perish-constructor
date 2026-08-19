"""Adjustable population-capacity formula used by long-run simulation profiles."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

BASE_POPULATION_CAPACITY_COLUMN = "base_population_capacity"
IRRIGATION_LEVELS_COLUMN = "irrigation_systems_levels"
IRRIGATION_LEGAL_CAP_COLUMN = "irrigation_systems_legal_cap"


@dataclass(frozen=True)
class PopulationCapacityFormula:
    """Recompute capacity from physical potential, development, and irrigation.

    All absolute values use EU5 population units (one unit is 1,000 people in the
    current profile). Relative values are additive fractions applied after the
    absolute terms have been summed.
    """

    physical_scale: float = 1.0
    development_absolute: float = 0.0
    development_relative: float = 0.0
    irrigation_absolute: float = 0.0
    irrigation_relative: float = 0.0
    development_min: float = 0.0
    development_max: float = 100.0
    minimum_capacity: float = 0.0

    def __post_init__(self) -> None:
        numeric = {
            "physical_scale": self.physical_scale,
            "development_absolute": self.development_absolute,
            "development_relative": self.development_relative,
            "irrigation_absolute": self.irrigation_absolute,
            "irrigation_relative": self.irrigation_relative,
            "development_min": self.development_min,
            "development_max": self.development_max,
            "minimum_capacity": self.minimum_capacity,
        }
        invalid = [name for name, value in numeric.items() if not np.isfinite(float(value))]
        if invalid:
            raise ValueError(f"non-finite population-capacity settings: {', '.join(invalid)}")
        if self.physical_scale < 0.0:
            raise ValueError("physical_scale must be non-negative")
        if self.development_max < self.development_min:
            raise ValueError("development_max must be at least development_min")
        if self.minimum_capacity < 0.0:
            raise ValueError("minimum_capacity must be non-negative")

    def evaluate(
        self,
        *,
        base_capacity: np.ndarray,
        development: np.ndarray,
        irrigation_levels: np.ndarray,
    ) -> np.ndarray:
        """Return the location-sized capacity array for the current state."""

        base = np.maximum(np.asarray(base_capacity, dtype=np.float64), 0.0)
        dev = np.clip(
            np.asarray(development, dtype=np.float64),
            float(self.development_min),
            float(self.development_max),
        )
        irrigation = np.maximum(np.asarray(irrigation_levels, dtype=np.float64), 0.0)
        if not (base.shape == dev.shape == irrigation.shape):
            raise ValueError("population-capacity inputs must have matching shapes")

        absolute = (
            base * float(self.physical_scale)
            + dev * float(self.development_absolute)
            + irrigation * float(self.irrigation_absolute)
        )
        relative = (
            1.0
            + dev * float(self.development_relative)
            + irrigation * float(self.irrigation_relative)
        )
        modeled = np.maximum(absolute * np.maximum(relative, 0.0), 0.0)
        return np.maximum(
            modeled,
            np.full(modeled.shape, float(self.minimum_capacity), dtype=np.float64),
        )
