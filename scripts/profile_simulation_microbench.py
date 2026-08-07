"""Microbench Simulation without loading full game data."""

from __future__ import annotations

import cProfile
import pstats
import time

import polars as pl

from prosper_or_perish_constructor.simulation import Simulation, advance_tick
from prosper_or_perish_constructor.simulation.capacity_pressure import (
    ABUNDANT_FREE_LAND,
    AVAILABLE_FREE_LAND,
    OVERPOPULATION,
    CapacityPressureBand,
)
from prosper_or_perish_constructor.simulation.modifiers import SimulationModifierContext
from prosper_or_perish_constructor.simulation.prosperity import ProsperityBaselines
from prosper_or_perish_constructor.simulation.trackers import require_tracker

MONTHS = 500


def _context() -> SimulationModifierContext:
    keys = (
        "local_population_growth",
        "local_monthly_prosperity",
        "local_province_food_sales_output_modifier",
        "local_province_food_purchase_output_modifier",
    )
    empty = {
        ABUNDANT_FREE_LAND: CapacityPressureBand(ABUNDANT_FREE_LAND, {}),
        AVAILABLE_FREE_LAND: CapacityPressureBand(AVAILABLE_FREE_LAND, {}),
        OVERPOPULATION: CapacityPressureBand(OVERPOPULATION, {}),
    }
    return SimulationModifierContext(
        pop_food_rates={
            "peasants": 0.1,
            "burghers": 0.2,
            "clergy": 0.15,
            "nobles": 0.3,
            "laborers": 0.1,
            "soldiers": 0.1,
            "slaves": 0.05,
            "tribesmen": 0.08,
            "unknown": 0.1,
        },
        growth_cap_years=2.0,
        food_growth_baselines={k: 0.01 if k == "local_population_growth" else 0.0 for k in keys},
        rank_baselines=pl.DataFrame(
            {
                "location_rank": ["rural_settlement", "town"],
                "local_population_growth": [-0.005, -0.005],
                "local_monthly_prosperity": [0.0, 0.0],
                "local_province_food_sales_output_modifier": [0.0, 0.0],
                "local_province_food_purchase_output_modifier": [0.0, 0.0],
            }
        ),
        subsistence_agriculture=1.2,
        capacity_pressure=empty,
        prosperity=ProsperityBaselines(
            base_monthly_prosperity=0.0,
            food_growth_monthly_prosperity=0.0,
            global_prosperity_decay=0.0,
            local_prosperity_decay=0.0,
            effects={},
        ),
        food_decay_rate=0.01,
    )


def _state() -> pl.DataFrame:
    # ~9 locations like luneburger_heide_province
    n = 9
    return pl.DataFrame(
        {
            "location_tag": [f"loc_{i}" for i in range(n)],
            "province": ["luneburger_heide_province"] * n,
            "location_rank": ["town" if i == 0 else "rural_settlement" for i in range(n)],
            "food": [1000.0] * n,
            "population_peasants": [3000.0] * n,
            "population_burghers": [100.0] * n,
            "population_clergy": [5.0] * n,
            "population_nobles": [2.0] * n,
            "population_laborers": [0.0] * n,
            "population_soldiers": [0.0] * n,
            "population_slaves": [0.0] * n,
            "population_tribesmen": [0.0] * n,
            "population_unknown": [0.0] * n,
            "total_population": [3107.0] * n,
            "development": [20.0] * n,
            "prosperity": [0.0] * n,
        }
    )


def bench(label: str, fn) -> float:
    t0 = time.perf_counter()
    fn()
    dt = time.perf_counter() - t0
    print(f"{label}: {MONTHS / dt:.1f} ticks/s  ({dt:.3f}s / {MONTHS})")
    return dt


def main() -> None:
    context = _context()
    state0 = _state()

    def only_advance() -> None:
        state = state0.clone()
        for _ in range(MONTHS):
            state = advance_tick(state, context, months=1)

    def only_sample() -> None:
        state = state0.clone()
        spec = require_tracker("province_total_population")
        for tick in range(MONTHS):
            spec.sample(state, tick=tick)

    def full_run() -> None:
        sim = Simulation(state0.clone(), context)
        sim.track("province_total_population")
        sim.run(months=MONTHS, progress=False)

    def advance_no_finalize() -> None:
        # Approximate: call internals if needed — just advance_tick for now
        only_advance()

    bench("advance_tick only", only_advance)
    bench("tracker sample only", only_sample)
    bench("Simulation.run+track", full_run)

    sim = Simulation(state0.clone(), context)
    sim.track("province_total_population")
    pr = cProfile.Profile()
    pr.enable()
    sim.run(months=MONTHS, progress=False)
    pr.disable()
    stats = pstats.Stats(pr)
    stats.sort_stats(pstats.SortKey.CUMULATIVE)
    print("\n=== top 30 cumulative ===")
    stats.print_stats(30)
    print("\n=== top 30 tottime ===")
    stats.sort_stats(pstats.SortKey.TIME)
    stats.print_stats(30)

    # Component split inside one advance_tick via manual imports
    from prosper_or_perish_constructor.simulation.food import (
        FOOD_COLUMN,
        compute_location_food_consumption,
    )
    from prosper_or_perish_constructor.simulation.modifiers import (
        apply_food_growth_and_rank_modifiers,
        finalize_location_state,
    )
    from prosper_or_perish_constructor.simulation.population import apply_population_growth

    state = state0.clone()
    parts = {
        "compute_consumption": 0.0,
        "apply_modifiers": 0.0,
        "apply_growth": 0.0,
        "finalize": 0.0,
    }
    for _ in range(MONTHS):
        t0 = time.perf_counter()
        frame = compute_location_food_consumption(state, context.pop_food_rates)
        parts["compute_consumption"] += time.perf_counter() - t0
        t0 = time.perf_counter()
        frame = apply_food_growth_and_rank_modifiers(frame, context)
        parts["apply_modifiers"] += time.perf_counter() - t0
        t0 = time.perf_counter()
        frame = apply_population_growth(frame, months=1)
        parts["apply_growth"] += time.perf_counter() - t0
        t0 = time.perf_counter()
        state = finalize_location_state(frame)
        parts["finalize"] += time.perf_counter() - t0
    print("\n=== advance_tick component split ===")
    for name, dt in parts.items():
        print(f"{name}: {MONTHS / dt:.1f} equiv-ticks/s  ({dt:.3f}s total, {100 * dt / sum(parts.values()):.1f}%)")


if __name__ == "__main__":
    main()
