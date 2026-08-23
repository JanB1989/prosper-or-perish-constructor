"""Adjustable population-capacity formula used by long-run simulation profiles."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

BASE_POPULATION_CAPACITY_COLUMN = "base_population_capacity"
INFRASTRUCTURE_POPULATION_CAPACITY_COLUMN = "infrastructure_population_capacity"
PHYSICAL_POPULATION_CAPACITY_COLUMN = "physical_population_capacity"
GAEZ_ZERO_DEVELOPMENT_CAPACITY_COLUMN = "gaez_zero_development_capacity"
HYDE_RAINFED_CAPACITY_EVIDENCE_COLUMN = "hyde_rainfed_capacity_evidence"
ZERO_DEVELOPMENT_CAPACITY_COLUMN = "zero_development_population_capacity"
IRRIGATION_LEVELS_COLUMN = "irrigation_systems_levels"
IRRIGATION_LEGAL_CAP_COLUMN = "irrigation_systems_legal_cap"


@dataclass(frozen=True)
class PopulationCapacityFormula:
    """Recompute capacity from location potential, infrastructure, and development.

    All absolute values use EU5 population units (one unit is 1,000 people in the
    current profile). Relative values are additive fractions applied after the
    absolute terms have been summed.
    """

    development_relative: float = 0.0
    global_relative: float = 0.0
    development_min: float = 0.0
    development_max: float = 100.0
    minimum_capacity: float = 0.0

    def __post_init__(self) -> None:
        numeric = {
            "development_relative": self.development_relative,
            "global_relative": self.global_relative,
            "development_min": self.development_min,
            "development_max": self.development_max,
            "minimum_capacity": self.minimum_capacity,
        }
        invalid = [name for name, value in numeric.items() if not np.isfinite(float(value))]
        if invalid:
            raise ValueError(f"non-finite population-capacity settings: {', '.join(invalid)}")
        if self.development_relative < 0.0:
            raise ValueError("development_relative must be non-negative")
        if not -0.5 <= self.global_relative <= 0.0:
            raise ValueError("global_relative must be in -0.5..0.0")
        if self.development_max < self.development_min:
            raise ValueError("development_max must be at least development_min")
        if self.minimum_capacity < 0.0:
            raise ValueError("minimum_capacity must be non-negative")

    def evaluate(
        self,
        *,
        base_capacity: np.ndarray,
        development: np.ndarray,
        infrastructure_capacity: np.ndarray | None = None,
    ) -> np.ndarray:
        """Return the location-sized capacity array for the current state."""

        base = np.maximum(np.asarray(base_capacity, dtype=np.float64), 0.0)
        dev = np.clip(
            np.asarray(development, dtype=np.float64),
            float(self.development_min),
            float(self.development_max),
        )
        infrastructure = (
            np.zeros_like(base)
            if infrastructure_capacity is None
            else np.maximum(np.asarray(infrastructure_capacity, dtype=np.float64), 0.0)
        )
        if not (base.shape == dev.shape == infrastructure.shape):
            raise ValueError("population-capacity inputs must have matching shapes")

        absolute = base + infrastructure
        relative = 1.0 + dev * float(self.development_relative) + float(self.global_relative)
        modeled = np.maximum(absolute * np.maximum(relative, 0.0), 0.0)
        return np.maximum(
            modeled,
            np.full(modeled.shape, float(self.minimum_capacity), dtype=np.float64),
        )
