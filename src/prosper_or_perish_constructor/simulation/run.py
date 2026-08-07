"""Simulation runner with opt-in history tracking."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import polars as pl

from prosper_or_perish_constructor.simulation.modifiers import SimulationModifierContext
from prosper_or_perish_constructor.simulation.numpy_engine import (
    NumPyLocationState,
    numpy_state_from_polars,
)
from prosper_or_perish_constructor.simulation.trackers import TrackerSpec, require_tracker


class Simulation:
    """Advance location state month-by-month with optional named history trackers.

    Monthly stepping uses a NumPy engine. Trackers are computed/stored only after
    ``track(...)``; with none registered, ``run`` only advances state.
    """

    def __init__(
        self,
        state: pl.DataFrame,
        context: SimulationModifierContext,
    ) -> None:
        self.context = context
        self.tick = 0
        self._tracked: list[str] = []
        self._specs: dict[str, TrackerSpec] = {}
        self._buffers: dict[str, list[pl.DataFrame]] = {}
        self._history_cache: dict[str, pl.DataFrame] | None = None
        self._recorded_tick_zero = False
        self._engine: NumPyLocationState = numpy_state_from_polars(state, context)
        self._state_cache: pl.DataFrame | None = None

    @property
    def state(self) -> pl.DataFrame:
        if self._state_cache is None:
            self._state_cache = self._engine.to_polars()
        return self._state_cache

    @state.setter
    def state(self, value: pl.DataFrame) -> None:
        self._engine = numpy_state_from_polars(value, self.context)
        self._state_cache = None

    def track(self, name: str) -> Simulation:
        """Register a named tracker. No sampling happens until ``run`` / ``record``."""
        spec = require_tracker(name)
        if name not in self._specs:
            self._tracked.append(name)
            self._specs[name] = spec
            self._buffers[name] = []
            self._history_cache = None
        return self

    @property
    def tracked(self) -> tuple[str, ...]:
        return tuple(self._tracked)

    def record(self) -> None:
        """Sample currently registered trackers for ``self.tick`` (no-op if none)."""
        if not self._tracked:
            return
        for name in self._tracked:
            self._buffers[name].append(self._specs[name].sample_numpy(self._engine, tick=self.tick))
        self._history_cache = None

    def run(self, months: int, *, progress: bool = True) -> pl.DataFrame:
        """Advance ``months`` one-month ticks, recording registered trackers each step.

        Records tick 0 once on the first ``run`` call (before any advance), then ticks
        ``1..months`` after each monthly advance. Does no tracker work when nothing is
        registered.

        ``progress=True`` (default) shows a tqdm progress bar in notebooks/terminals.
        """
        if months < 0:
            raise ValueError(f"months must be non-negative: {months}")

        if not self._recorded_tick_zero:
            self.record()
            self._recorded_tick_zero = True

        ticks: Any = range(months)
        if progress and months > 0:
            from tqdm.auto import tqdm

            ticks = tqdm(ticks, total=months, desc="simulation", unit="mo")

        for _ in ticks:
            self._engine.tick_one_month()
            self.tick += 1
            self._state_cache = None
            self.record()
        return self.state

    @property
    def history(self) -> Mapping[str, pl.DataFrame]:
        """Dict of ``tracker_name → DataFrame`` with columns ``tick``, keys…, ``value``.

        Only includes trackers that were registered. Empty registration ⇒ empty dict.
        """
        if self._history_cache is None:
            self._history_cache = {
                name: pl.concat(parts) if parts else self._specs[name].empty_frame()
                for name, parts in self._buffers.items()
            }
        return self._history_cache

    def __repr__(self) -> str:
        tracked = ", ".join(self._tracked) if self._tracked else "(none)"
        return f"Simulation(tick={self.tick}, tracked=[{tracked}])"
