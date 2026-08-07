"""Profile Simulation.run throughput for one province."""

from __future__ import annotations

import cProfile
import pstats
import time
from pathlib import Path

from prosper_or_perish_constructor.farming_village_unlocks import load_start_location_frame
from prosper_or_perish_constructor.simulation import (
    Simulation,
    advance_tick,
    load_simulation_modifier_context,
)
from prosper_or_perish_constructor.simulation.trackers import require_tracker

REPO = Path(__file__).resolve().parents[1]
LOAD_ORDER = REPO / "constructor.load_order.toml"
MONTHS = 200
PROVINCE = "luneburger_heide_province"


def main() -> None:
    locations = load_start_location_frame(REPO, REPO / "constructor.toml")
    context = load_simulation_modifier_context(
        profile="constructor",
        load_order_path=LOAD_ORDER,
    )
    state0 = locations.filter(locations["province"] == PROVINCE)
    print(f"locations in province: {state0.height}")

    # --- throughput: advance_tick only ---
    state = state0.clone()
    t0 = time.perf_counter()
    for _ in range(MONTHS):
        state = advance_tick(state, context, months=1)
    dt = time.perf_counter() - t0
    print(f"advance_tick only: {MONTHS / dt:.1f} ticks/s ({dt:.3f}s for {MONTHS})")

    # --- throughput: record/sample only ---
    state = state0.clone()
    spec = require_tracker("province_total_population")
    buf: list = []
    t0 = time.perf_counter()
    for tick in range(MONTHS + 1):
        buf.append(spec.sample(state, tick=tick))
    dt = time.perf_counter() - t0
    print(f"tracker sample only: {(MONTHS + 1) / dt:.1f} samples/s ({dt:.3f}s)")

    # --- throughput: full Simulation.run with tracking ---
    sim = Simulation(state0.clone(), context)
    sim.track("province_total_population")
    t0 = time.perf_counter()
    sim.run(months=MONTHS, progress=False)
    dt = time.perf_counter() - t0
    print(f"Simulation.run+track: {MONTHS / dt:.1f} ticks/s ({dt:.3f}s for {MONTHS})")

    # --- cProfile ---
    sim = Simulation(state0.clone(), context)
    sim.track("province_total_population")
    profiler = cProfile.Profile()
    profiler.enable()
    sim.run(months=MONTHS, progress=False)
    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats(pstats.SortKey.CUMULATIVE)
    print("\n=== cProfile top 40 (cumulative) ===")
    stats.print_stats(40)


if __name__ == "__main__":
    main()
