"""Start food model v2: the province food budget as the engine computes it at game start.

Fitted 2026-09-25 on the day-0 save of a fresh campaign (nb.eu5, 1337.4.1, 4,018 province-owner pools; production =
``base_food_consumption + cached_structural_food_change``):

* **Subsistence** is the define ``NLocation.SUBSISTENCE_AGRICULTURE`` per 1,000 jobless **peasants and slaves**,
  scaled by the location's static ``local_monthly_food_modifier`` stack (rank, climate/vegetation/topography classes,
  setup modifiers: all read from the game files; the World Builder class rows cancel the vanilla ones, so the stack is
  near zero) and by a fitted factor per rank and per climate (``yield_rank`` / ``yield_climate``). Jobless laborers
  produce nothing (their fitted coefficient is -0.03), so the engine's ~40 M setup laborers eat without farming.
* **Overpopulation** (the mod's ``overpopulation`` static modifier, scaled by pop / capacity - 1) adds
  ``local_peasants_food_consumption = +0.5`` per unit: a location at twice its capacity eats 50 % more peasant food.
  ``base_food_consumption`` leaves it out, the structural change carries it (fitted -0.47..-0.51 per peasant-unit).
  This, not the land, is why deserts and very-low-fertility land looked barren in the pre-plague analysis.
* **Building food** per staffed level: ``local_monthly_food`` (scaled by the stack) plus the Province Food good
  (``local_food``) of the method that runs. Farms, fishing and forest villages and orchards run Provisioning once
  stores are low; the cookery's dish slot runs Serve on ``cookery_serve_share`` of the levels (53 % in 1341, 49 % in
  1345 of the same campaign, 28 % in short pools: the engine picks by price, not by need) and Preserve (victuals) on
  the rest, and its container and drink slots make victuals on every level (0.67 per level on day 0); Victualler
  imports add +90, exports -90 per staffed level.

At day 0 the engine has not switched any farm to Provisioning nor any cookery to Serve yet (the setup reads full
stores), so ``day0`` in the budget leaves the Province Food out.

``[worldbuilder.start.food_model]`` in constructor.toml holds the numbers; ``ppc worldbuilder food-check`` refits the
yields from a save.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np

RANKS = ("rural_settlement", "town", "city", "megalopolis")
RANK_ORDER = {"megalopolis": 0, "city": 1, "town": 2, "rural_settlement": 3}

# fitted on nb.eu5 (1337.4.1) with the overpopulation term fixed at 0.5: food per 1,000 jobless peasants/slaves
# = define 1.5 x (1 + static stack) x rank factor x climate factor
DEFAULT_YIELD_RANK = {"rural_settlement": 1.037, "town": 1.016, "city": 0.972, "megalopolis": 0.911}
DEFAULT_YIELD_CLIMATE: dict[str, float] = {}
DEFAULT_CAPACITY = {
    # province food capacity (max_food_value) per pool, fitted on nb.eu5: R2 0.968
    "per_development": 31.97,
    "per_population_k": 3.65,
    "per_location": 99.9,
    "rank": {"town": 521.3, "city": 815.2, "megalopolis": 1240.8},
}


@dataclass(frozen=True)
class FoodModelConfig:
    """``[worldbuilder.start.food_model]``."""

    subsistence_pop_types: tuple[str, ...] = ("peasants", "slaves")
    yield_rank: Mapping[str, float] = field(default_factory=lambda: dict(DEFAULT_YIELD_RANK))
    yield_climate: Mapping[str, float] = field(default_factory=lambda: dict(DEFAULT_YIELD_CLIMATE))
    overpopulation_consumption: float = 0.5          # local_peasants_food_consumption per unit of pop / capacity - 1
    overpopulation_pop_types: tuple[str, ...] = ("peasants",)
    capacity: Mapping[str, Any] = field(default_factory=lambda: {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULT_CAPACITY.items()})
    start_food_share: float = 0.10                   # game rule pp_starting_province_food default: 10 % of capacity
    # placement v2
    market_victuals_per_level: float = 3.0           # victuals a staffed import buys / an export sells per month
    cookery_serve_share: float = 0.5                 # share of cookery levels whose dish slot runs Serve
    preserve_victuals_per_level: float = 0.64        # the dish slot on Preserve (nb.eu5: 1,471 victuals / 2,301 levels)
    cookery_victuals_other: float = 0.67             # container and drink slots, every level (nb.eu5: 1,540 / 2,301)
    victuals_target: float = 1.1                     # victuals supply >= demand x this per market
    export_surplus_share: float = 0.25               # a pool exports only above this surplus (share of its demand)
    export_min_capacity_months: float = 18.0         # ... and only if its store can reach the export band
    serve_raw_goods_share: float = 0.2               # share of a market's raw food output new Serve cookeries may use
    raw_goods_per_rgo_k: float = 1.5                 # raw food goods per 1,000 RGO workers (nb.eu5: 1.50 median)
    serve_fallback_raw_goods_share: float = 0.5      # raw goods share allowed when the market cannot afford imports
    import_priority_coverage: float = 0.85           # pools fed below this share come first for the market's victuals

    @classmethod
    def from_raw(cls, raw: Mapping[str, Any] | None) -> "FoodModelConfig":
        raw = dict(raw or {})
        kwargs: dict[str, Any] = {}
        for name in ("subsistence_pop_types", "overpopulation_pop_types"):
            if name in raw:
                kwargs[name] = tuple(str(v) for v in raw[name])
        for name in ("yield_rank", "yield_climate"):
            if isinstance(raw.get(name), Mapping):
                kwargs[name] = {str(k): float(v) for k, v in raw[name].items()}
        if isinstance(raw.get("capacity"), Mapping):
            cap = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULT_CAPACITY.items()}
            for k, v in raw["capacity"].items():
                cap[str(k)] = {str(a): float(b) for a, b in v.items()} if isinstance(v, Mapping) else float(v)
            kwargs["capacity"] = cap
        for name in ("overpopulation_consumption", "start_food_share", "market_victuals_per_level", "preserve_victuals_per_level",
                     "cookery_serve_share", "cookery_victuals_other",
                     "victuals_target", "export_surplus_share", "export_min_capacity_months", "serve_raw_goods_share",
                     "raw_goods_per_rgo_k", "serve_fallback_raw_goods_share", "import_priority_coverage"):
            if name in raw:
                kwargs[name] = float(raw[name])
        return cls(**kwargs)


# --------------------------------------------------------------------------------------------- terms
def static_food_modifier(rules, rank: str, classes: Mapping[str, Any], static_keys: Iterable[str] = ()) -> float:
    """The location's static ``local_monthly_food_modifier`` stack: rank and location classes (``Rules.food_modifier``)
    plus the static modifiers the setup places on it (fertility, soil, coast, lake, river level)."""
    total = float(rules.food_modifier(rank, classes)) if hasattr(rules, "food_modifier") else 0.0
    return total + statics_food_modifier(getattr(rules, "statics", {}) or {}, static_keys)


def statics_food_modifier(statics: Mapping[str, Any], keys: Iterable[str]) -> float:
    """Sum of ``local_monthly_food_modifier`` over the named static modifiers."""
    total = 0.0
    for key in keys:
        for entry in getattr(statics.get(key), "entries", []) or []:
            if entry.key == "local_monthly_food_modifier" and isinstance(entry.value, (int, float)):
                total += float(entry.value)
    return total


def location_yield(define: float, stack: float, rank: str | None, climate: str | None, cfg: FoodModelConfig) -> float:
    """Food per 1,000 jobless peasants/slaves per month."""
    return (
        float(define)
        * max(0.0, 1.0 + float(stack))
        * float(cfg.yield_rank.get(str(rank or "rural_settlement"), 1.0))
        * float(cfg.yield_climate.get(str(climate or ""), 1.0))
    )


def overpopulation_food(peasants_k: float, pop_k: float, capacity_k: float, cfg: FoodModelConfig) -> float:
    """Extra food the location's peasants eat under the ``overpopulation`` modifier (per month)."""
    if capacity_k <= 0 or pop_k <= capacity_k:
        return 0.0
    return float(cfg.overpopulation_consumption) * max(0.0, peasants_k) * (pop_k / capacity_k - 1.0)


def food_capacity(rows: Iterable[tuple[float, float, str]], cfg: FoodModelConfig) -> float:
    """Province food capacity (the engine's ``max_food_value``) of a pool from its locations' (development, pop k,
    rank)."""
    c = cfg.capacity
    rank_bonus = c.get("rank", {}) or {}
    total = 0.0
    for dev, pop_k, rank in rows:
        total += (
            float(c.get("per_development", 0.0)) * float(dev or 0.0)
            + float(c.get("per_population_k", 0.0)) * float(pop_k or 0.0)
            + float(c.get("per_location", 0.0))
            + float(rank_bonus.get(str(rank), 0.0))
        )
    return total


def cookery_victuals(cfg: FoodModelConfig) -> float:
    """Victuals one staffed cookery level makes per month: its container and drink slots plus the dish slot on the
    levels that run Preserve."""
    return float(cfg.cookery_victuals_other) + (1.0 - float(cfg.cookery_serve_share)) * float(cfg.preserve_victuals_per_level)


def structural_ratio(supply: float, demand: float) -> float:
    """R = what the pool feeds itself with (subsistence + building food, no trade) / what it eats."""
    return supply / demand if demand > 1e-9 else math.inf


# --------------------------------------------------------------------------------------------- fit
def r2(actual, predicted) -> float | None:
    a = np.asarray(actual, dtype=float)
    p = np.asarray(predicted, dtype=float)
    ss = float(((a - a.mean()) ** 2).sum())
    return round(1.0 - float(((a - p) ** 2).sum()) / ss, 4) if ss else None


def fit_yields(
    pool_index: np.ndarray,
    jobless: np.ndarray,
    stack: np.ndarray,
    ranks: list[str],
    climates: list[str],
    overpop: np.ndarray,
    fixed: np.ndarray,
    production: np.ndarray,
    *,
    define: float,
    overpopulation_consumption: float = 0.5,
    min_weight_k: float = 500.0,
    iterations: int = 40,
) -> dict[str, Any]:
    """Fit the rank and climate yield factors so that per pool

        production = sum_loc define x (1 + stack) x f_rank x f_climate x jobless  +  fixed  -  overpop

    (``overpop`` already multiplied by the overpopulation consumption). Arrays are per location except ``production``
    (per pool; ``pool_index`` maps a location to its pool). Classes with fewer than ``min_weight_k`` thousand jobless
    workers keep factor 1. Alternating least squares; the climate factors are normalised to a jobless-weighted mean
    of 1."""
    n = len(production)
    base = define * np.clip(1.0 + stack, 0.0, None) * jobless
    R = sorted(set(ranks))
    C = sorted(set(climates))
    ri = np.array([R.index(r) for r in ranks])
    ci = np.array([C.index(c) for c in climates])
    wc = np.array([jobless[ci == j].sum() for j in range(len(C))])
    wr = np.array([jobless[ri == j].sum() for j in range(len(R))])
    fr = np.ones(len(R))
    fc = np.ones(len(C))
    target = production - fixed + overpop

    def solve(groups, idx, other, weights):
        free = [j for j in range(len(groups)) if weights[j] >= min_weight_k]
        cols = [np.bincount(pool_index, base * other * (idx == j), n) for j in free]
        fixed_part = np.zeros(n)
        for j in range(len(groups)):
            if j not in free:
                fixed_part += np.bincount(pool_index, base * other * (idx == j), n)
        out = np.ones(len(groups))
        if cols:
            sol, *_ = np.linalg.lstsq(np.column_stack(cols), target - fixed_part, rcond=None)
            out[free] = sol
        return out

    for _ in range(iterations):
        fr = solve(R, ri, fc[ci], wr)
        fc = solve(C, ci, fr[ri], wc)
        free = wc >= min_weight_k
        if free.any():
            s = float((fc[free] * wc[free]).sum() / wc[free].sum())
            fc[free] /= s
            fr *= s
    pred = np.bincount(pool_index, base * fr[ri] * fc[ci], n) + fixed - overpop
    plain = np.bincount(pool_index, base, n) + fixed - overpop
    return {
        "yield_rank": {r: round(float(v), 3) for r, v in zip(R, fr)},
        "yield_climate": {c: round(float(v), 3) for c, v in zip(C, fc) if wc[C.index(c)] >= min_weight_k},
        "yield_per_1000_jobless_by_rank": {r: round(define * float(v), 3) for r, v in zip(R, fr)},
        "jobless_k_by_climate": {c: round(float(w)) for c, w in zip(C, wc)},
        "r2_production": r2(production, pred),
        "aggregate_model": round(float(pred.sum())),
        "aggregate_engine": round(float(production.sum())),
        "aggregate_error": round(float(pred.sum() / production.sum() - 1.0), 4) if production.sum() else None,
        "plain_define": {"r2_production": r2(production, plain), "aggregate_model": round(float(plain.sum()))},
        "overpopulation_consumption": overpopulation_consumption,
    }
