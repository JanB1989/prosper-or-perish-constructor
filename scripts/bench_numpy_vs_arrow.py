"""Compare NumPy vs PyArrow for a 100-month simulation hot loop."""

from __future__ import annotations

import time

import numpy as np
import polars as pl
import pyarrow as pa
import pyarrow.compute as pc

MONTHS = 100
N = 9
GROWTH_CAP_YEARS = 2.0
FOOD_GROWTH_BASE = 0.01
RANK_GROWTH = -0.005


def _seed_state() -> dict[str, np.ndarray]:
    rng = np.random.default_rng(0)
    province = np.array([0, 0, 0, 0, 0, 0, 1, 1, 1], dtype=np.int32)  # 2 provinces
    pops = {
        "peasants": rng.uniform(1000, 5000, N),
        "burghers": rng.uniform(0, 400, N),
        "clergy": rng.uniform(0, 20, N),
    }
    rates = {"peasants": 0.1, "burghers": 0.2, "clergy": 0.15}
    total = sum(pops.values())
    food = total * rates["peasants"] * 24.0  # rough cap fill
    rank = np.full(N, RANK_GROWTH, dtype=np.float64)
    return {
        "province": province,
        "food": food.astype(np.float64),
        "rank_growth": rank,
        "total_population": total.astype(np.float64),
        **{k: v.astype(np.float64) for k, v in pops.items()},
        "_rates": rates,  # type: ignore[dict-item]
    }


def _numpy_tick(state: dict, rates: dict[str, float]) -> None:
    consumption = np.zeros(N, dtype=np.float64)
    for name, rate in rates.items():
        consumption += state[name] * rate

    # province aggregates
    prov_ids = np.unique(state["province"])
    scale = np.zeros(N, dtype=np.float64)
    for pid in prov_ids:
        mask = state["province"] == pid
        c = float(consumption[mask].sum())
        f = float(state["food"][mask].sum())
        months = (f / c) if c > 0 else 0.0
        years = min(max(months / 12.0, 0.0), GROWTH_CAP_YEARS)
        scale[mask] = years

    yearly = state["rank_growth"] + FOOD_GROWTH_BASE * scale
    mult = (1.0 + yearly) ** (1.0 / 12.0)
    for name in rates:
        state[name] *= mult
    state["total_population"] *= mult


def _arrow_tick(table: pa.Table, rates: dict[str, float]) -> pa.Table:
    consumption = pa.array(np.zeros(table.num_rows, dtype=np.float64))
    for name, rate in rates.items():
        consumption = pc.add(consumption, pc.multiply(table[name], rate))

    province = table["province"].to_numpy()
    food = table["food"].to_numpy()
    cons = consumption.to_numpy()
    scale = np.zeros(table.num_rows, dtype=np.float64)
    for pid in np.unique(province):
        mask = province == pid
        c = float(cons[mask].sum())
        f = float(food[mask].sum())
        months = (f / c) if c > 0 else 0.0
        years = min(max(months / 12.0, 0.0), GROWTH_CAP_YEARS)
        scale[mask] = years

    rank = table["rank_growth"].to_numpy()
    yearly = rank + FOOD_GROWTH_BASE * scale
    mult = (1.0 + yearly) ** (1.0 / 12.0)
    mult_arr = pa.array(mult)

    cols = []
    names = []
    for name in table.column_names:
        if name in rates or name == "total_population":
            cols.append(pc.multiply(table[name], mult_arr))
        else:
            cols.append(table[name])
        names.append(name)
    return pa.table(cols, names=names)


def _polars_tick(df: pl.DataFrame, rates: dict[str, float], rank_baselines: pl.DataFrame) -> pl.DataFrame:
    """Closest stand-in for current advance_tick cost (simplified modifiers)."""
    from prosper_or_perish_constructor.simulation.capacity_pressure import (
        ABUNDANT_FREE_LAND,
        AVAILABLE_FREE_LAND,
        OVERPOPULATION,
        CapacityPressureBand,
    )
    from prosper_or_perish_constructor.simulation.modifiers import SimulationModifierContext, apply_food_growth_and_rank_modifiers
    from prosper_or_perish_constructor.simulation.food import compute_location_food_consumption
    from prosper_or_perish_constructor.simulation.population import apply_population_growth
    from prosper_or_perish_constructor.simulation.modifiers import finalize_location_state
    from prosper_or_perish_constructor.simulation.prosperity import ProsperityBaselines

    ctx = SimulationModifierContext(
        pop_food_rates=rates,
        growth_cap_years=GROWTH_CAP_YEARS,
        food_growth_baselines={
            "local_population_growth": FOOD_GROWTH_BASE,
            "local_monthly_prosperity": 0.0,
            "local_province_food_sales_output_modifier": 0.0,
            "local_province_food_purchase_output_modifier": 0.0,
        },
        rank_baselines=rank_baselines,
        subsistence_agriculture=1.2,
        capacity_pressure={
            ABUNDANT_FREE_LAND: CapacityPressureBand(ABUNDANT_FREE_LAND, {}),
            AVAILABLE_FREE_LAND: CapacityPressureBand(AVAILABLE_FREE_LAND, {}),
            OVERPOPULATION: CapacityPressureBand(OVERPOPULATION, {}),
        },
        prosperity=ProsperityBaselines(
            base_monthly_prosperity=0.0,
            food_growth_monthly_prosperity=0.0,
            global_prosperity_decay=0.0,
            local_prosperity_decay=0.0,
            effects={},
        ),
    )
    frame = compute_location_food_consumption(df, rates)
    frame = apply_food_growth_and_rank_modifiers(frame, ctx)
    frame = apply_population_growth(frame, months=1)
    return finalize_location_state(frame)


def bench(label: str, fn) -> float:
    # warmup
    fn()
    t0 = time.perf_counter()
    fn()
    dt = time.perf_counter() - t0
    print(f"{label}: {MONTHS / dt:,.0f} ticks/s  ({dt*1000:.2f} ms / {MONTHS} mo)")
    return dt


def main() -> None:
    seed = _seed_state()
    rates = seed.pop("_rates")  # type: ignore[misc]

    # NumPy
    def run_numpy() -> None:
        state = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in seed.items()}
        for _ in range(MONTHS):
            _numpy_tick(state, rates)

    # Arrow (table rebuild each tick; province agg still via numpy masks for fairness on small N)
    def run_arrow() -> None:
        arrays = {k: pa.array(v) for k, v in seed.items()}
        table = pa.table(arrays)
        for _ in range(MONTHS):
            table = _arrow_tick(table, rates)

    # Current Polars path (control)
    rank_baselines = pl.DataFrame(
        {
            "location_rank": ["rural_settlement", "town"],
            "local_population_growth": [RANK_GROWTH, RANK_GROWTH],
            "local_monthly_prosperity": [0.0, 0.0],
            "local_province_food_sales_output_modifier": [0.0, 0.0],
            "local_province_food_purchase_output_modifier": [0.0, 0.0],
        }
    )
    df0 = pl.DataFrame(
        {
            "location_tag": [f"loc_{i}" for i in range(N)],
            "province": [f"p{pid}" for pid in seed["province"].tolist()],
            "location_rank": ["town" if i == 0 else "rural_settlement" for i in range(N)],
            "food": seed["food"].tolist(),
            "population_peasants": seed["peasants"].tolist(),
            "population_burghers": seed["burghers"].tolist(),
            "population_clergy": seed["clergy"].tolist(),
            "total_population": seed["total_population"].tolist(),
            "development": [20.0] * N,
            "prosperity": [0.0] * N,
        }
    )

    def run_polars() -> None:
        df = df0.clone()
        for _ in range(MONTHS):
            df = _polars_tick(df, rates, rank_baselines)

    print(f"N={N} locations, months={MONTHS}")
    bench("NumPy hot loop", run_numpy)
    bench("PyArrow table loop", run_arrow)
    bench("Polars advance_tick-like", run_polars)


if __name__ == "__main__":
    main()
