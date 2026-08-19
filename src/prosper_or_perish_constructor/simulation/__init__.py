"""Vectorized game-state simulation (outer tick layer)."""

from prosper_or_perish_constructor.simulation.modifiers import (
    SimulationModifierContext,
    load_simulation_modifier_context,
)
from prosper_or_perish_constructor.simulation.population import apply_population_growth
from prosper_or_perish_constructor.simulation.capacity_pressure import (
    CapacityPressureBand,
    load_capacity_pressure_baselines,
)
from prosper_or_perish_constructor.simulation.capacity_model import PopulationCapacityFormula
from prosper_or_perish_constructor.simulation.run import Simulation
from prosper_or_perish_constructor.simulation.tick import advance_tick, prepare_start_locations
from prosper_or_perish_constructor.simulation.trackers import list_trackers

__all__ = [
    "CapacityPressureBand",
    "PopulationCapacityFormula",
    "Simulation",
    "SimulationModifierContext",
    "advance_tick",
    "apply_population_growth",
    "list_trackers",
    "load_capacity_pressure_baselines",
    "load_simulation_modifier_context",
    "prepare_start_locations",
]
