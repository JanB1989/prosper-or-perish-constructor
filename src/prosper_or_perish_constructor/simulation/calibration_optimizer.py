"""Constrained calibration algorithms for the population-capacity simulation.

Starting population is used only by acceptance constraints and loss reporting.
It is never exposed to the functions that generate potential, development, or
infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from time import perf_counter
import tomllib
from typing import Any, Mapping, Sequence

import numpy as np
import optuna
import polars as pl
from scipy.optimize import linprog
from scipy.sparse import lil_matrix
from sklearn.tree import DecisionTreeRegressor

from prosper_or_perish_constructor.simulation.capacity_model import (
    BASE_POPULATION_CAPACITY_COLUMN,
    INFRASTRUCTURE_POPULATION_CAPACITY_COLUMN,
    PHYSICAL_POPULATION_CAPACITY_COLUMN,
    ZERO_DEVELOPMENT_CAPACITY_COLUMN,
)
from prosper_or_perish_constructor.simulation.profile import (
    SimulationProfile,
    _prepare_state,
    load_population_simulation_profile,
)
from prosper_or_perish_constructor.simulation.run import Simulation


CONSTRAINT_NAMES = (
    "ordinary_location_fill",
    "supercity_province_fill",
    "global_capacity",
    "location_potential_spread",
    "development_maximum",
    "development_capacity_contribution",
    "global_modifier_minimum",
    "china_lower_nile_ranking",
    "global_100y_growth_minimum",
    "global_100y_growth_maximum",
    "macro_region_100y_growth_minimum",
    "macro_region_100y_growth_maximum",
)


@dataclass(frozen=True)
class SearchParameter:
    kind: str
    low: float | int
    high: float | int
    log: bool = False
    step: float | int | None = None


@dataclass(frozen=True)
class CalibrationConfig:
    algorithm: str
    study_name: str
    storage_path: Path
    report_path: Path
    best_parameters_path: Path
    seed: int
    startup_trials: int
    solve_infrastructure_effects: bool
    search_space: Mapping[str, SearchParameter]
    regime_min_samples_leaf: int
    regime_max_leaf_nodes: int | None
    global_capacity_safety_margin_people: float
    minimum_infrastructure_share: float
    regime_features: tuple[str, ...]
    regime_model_path: Path
    regime_potential_path: Path


@dataclass(frozen=True)
class CalibrationResult:
    trials_completed: int
    feasible_trials: int
    best_trial_number: int
    best_loss: float
    passed: bool
    report_path: Path
    best_parameters_path: Path
    elapsed_seconds: float


def load_calibration_config(profile_path: Path, *, repo: Path) -> CalibrationConfig:
    raw = tomllib.loads(profile_path.read_text(encoding="utf-8-sig"))
    section = raw.get("optimization")
    if not isinstance(section, dict):
        raise ValueError("population profile requires an [optimization] table")
    raw_space = section.get("search_space")
    if not isinstance(raw_space, dict) or not raw_space:
        raise ValueError("optimization.search_space must not be empty")
    search_space: dict[str, SearchParameter] = {}
    for key, raw_parameter in raw_space.items():
        if not isinstance(raw_parameter, dict):
            raise ValueError(f"optimization parameter {key!r} must be a table")
        kind = str(raw_parameter.get("type") or "")
        if kind not in {"float", "int"}:
            raise ValueError(f"optimization parameter {key!r} has invalid type {kind!r}")
        low = raw_parameter.get("low")
        high = raw_parameter.get("high")
        if not isinstance(low, int | float) or not isinstance(high, int | float):
            raise ValueError(f"optimization parameter {key!r} requires numeric bounds")
        if float(high) <= float(low):
            raise ValueError(f"optimization parameter {key!r} has an empty range")
        search_space[str(key)] = SearchParameter(
            kind=kind,
            low=int(low) if kind == "int" else float(low),
            high=int(high) if kind == "int" else float(high),
            log=bool(raw_parameter.get("log", False)),
            step=raw_parameter.get("step"),
        )
    return CalibrationConfig(
        algorithm=str(section.get("algorithm") or "tpe_lp"),
        study_name=str(section.get("study_name") or "population_capacity_tpe"),
        storage_path=_resolve(repo, section.get("storage")),
        report_path=_resolve(repo, section.get("report")),
        best_parameters_path=_resolve(repo, section.get("best_parameters")),
        seed=int(section.get("seed", 1337)),
        startup_trials=int(section.get("startup_trials", 64)),
        solve_infrastructure_effects=bool(
            section.get("solve_infrastructure_effects", True)
        ),
        search_space=search_space,
        regime_min_samples_leaf=int(section.get("regime_min_samples_leaf", 20)),
        regime_max_leaf_nodes=(
            int(section["regime_max_leaf_nodes"])
            if section.get("regime_max_leaf_nodes") is not None
            else None
        ),
        global_capacity_safety_margin_people=float(
            section.get("global_capacity_safety_margin_people", 0.0)
        ),
        minimum_infrastructure_share=float(
            section.get("minimum_infrastructure_share", 0.35)
        ),
        regime_features=tuple(str(value) for value in section.get("regime_features") or ()),
        regime_model_path=_resolve(repo, section.get("regime_model")),
        regime_potential_path=_resolve(repo, section.get("regime_potential")),
    )


def _resolve(repo: Path, raw: object) -> Path:
    if not isinstance(raw, str) or not raw:
        raise ValueError("optimization output paths must be non-empty strings")
    path = Path(raw)
    return path if path.is_absolute() else repo / path


def _suggest(trial: optuna.Trial, search_space: Mapping[str, SearchParameter]) -> dict[str, float | int]:
    values: dict[str, float | int] = {}
    for name, parameter in search_space.items():
        if parameter.kind == "int":
            values[name] = trial.suggest_int(
                name,
                int(parameter.low),
                int(parameter.high),
                step=int(parameter.step or 1),
                log=parameter.log,
            )
        else:
            values[name] = trial.suggest_float(
                name,
                float(parameter.low),
                float(parameter.high),
                step=float(parameter.step) if parameter.step is not None else None,
                log=parameter.log,
            )
    return values


def _override_strings(parameters: Mapping[str, float | int]) -> tuple[str, ...]:
    return tuple(f"{key}={json.dumps(value)}" for key, value in parameters.items())


def solve_infrastructure_effects(
    state: pl.DataFrame,
    profile: SimulationProfile,
    search_space: Mapping[str, SearchParameter],
) -> tuple[pl.DataFrame, dict[str, float], dict[str, float]]:
    """Solve flat building effects exactly for fixed source/placement choices.

    The two relaxation variables are maximum proportional location shortfall
    and proportional global-capacity overflow. A zero value for both proves the
    two hard constraints are jointly feasible for the selected placement.
    """

    buildings = tuple(profile.infrastructure_capacity_per_level)
    level_columns = [f"infrastructure_{building}_levels" for building in buildings]
    missing = sorted(set(level_columns) - set(state.columns))
    if missing:
        raise ValueError(f"infrastructure level columns missing from state: {missing}")
    levels = np.column_stack(
        [state[column].fill_null(0.0).to_numpy() for column in level_columns]
    )
    base = state[BASE_POPULATION_CAPACITY_COLUMN].fill_null(0.0).to_numpy()
    development = state["development"].fill_null(0.0).to_numpy()
    relative = np.maximum(
        1.0
        + development * profile.capacity_formula.development_relative
        + profile.capacity_formula.global_relative,
        1e-12,
    )
    population = state["total_population"].fill_null(0.0).to_numpy()
    fill_limit = profile.acceptance["ordinary_maximum_fill"]
    required = population / fill_limit
    m = len(buildings)
    # Variables: m effects, maximum relative location shortfall, normalized
    # global overflow. The latter two are minimized before a tiny capacity term.
    location_matrix = np.zeros((state.height, m + 2), dtype=np.float64)
    location_matrix[:, :m] = -relative[:, None] * levels
    location_matrix[:, m] = -required
    location_rhs = relative * base - required
    global_limit = (
        profile.acceptance["global_capacity_maximum_people"]
        / profile.people_per_game_unit
    )
    global_coefficients = np.sum(relative[:, None] * levels, axis=0)
    global_base = float(np.sum(relative * base))
    global_row = np.zeros((1, m + 2), dtype=np.float64)
    global_row[0, :m] = global_coefficients
    global_row[0, m + 1] = -global_limit
    bounds: list[tuple[float, float]] = []
    for building in buildings:
        key = f"infrastructure.capacity_per_level.{building}"
        parameter = search_space[key]
        bounds.append((float(parameter.low), float(parameter.high)))
    # A trial may generate arbitrarily excessive base capacity. Keep the
    # overflow slack unbounded so such a candidate receives a large loss
    # instead of aborting the persistent optimization study.
    bounds.extend(((0.0, 1.0), (0.0, None)))
    primary_objective = np.zeros(m + 2, dtype=np.float64)
    primary_objective[m] = 1.0
    primary_objective[m + 1] = 1.0
    constraint_matrix = np.vstack((location_matrix, global_row))
    constraint_rhs = np.concatenate((location_rhs, [global_limit - global_base]))
    result = linprog(
        primary_objective,
        A_ub=constraint_matrix,
        b_ub=constraint_rhs,
        bounds=bounds,
        method="highs",
    )
    if not result.success or result.x is None:
        raise RuntimeError(f"infrastructure inner solve failed: {result.message}")
    # The primary minimax objective can be controlled by a source-poor,
    # unowned location that cannot receive buildings. Among equally optimal
    # primary solutions, spend the remaining capacity budget on the globally
    # required breadbasket provinces instead of defaulting every effect to its
    # minimum. Effects remain global; only the choice among primary optima is
    # guided by the ranking acceptance target.
    expected_mask = np.isin(
        state["province"].fill_null("").to_numpy(),
        np.asarray(profile.expected_high_capacity_provinces, dtype=object),
    )
    expected_coefficients = np.sum(
        relative[expected_mask, None] * levels[expected_mask], axis=0
    )
    secondary_objective = np.zeros(m + 2, dtype=np.float64)
    secondary_objective[:m] = (
        global_coefficients / max(global_limit, 1e-12) * 1e-9
        - expected_coefficients / max(float(np.sum(expected_coefficients)), 1e-12)
    )
    primary_row = np.zeros((1, m + 2), dtype=np.float64)
    primary_row[0, m:] = 1.0
    secondary = linprog(
        secondary_objective,
        A_ub=np.vstack((constraint_matrix, primary_row)),
        b_ub=np.concatenate((constraint_rhs, [float(result.fun)])),
        bounds=bounds,
        method="highs",
    )
    solution = secondary if secondary.success and secondary.x is not None else result
    effects = {
        f"infrastructure.capacity_per_level.{building}": float(solution.x[index])
        for index, building in enumerate(buildings)
    }
    infrastructure = levels @ solution.x[:m]
    capacity = profile.capacity_formula.evaluate(
        base_capacity=base,
        development=development,
        infrastructure_capacity=infrastructure,
    )
    updated = state.with_columns(
        pl.Series(INFRASTRUCTURE_POPULATION_CAPACITY_COLUMN, infrastructure),
        pl.Series("local_population_capacity", capacity),
    )
    return updated, effects, {
        "inner_maximum_relative_shortfall": float(solution.x[m]),
        "inner_global_overflow": float(solution.x[m + 1]),
        "inner_objective": float(solution.x[m] + solution.x[m + 1]),
    }


def evaluate_static_candidate(
    state: pl.DataFrame,
    profile: SimulationProfile,
) -> tuple[float, dict[str, float], list[float]]:
    """Return a smooth loss, diagnostics, and normalized hard violations."""

    population = state["total_population"].to_numpy()
    capacity = np.maximum(state["local_population_capacity"].to_numpy(), 1e-12)
    provinces = state["province"].fill_null("").to_numpy()
    ordinary = (population > 0.0) & ~np.isin(
        provinces,
        np.asarray(sorted(profile.supercity_exceptions), dtype=object),
    )
    ordinary_fill = population[ordinary] / capacity[ordinary]
    fill_limit = profile.acceptance["ordinary_maximum_fill"]
    fill_excess = np.maximum(ordinary_fill / fill_limit - 1.0, 0.0)
    maximum_fill = float(np.max(ordinary_fill)) if ordinary_fill.size else 0.0
    shortfall = np.maximum(population[ordinary] / fill_limit - capacity[ordinary], 0.0)
    shortfall_share = float(np.sum(shortfall) / max(float(np.sum(population[ordinary])), 1e-12))
    overfilled_fraction = float(np.mean(fill_excess > 0.0)) if fill_excess.size else 0.0

    province_rows = state.group_by("province").agg(
        pl.col("total_population").sum().alias("population"),
        pl.col("local_population_capacity").sum().alias("capacity"),
    )
    supercity_fill = 0.0
    if profile.supercity_exceptions:
        exceptions = province_rows.filter(
            pl.col("province").is_in(sorted(profile.supercity_exceptions))
        )
        if exceptions.height:
            supercity_fill = float(
                exceptions.select(
                    (pl.col("population") / pl.col("capacity").clip(lower_bound=1e-12)).max()
                ).item()
            )

    global_capacity = float(np.sum(capacity)) * profile.people_per_game_unit
    potential = state[ZERO_DEVELOPMENT_CAPACITY_COLUMN].to_numpy()
    positive_potential = potential[potential > 0.0]
    potential_spread = (
        float(np.max(positive_potential) / np.min(positive_potential))
        if positive_potential.size
        else math.inf
    )
    development_maximum = float(state["development"].max())
    development_contribution = (
        development_maximum * profile.capacity_formula.development_relative
    )

    ranked = province_rows.sort("capacity", descending=True).with_row_index(
        "rank", offset=1
    )
    expected = ranked.filter(
        pl.col("province").is_in(profile.expected_high_capacity_provinces)
    )
    missing_expected = len(profile.expected_high_capacity_provinces) - expected.height
    worst_expected_rank = (
        int(expected["rank"].max()) if expected.height else ranked.height + 1
    )
    ranking_limit = int(profile.acceptance["ranking_top_count"])
    ranking_violation = max(worst_expected_rank / ranking_limit - 1.0, 0.0) + missing_expected

    constraints = [
        maximum_fill / fill_limit - 1.0,
        supercity_fill / profile.acceptance["supercity_province_maximum_fill"] - 1.0,
        global_capacity / profile.acceptance["global_capacity_maximum_people"] - 1.0,
        potential_spread / profile.acceptance["location_potential_maximum_spread"] - 1.0,
        development_maximum / profile.acceptance["development_maximum"] - 1.0,
        development_contribution
        / profile.acceptance["development_maximum_capacity_contribution"]
        - 1.0,
        profile.acceptance["global_modifier_minimum"]
        - profile.capacity_formula.global_relative,
        ranking_violation,
    ]
    constraints = [0.0 if abs(value) < 1e-10 else value for value in constraints]
    positive_constraints = np.maximum(np.asarray(constraints), 0.0)
    loss = (
        8.0 * math.log1p(max(float(constraints[0]), 0.0))
        + 24.0 * shortfall_share
        + 4.0 * math.sqrt(float(np.mean(np.square(np.log1p(fill_excess)))))
        + 3.0 * overfilled_fraction
        + 20.0 * float(np.sum(np.square(positive_constraints[1:])))
        + 0.05
        * global_capacity
        / profile.acceptance["global_capacity_maximum_people"]
    )
    metrics = {
        "maximum_ordinary_fill": maximum_fill,
        "overfilled_locations": float(np.sum(fill_excess > 0.0)),
        "overfilled_fraction": overfilled_fraction,
        "capacity_shortfall_share": shortfall_share,
        "global_capacity_people": global_capacity,
        "location_potential_spread": potential_spread,
        "development_maximum": development_maximum,
        "development_capacity_contribution": development_contribution,
        "supercity_province_maximum_fill": supercity_fill,
        "worst_expected_province_rank": float(worst_expected_rank),
    }
    return loss, metrics, constraints


def evaluate_growth_candidate(
    state: pl.DataFrame,
    context: Any,
    profile: SimulationProfile,
) -> tuple[float, dict[str, float], list[float]]:
    start_total = float(state["total_population"].sum())
    start_regions = state.group_by("macro_region").agg(
        pl.col("total_population").sum().alias("start")
    )
    simulation = Simulation(state, context)
    simulation.run(months=1200, progress=False)
    end = simulation.state
    end_total = float(end["total_population"].sum())
    global_growth = end_total / max(start_total, 1e-12)
    real_regions = set(profile.tracked_provinces)
    regional = (
        end.group_by("macro_region")
        .agg(pl.col("total_population").sum().alias("end"))
        .join(start_regions, on="macro_region")
        .filter(pl.col("macro_region").is_in(sorted(real_regions)))
        .with_columns((pl.col("end") / pl.col("start").clip(lower_bound=1e-12)).alias("growth"))
    )
    minimum_region_growth = float(regional["growth"].min())
    maximum_region_growth = float(regional["growth"].max())
    lower = profile.acceptance["global_100y_growth_minimum"]
    upper = profile.acceptance["global_100y_growth_maximum"]
    region_lower = profile.acceptance["macro_region_100y_growth_minimum"]
    region_upper = profile.acceptance["macro_region_100y_growth_maximum"]
    constraints = [
        lower - global_growth,
        global_growth - upper,
        region_lower - minimum_region_growth,
        maximum_region_growth - region_upper,
    ]
    loss = (
        30.0 * (global_growth - 1.0) ** 2
        + 12.0 * max(region_lower - minimum_region_growth, 0.0) ** 2
        + 12.0 * max(maximum_region_growth - region_upper, 0.0) ** 2
    )
    return loss, {
        "global_100y_growth": global_growth,
        "minimum_macro_region_100y_growth": minimum_region_growth,
        "maximum_macro_region_100y_growth": maximum_region_growth,
    }, constraints


def _constraints_from_trial(trial: optuna.trial.FrozenTrial) -> Sequence[float]:
    raw = trial.user_attrs.get("constraints")
    if not isinstance(raw, list) or len(raw) != len(CONSTRAINT_NAMES):
        return [1e6] * len(CONSTRAINT_NAMES)
    return [float(value) for value in raw]


def physical_regime_training_data(
    state: pl.DataFrame,
    feature_names: Sequence[str],
) -> tuple[np.ndarray, np.ndarray]:
    """Build ML inputs without exposing the starting population column."""

    features = np.nan_to_num(
        state.select(feature_names).fill_null(0.0).to_numpy(),
        nan=0.0,
        posinf=0.0,
        neginf=0.0,
    )
    target = state[PHYSICAL_POPULATION_CAPACITY_COLUMN].fill_null(0.0).to_numpy()
    return (
        np.log1p(np.maximum(features, 0.0)),
        np.log1p(np.maximum(target, 0.0)),
    )


def _run_regime_tree_lp_calibration(
    *,
    repo: Path,
    project: Path,
    profile_path: Path,
    config: CalibrationConfig,
    static_only: bool,
) -> CalibrationResult:
    """Fit population-independent physical regimes, then enforce hard bounds.

    Tree topology is supervised only by the independent physical-capacity
    estimate. Starting population is neither a feature nor the tree target; it
    appears only in the linear program's one-sided 115% feasibility inequality.
    """

    started = perf_counter()
    profile = load_population_simulation_profile(profile_path, repo=repo)
    state, context, _preparation = _prepare_state(
        repo,
        project,
        profile,
        refresh_cache=False,
    )
    missing = sorted(set(config.regime_features) - set(state.columns))
    if missing:
        raise ValueError(f"regime-tree features missing from prepared state: {missing}")
    if config.regime_min_samples_leaf < 2:
        raise ValueError("regime_min_samples_leaf must be at least 2")
    if not 0.0 <= config.minimum_infrastructure_share < 1.0:
        raise ValueError("minimum_infrastructure_share must be in [0, 1)")

    features, physical_target = physical_regime_training_data(
        state, config.regime_features
    )
    population = state["total_population"].fill_null(0.0).to_numpy()
    development = state["development"].fill_null(0.0).to_numpy()
    relative = np.maximum(
        1.0
        + development * profile.capacity_formula.development_relative
        + profile.capacity_formula.global_relative,
        1e-12,
    )
    fill_limit = profile.acceptance["ordinary_maximum_fill"]
    tree = DecisionTreeRegressor(
        min_samples_leaf=config.regime_min_samples_leaf,
        max_leaf_nodes=config.regime_max_leaf_nodes,
        random_state=config.seed,
    ).fit(features, physical_target)
    raw_leaf = tree.apply(features)
    leaf_ids, leaf_index = np.unique(raw_leaf, return_inverse=True)
    leaf_count = len(leaf_ids)
    leaf_sizes = np.bincount(leaf_index, minlength=leaf_count)
    physical_prediction = tree.predict(features)
    physical_log_rmse = float(
        np.sqrt(np.mean(np.square(physical_prediction - physical_target)))
    )
    physical_total_variance = float(
        np.sum(np.square(physical_target - np.mean(physical_target)))
    )
    physical_r2 = 1.0 - float(
        np.sum(np.square(physical_prediction - physical_target))
    ) / max(physical_total_variance, 1e-12)

    buildings = tuple(profile.infrastructure_capacity_per_level)
    levels = np.column_stack(
        [
            state[f"infrastructure_{building}_levels"].fill_null(0.0).to_numpy()
            for building in buildings
        ]
    )
    building_count = len(buildings)
    spread_index = leaf_count + building_count
    variable_count = spread_index + 1
    # Rows: every location boundary, lower/upper spread bounds per leaf, and
    # the minimum global infrastructure-attribution share.
    matrix = lil_matrix(
        (state.height + 2 * leaf_count + 1, variable_count),
        dtype=np.float64,
    )
    rhs = np.zeros(state.height + 2 * leaf_count + 1, dtype=np.float64)
    for row in range(state.height):
        matrix[row, leaf_index[row]] = -relative[row]
        matrix[row, leaf_count : leaf_count + building_count] = (
            -relative[row] * levels[row]
        )
        rhs[row] = -population[row] / fill_limit
    spread = profile.acceptance["location_potential_maximum_spread"]
    for leaf in range(leaf_count):
        lower_row = state.height + leaf
        upper_row = state.height + leaf_count + leaf
        matrix[lower_row, leaf] = -1.0
        matrix[lower_row, spread_index] = 1.0
        matrix[upper_row, leaf] = 1.0
        matrix[upper_row, spread_index] = -spread
    potential_coefficients = np.bincount(
        leaf_index,
        weights=relative,
        minlength=leaf_count,
    )
    infrastructure_coefficients = np.sum(relative[:, None] * levels, axis=0)
    share_row = matrix.shape[0] - 1
    share = config.minimum_infrastructure_share
    matrix[share_row, :leaf_count] = share * potential_coefficients
    matrix[share_row, leaf_count : leaf_count + building_count] = (
        -(1.0 - share) * infrastructure_coefficients
    )

    objective = np.zeros(variable_count, dtype=np.float64)
    objective[:leaf_count] = potential_coefficients
    objective[leaf_count : leaf_count + building_count] = infrastructure_coefficients
    bounds: list[tuple[float, float | None]] = [(0.0, None)] * leaf_count
    for building in buildings:
        parameter = config.search_space[
            f"infrastructure.capacity_per_level.{building}"
        ]
        bounds.append((float(parameter.low), float(parameter.high)))
    bounds.append((0.0, None))
    solution = linprog(
        objective,
        A_ub=matrix.tocsr(),
        b_ub=rhs,
        bounds=bounds,
        method="highs",
    )
    if not solution.success or solution.x is None:
        raise RuntimeError(f"regime-tree capacity solve failed: {solution.message}")

    potential = solution.x[leaf_index]
    # Six decimals are the canonical TOML/blueprint/compiler precision. Evaluate
    # the deployable values, not higher-precision LP values that cannot be
    # represented by the game data.
    effects = np.round(
        solution.x[leaf_count : leaf_count + building_count], decimals=6
    )
    infrastructure = levels @ effects
    # Match the integral compiler contract before evaluating hard gates.
    deployed_potential = np.ceil(potential - 1e-12)
    capacity = profile.capacity_formula.evaluate(
        base_capacity=deployed_potential,
        development=development,
        infrastructure_capacity=infrastructure,
    )
    state = state.with_columns(
        pl.Series(ZERO_DEVELOPMENT_CAPACITY_COLUMN, potential),
        pl.Series(BASE_POPULATION_CAPACITY_COLUMN, deployed_potential),
        pl.Series(INFRASTRUCTURE_POPULATION_CAPACITY_COLUMN, infrastructure),
        pl.Series("local_population_capacity", capacity),
    )
    static_loss, metrics, static_constraints = evaluate_static_candidate(state, profile)
    infrastructure_total = float(np.sum(relative * infrastructure))
    metrics.update(
        {
            "regime_leaves": float(leaf_count),
            "regime_tree_depth": float(tree.get_depth()),
            "regime_minimum_size": float(np.min(leaf_sizes)),
            "regime_median_size": float(np.median(leaf_sizes)),
            "regime_maximum_size": float(np.max(leaf_sizes)),
            "physical_prior_log_rmse": physical_log_rmse,
            "physical_prior_r2": physical_r2,
            "global_capacity_safety_headroom_people": (
                profile.acceptance["global_capacity_maximum_people"]
                - config.global_capacity_safety_margin_people
                - metrics["global_capacity_people"]
            ),
            "infrastructure_capacity_share": infrastructure_total
            / max(float(np.sum(capacity)), 1e-12),
        }
    )
    constraints = [
        *static_constraints,
        *((0.0, 0.0, 0.0, 0.0) if static_only else (1.0, 1.0, 1.0, 1.0)),
    ]
    growth_loss = 0.0
    simulated = False
    if not static_only and all(value <= 0.0 for value in static_constraints):
        growth_loss, growth_metrics, growth_constraints = evaluate_growth_candidate(
            state, context, profile
        )
        metrics.update(growth_metrics)
        constraints[-4:] = growth_constraints
        simulated = True
    passed = all(value <= 0.0 for value in constraints)

    config.regime_potential_path.parent.mkdir(parents=True, exist_ok=True)
    state.select(
        "location_tag",
        pl.col(ZERO_DEVELOPMENT_CAPACITY_COLUMN).alias("location_potential"),
    ).write_parquet(config.regime_potential_path)
    importances = sorted(
        zip(config.regime_features, tree.feature_importances_, strict=True),
        key=lambda item: item[1],
        reverse=True,
    )
    model_payload = {
        "schema_version": 1,
        "algorithm": "upper-envelope regime tree + constrained linear program",
        "tree_supervision": PHYSICAL_POPULATION_CAPACITY_COLUMN,
        "starting_population_role": "one_sided_lp_constraint_only",
        "seed": config.seed,
        "min_samples_leaf": config.regime_min_samples_leaf,
        "max_leaf_nodes": config.regime_max_leaf_nodes,
        "leaf_count": leaf_count,
        "depth": tree.get_depth(),
        "features": list(config.regime_features),
        "feature_importance": {name: float(value) for name, value in importances},
        "infrastructure_effects": dict(zip(buildings, map(float, effects), strict=True)),
        "minimum_infrastructure_share": share,
        "global_capacity_safety_margin_people": (
            config.global_capacity_safety_margin_people
        ),
        "physical_prior_log_rmse": physical_log_rmse,
        "physical_prior_r2": physical_r2,
    }
    config.regime_model_path.parent.mkdir(parents=True, exist_ok=True)
    config.regime_model_path.write_text(
        json.dumps(model_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    parameters = {
        "optimization.regime_min_samples_leaf": config.regime_min_samples_leaf,
        "optimization.regime_max_leaf_nodes": config.regime_max_leaf_nodes,
        "optimization.global_capacity_safety_margin_people": (
            config.global_capacity_safety_margin_people
        ),
        "optimization.minimum_infrastructure_share": share,
        **{
            f"infrastructure.capacity_per_level.{building}": float(effect)
            for building, effect in zip(buildings, effects, strict=True)
        },
    }
    best_payload = {
        "schema_version": 1,
        "algorithm": config.algorithm,
        "passed": passed,
        "loss": float(static_loss + growth_loss),
        "parameters": parameters,
        "metrics": metrics,
        "constraints": dict(zip(CONSTRAINT_NAMES, constraints, strict=True)),
        "simulated_100y": simulated,
    }
    config.best_parameters_path.parent.mkdir(parents=True, exist_ok=True)
    config.best_parameters_path.write_text(
        json.dumps(best_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Population-Capacity Calibration",
        "",
        f"**Overall: {'PASS' if passed else 'FAIL'}**",
        "",
        "- Algorithm: physical-prior regime tree + constrained linear program",
        "- Tree supervision: independent physical capacity (population is not the target)",
        f"- Shared regimes: {leaf_count:,}",
        f"- Minimum samples per regime: {config.regime_min_samples_leaf}",
        f"- Maximum leaf nodes: {config.regime_max_leaf_nodes or 'unbounded'}",
        (
            "- Requested global-capacity safety margin: "
            f"{config.global_capacity_safety_margin_people:,.0f} people"
        ),
        f"- Tree depth: {tree.get_depth()}",
        f"- 100-year simulation evaluated: {simulated}",
        "",
        "## Hard constraints",
        "",
        "| Constraint | Normalized violation | Result |",
        "|---|---:|:---:|",
    ]
    for index, (name, value) in enumerate(
        zip(CONSTRAINT_NAMES, constraints, strict=True)
    ):
        if index >= len(static_constraints) and not simulated:
            lines.append(f"| {name} | — | N/A |")
        else:
            lines.append(
                f"| {name} | {value:+.6f} | {'PASS' if value <= 0 else 'FAIL'} |"
            )
    lines.extend(["", "## Metrics", "", "| Metric | Value |", "|---|---:|"])
    for name, value in sorted(metrics.items()):
        lines.append(f"| {name} | {value:,.6f} |")
    lines.extend(
        [
            "",
            "## Selection objective",
            "",
            "The optimizer uses a lexicographic loss; a softer average cannot hide a failed location:",
            "",
            "1. Reject any model that violates an all-map hard constraint.",
            "2. Require the configured global-capacity safety margin below 1.2 billion.",
            "3. Prefer the largest minimum regime size, then the fewest regimes.",
            "4. For fixed regimes, minimize total global capacity with the exact LP.",
            "5. Use the independent physical-prior error as a diagnostic, never EU5 population as a tree target.",
        ]
    )
    lines.extend(
        [
            "",
            "## Infrastructure effects",
            "",
            "| Building | Capacity per level |",
            "|---|---:|",
        ]
    )
    for building, effect in zip(buildings, effects, strict=True):
        lines.append(f"| {building} | {effect:.6f} |")
    lines.extend(
        [
            "",
            "## Most influential features",
            "",
            "| Feature | Importance |",
            "|---|---:|",
        ]
    )
    for name, value in importances[:15]:
        lines.append(f"| {name} | {value:.6f} |")
    config.report_path.parent.mkdir(parents=True, exist_ok=True)
    config.report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    elapsed = perf_counter() - started
    return CalibrationResult(
        trials_completed=1,
        feasible_trials=1 if passed else 0,
        best_trial_number=0,
        best_loss=float(static_loss + growth_loss),
        passed=passed,
        report_path=config.report_path,
        best_parameters_path=config.best_parameters_path,
        elapsed_seconds=elapsed,
    )


def run_population_capacity_calibration(
    *,
    repo: Path,
    project: Path,
    profile_path: Path,
    trials: int,
    timeout_seconds: float | None = None,
    seed: int | None = None,
    static_only: bool = False,
) -> CalibrationResult:
    if trials <= 0:
        raise ValueError("--trials must be positive")
    started = perf_counter()
    config = load_calibration_config(profile_path, repo=repo)
    if config.algorithm == "regime_tree_lp":
        return _run_regime_tree_lp_calibration(
            repo=repo,
            project=project,
            profile_path=profile_path,
            config=config,
            static_only=static_only,
        )
    if config.algorithm != "tpe_lp":
        raise ValueError(f"unsupported population calibration algorithm: {config.algorithm}")
    config.storage_path.parent.mkdir(parents=True, exist_ok=True)
    sampler = optuna.samplers.TPESampler(
        seed=config.seed if seed is None else seed,
        n_startup_trials=config.startup_trials,
        multivariate=True,
        group=True,
        constraints_func=_constraints_from_trial,
    )
    study = optuna.create_study(
        study_name=config.study_name,
        storage=f"sqlite:///{config.storage_path}",
        direction="minimize",
        sampler=sampler,
        load_if_exists=True,
    )
    if not any(
        trial.state == optuna.trial.TrialState.COMPLETE for trial in study.trials
    ):
        baseline = load_population_simulation_profile(profile_path, repo=repo)
        current: dict[str, float | int] = {}
        raw = tomllib.loads(profile_path.read_text(encoding="utf-8-sig"))
        for key in config.search_space:
            if config.solve_infrastructure_effects and key.startswith(
                "infrastructure.capacity_per_level."
            ):
                continue
            value: Any = raw
            for part in key.split("."):
                value = value[part]
            current[key] = value
        study.enqueue_trial(current)

    def objective(trial: optuna.Trial) -> float:
        sampled_space = {
            key: value
            for key, value in config.search_space.items()
            if not (
                config.solve_infrastructure_effects
                and key.startswith("infrastructure.capacity_per_level.")
            )
        }
        parameters = _suggest(trial, sampled_space)
        profile = load_population_simulation_profile(
            profile_path,
            repo=repo,
            overrides=_override_strings(parameters),
        )
        state, context, _preparation = _prepare_state(
            repo,
            project,
            profile,
            refresh_cache=False,
        )
        derived_parameters: dict[str, float] = {}
        inner_metrics: dict[str, float] = {}
        if config.solve_infrastructure_effects:
            state, derived_parameters, inner_metrics = solve_infrastructure_effects(
                state,
                profile,
                config.search_space,
            )
        static_loss, metrics, static_constraints = evaluate_static_candidate(
            state, profile
        )
        metrics.update(inner_metrics)
        # A static-only calibration must be able to prove static feasibility.
        # Growth placeholders are positive only when growth was requested but
        # skipped because a static hard gate failed.
        all_constraints = [
            *static_constraints,
            *((0.0, 0.0, 0.0, 0.0) if static_only else (1.0, 1.0, 1.0, 1.0)),
        ]
        simulated = False
        growth_loss = 0.0
        if not static_only and all(value <= 0.0 for value in static_constraints):
            growth_loss, growth_metrics, growth_constraints = evaluate_growth_candidate(
                state, context, profile
            )
            metrics.update(growth_metrics)
            all_constraints[-4:] = growth_constraints
            simulated = True
        trial.set_user_attr("constraints", [float(value) for value in all_constraints])
        trial.set_user_attr("metrics", {key: float(value) for key, value in metrics.items()})
        trial.set_user_attr("derived_parameters", derived_parameters)
        trial.set_user_attr("simulated_100y", simulated)
        return float(static_loss + growth_loss)

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study.optimize(
        objective,
        n_trials=trials,
        timeout=timeout_seconds,
        gc_after_trial=True,
        show_progress_bar=True,
    )
    complete = [
        trial
        for trial in study.trials
        if trial.state == optuna.trial.TrialState.COMPLETE and trial.value is not None
    ]
    if not complete:
        raise RuntimeError("calibration produced no completed trials")
    feasible = [
        trial
        for trial in complete
        if all(value <= 0.0 for value in _constraints_from_trial(trial))
    ]
    best = min(
        feasible or complete,
        key=lambda trial: (
            sum(max(value, 0.0) for value in _constraints_from_trial(trial)),
            float(trial.value or math.inf),
        ),
    )
    passed = bool(feasible)
    _write_outputs(config, study, best, passed)
    return CalibrationResult(
        trials_completed=len(complete),
        feasible_trials=len(feasible),
        best_trial_number=best.number,
        best_loss=float(best.value),
        passed=passed,
        report_path=config.report_path,
        best_parameters_path=config.best_parameters_path,
        elapsed_seconds=perf_counter() - started,
    )


def _write_outputs(
    config: CalibrationConfig,
    study: optuna.Study,
    best: optuna.trial.FrozenTrial,
    passed: bool,
) -> None:
    constraints = _constraints_from_trial(best)
    payload = {
        "schema_version": 1,
        "study_name": study.study_name,
        "trial_number": best.number,
        "passed": passed,
        "loss": best.value,
        "parameters": {
            **best.params,
            **(best.user_attrs.get("derived_parameters") or {}),
        },
        "metrics": best.user_attrs.get("metrics", {}),
        "constraints": dict(zip(CONSTRAINT_NAMES, constraints, strict=True)),
        "simulated_100y": bool(best.user_attrs.get("simulated_100y", False)),
    }
    config.best_parameters_path.parent.mkdir(parents=True, exist_ok=True)
    config.best_parameters_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    complete = [
        trial
        for trial in study.trials
        if trial.state == optuna.trial.TrialState.COMPLETE and trial.value is not None
    ]
    ranked = sorted(
        complete,
        key=lambda trial: (
            sum(max(value, 0.0) for value in _constraints_from_trial(trial)),
            float(trial.value or math.inf),
        ),
    )[:10]
    lines = [
        "# Population-Capacity Calibration",
        "",
        f"**Overall: {'PASS' if passed else 'FAIL'}**",
        "",
        f"- Algorithm: constrained multivariate Tree-structured Parzen Estimator (TPE)",
        f"- Study: `{study.study_name}`",
        f"- Completed trials: {len(complete):,}",
        f"- Fully feasible trials: {sum(all(v <= 0 for v in _constraints_from_trial(t)) for t in complete):,}",
        f"- Selected trial: {best.number}",
        f"- Selected loss: {float(best.value):.6f}",
        f"- 100-year simulation evaluated: {bool(best.user_attrs.get('simulated_100y', False))}",
        "",
        "## Hard constraints",
        "",
        "| Constraint | Normalized violation | Result |",
        "|---|---:|:---:|",
    ]
    simulated = bool(best.user_attrs.get("simulated_100y", False))
    for index, (name, value) in enumerate(
        zip(CONSTRAINT_NAMES, constraints, strict=True)
    ):
        if index >= 8 and not simulated:
            lines.append(f"| {name} | — | N/A |")
        else:
            lines.append(
                f"| {name} | {value:+.6f} | {'PASS' if value <= 0 else 'FAIL'} |"
            )
    lines.extend(
        [
            "",
            "## Selected metrics",
            "",
            "| Metric | Value |",
            "|---|---:|",
        ]
    )
    for key, value in sorted((best.user_attrs.get("metrics") or {}).items()):
        lines.append(f"| {key} | {float(value):,.6f} |")
    lines.extend(
        [
            "",
            "## Selected parameters",
            "",
            "```toml",
            *[
                f"{key} = {json.dumps(value)}"
                for key, value in sorted(
                    {
                        **best.params,
                        **(best.user_attrs.get("derived_parameters") or {}),
                    }.items()
                )
            ],
            "```",
            "",
            "## Ten least-violating trials",
            "",
            "| Trial | Positive constraint sum | Loss | 100y |",
            "|---:|---:|---:|:---:|",
        ]
    )
    for trial in ranked:
        violation = sum(max(value, 0.0) for value in _constraints_from_trial(trial))
        lines.append(
            f"| {trial.number} | {violation:.6f} | {float(trial.value):.6f} | "
            f"{'yes' if trial.user_attrs.get('simulated_100y') else 'no'} |"
        )
    config.report_path.parent.mkdir(parents=True, exist_ok=True)
    config.report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
