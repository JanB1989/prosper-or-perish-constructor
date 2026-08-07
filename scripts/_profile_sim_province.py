#!/usr/bin/env python3
"""Profile Simulation for a single province (luneburger_heide_province)."""

from __future__ import annotations

import cProfile
import os
import pstats
import time
from io import StringIO
from pathlib import Path

import polars as pl

from prosper_or_perish_constructor.farming_village_unlocks import load_start_location_frame
from prosper_or_perish_constructor.simulation import (
    Simulation,
    advance_tick,
    load_simulation_modifier_context,
)

PROFILE = os.environ.get("PROFILE", "constructor")
LOAD_ORDER = Path(os.environ.get("LOAD_ORDER", "constructor.load_order.toml"))
REPO = Path(os.environ.get("REPO", ".")).resolve()
PROJECT = REPO / "constructor.toml"
PROVINCE = "luneburger_heide_province"
MONTHS = 200


def load_province_state():
    locations = load_start_location_frame(REPO, PROJECT)
    context = load_simulation_modifier_context(
        profile=PROFILE,
        load_order_path=LOAD_ORDER,
    )
    state = locations.filter(pl.col("province") == PROVINCE)
    if state.height == 0:
        raise SystemExit(f"no locations for province={PROVINCE!r}")
    return state, context


def main() -> None:
    print(f"REPO={REPO}")
    print(f"PROFILE={PROFILE} LOAD_ORDER={LOAD_ORDER}")
    print(f"province={PROVINCE} months={MONTHS}")

    state0, context = load_province_state()
    print(f"locations in province: {state0.height}")

    # cProfile of full tracked run
    sim = Simulation(state0.clone(), context)
    sim.track("province_total_population")

    profiler = cProfile.Profile()
    profiler.enable()
    sim.run(months=MONTHS, progress=False)
    profiler.disable()

    stream = StringIO()
    stats = pstats.Stats(profiler, stream=stream).sort_stats("cumulative")
    stats.print_stats(40)
    print()
    print("===== cProfile top 40 (cumulative) =====")
    print(stream.getvalue(), end="")

    # throughput: advance_tick alone (no tracking)
    state, ctx = load_province_state()
    t0 = time.perf_counter()
    for _ in range(MONTHS):
        state = advance_tick(state, ctx, months=1)
    advance_secs = time.perf_counter() - t0
    advance_tps = MONTHS / advance_secs

    # throughput: record/sample alone
    state, ctx = load_province_state()
    sim_rec = Simulation(state, ctx)
    sim_rec.track("province_total_population")
    t0 = time.perf_counter()
    for i in range(MONTHS):
        sim_rec.tick = i
        sim_rec.record()
    record_secs = time.perf_counter() - t0
    record_tps = MONTHS / record_secs

    # throughput: full sim.run with tracking
    state, ctx = load_province_state()
    sim_full = Simulation(state, ctx)
    sim_full.track("province_total_population")
    t0 = time.perf_counter()
    sim_full.run(months=MONTHS, progress=False)
    full_secs = time.perf_counter() - t0
    full_tps = MONTHS / full_secs

    print()
    print("===== throughput (200 months) =====")
    print(f"advance_tick alone: {advance_secs:.4f}s  -> {advance_tps:.2f} ticks/sec")
    print(f"record/sample alone: {record_secs:.4f}s  -> {record_tps:.2f} ticks/sec")
    print(f"full sim.run + tracking: {full_secs:.4f}s  -> {full_tps:.2f} ticks/sec")


if __name__ == "__main__":
    main()
