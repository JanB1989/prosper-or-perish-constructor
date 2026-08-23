"""One-report validation of algebraic province equilibria against the simulator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from statistics import median
from time import perf_counter
from typing import Sequence

import polars as pl

from prosper_or_perish_constructor.simulation.equilibrium import (
    ProvinceEquilibrium,
    solve_province_equilibrium,
)
from prosper_or_perish_constructor.simulation.profile import (
    load_population_simulation_profile,
    prepare_population_simulation_state,
)
from prosper_or_perish_constructor.simulation.modifiers import (
    SimulationModifierContext,
)
from prosper_or_perish_constructor.simulation.run import Simulation


@dataclass(frozen=True)
class EquilibriumReportResult:
    report_path: Path
    elapsed_seconds: float
    province_count: int
    validation_years: tuple[int, ...]


def run_population_equilibrium_report(
    *,
    repo: Path,
    project: Path,
    profile_path: Path,
    output_path: Path,
    validation_years: Sequence[int] = (100, 200, 500, 1_000, 2_000, 5_000),
) -> EquilibriumReportResult:
    """Solve named province setpoints and compare them with isolated simulations."""

    started = perf_counter()
    years = tuple(sorted(set(int(year) for year in validation_years)))
    if not years or years[0] <= 0:
        raise ValueError("validation years must be positive")

    profile = load_population_simulation_profile(profile_path, repo=repo)
    state, context, _preparation = prepare_population_simulation_state(
        repo,
        project,
        profile,
    )
    anchors = _anchor_provinces(state, profile.spot_check_locations)
    predictions: list[tuple[str, ProvinceEquilibrium, ProvinceEquilibrium]] = []
    validations: dict[str, dict[int, dict[str, float]]] = {}
    for anchor, province in anchors:
        province_state = state.filter(pl.col("province") == province)
        quasi = solve_province_equilibrium(
            province_state,
            context,
            population_mode="aggregate",
        )
        asymptotic = solve_province_equilibrium(
            province_state,
            context,
            population_mode="asymptotic",
        )
        predictions.append((anchor, quasi, asymptotic))

        simulation = Simulation(province_state, context)
        checkpoints: dict[int, dict[str, float]] = {}
        previous = 0
        for year in years:
            simulation.run((year - previous) * 12, progress=False)
            checkpoints[year] = _state_summary(simulation.state)
            previous = year
        validations[province] = checkpoints

    report = build_population_equilibrium_report(
        profile_path=profile.path,
        context=context,
        predictions=predictions,
        validations=validations,
        validation_years=years,
        elapsed_seconds=perf_counter() - started,
    )
    resolved_output = output_path if output_path.is_absolute() else repo / output_path
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    resolved_output.write_text(report, encoding="utf-8")
    return EquilibriumReportResult(
        report_path=resolved_output,
        elapsed_seconds=perf_counter() - started,
        province_count=len(predictions),
        validation_years=years,
    )


def build_population_equilibrium_report(
    *,
    profile_path: Path,
    context: SimulationModifierContext,
    predictions: Sequence[tuple[str, ProvinceEquilibrium, ProvinceEquilibrium]],
    validations: dict[str, dict[int, dict[str, float]]],
    validation_years: Sequence[int],
    elapsed_seconds: float,
) -> str:
    """Render the formal reduction, predictions, and trajectory comparison."""

    prosperity = context.prosperity
    food_growth = float(context.food_growth_baselines["local_population_growth"])
    development_gain = prosperity.get_effect("local_monthly_development")
    development_modifier = prosperity.get_effect("local_monthly_development_modifier")
    rank_rows = context.rank_baselines.select(
        "location_rank",
        "local_population_growth",
    ).sort("location_rank").to_dicts()

    lines = [
        "# Population and Development Equilibrium Report",
        "",
        f"- Simulation profile: `{profile_path}`",
        f"- Runtime: {elapsed_seconds:.1f} seconds",
        f"- Provinces: {len(predictions)}",
        "- Method: algebraic zero-change equations; simulator used only for validation",
        "",
        "## Formal reduction",
        "",
        "For a province, `H` is post-food months stored, `S = H / 12` is the capped stored-year scale, "
        "`P` is prosperity, `D` is development, and `x` scales the starting non-tribal population composition.",
        "",
        "```text",
        f"aggregate population: 0 = weighted_rank_growth + {food_growth:g} * S",
        f"prosperity income:     I = 100 * ({prosperity.base_monthly_prosperity:g} + {prosperity.food_growth_monthly_prosperity:g} * S)",
        f"prosperity rest:       P = (P + I) * (1 - {prosperity.global_prosperity_decay:g} - {prosperity.local_prosperity_decay:g} * P / 100)",
        f"development rest:      0 = (P / 100 * {development_gain:g} + D * {prosperity.development_monthly_per_point:g}) * (1 + P / 100 * {development_modifier:g})",
        f"province food rest:    production(x, D, P) = consumption(x, D, P) * (1 + {context.food_decay_rate:g} * H)",
        "```",
        "",
        "The first equation fixes `S`; the next two give `P(S)` and `D(P)` directly. "
        "Only the final scalar equation in `x` requires root finding. The food-decay term is exact for the simulator's order: net food is applied, stored months are read, then spoilage occurs.",
        "",
        "Rank-specific zero-growth storage requirements:",
        "",
        "| Rank | Annual baseline | Required stored months |",
        "|---|---:|---:|",
    ]
    for row in rank_rows:
        rank = str(row["location_rank"])
        growth = float(row["local_population_growth"])
        required_months = -growth / food_growth * 12.0
        lines.append(f"| {rank} | {growth:+.4%} | {required_months:.2f} |")

    lines.extend(
        [
            "",
            "A province containing both rural and urban non-tribal population cannot make every location exactly stationary because food storage is shared but the rank requirements differ. Its result is an aggregate, composition-preserving quasi-equilibrium. The individual-growth range below quantifies the remaining drift.",
            "",
            "## Algebraic resting-point predictions",
            "",
            "| Anchor | Model | Province | Start pop | Selected pop | All candidate populations | Pop ratio | Stored months | Prosperity | Start dev | Rest dev | Eliminated incompatible pop | Individual annual growth | Food solution |",
            "|---|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for anchor, quasi, asymptotic in predictions:
        for label, prediction in (("quasi", quasi), ("asymptotic", asymptotic)):
            population = _number(prediction.population)
            ratio = (
                prediction.population / prediction.starting_population
                if prediction.population is not None and prediction.starting_population > 0.0
                else None
            )
            growth_range = (
                f"{prediction.minimum_individual_annual_growth:+.4%} to "
                f"{prediction.maximum_individual_annual_growth:+.4%}"
            )
            if prediction.population_root_count:
                food_solution = f"{prediction.population_root_count} exact root(s)"
            elif prediction.pressure_threshold_crossing_count:
                food_solution = "threshold cycle"
            else:
                food_solution = prediction.status
            exact_candidates = [
                prediction.fixed_population
                + multiplier * prediction.movable_population
                for multiplier in prediction.population_root_multipliers
            ]
            threshold_candidates = [
                prediction.fixed_population
                + multiplier * prediction.movable_population
                for multiplier in prediction.pressure_threshold_multipliers
            ]
            candidate_parts = [f"{value:,.1f} exact" for value in exact_candidates]
            candidate_parts.extend(
                f"{value:,.1f} threshold" for value in threshold_candidates
            )
            candidates = ", ".join(candidate_parts) or "—"
            lines.append(
                "| "
                + " | ".join(
                    [
                        anchor,
                        label,
                        prediction.province,
                        f"{prediction.starting_population:,.1f}",
                        population,
                        candidates,
                        _ratio(ratio),
                        f"{prediction.stored_food_months:.2f}",
                        f"{prediction.prosperity:.2f}",
                        f"{prediction.starting_development_mean:.2f}",
                        f"{prediction.development:.2f}",
                        f"{prediction.eliminated_population:,.1f}",
                        growth_range,
                        food_solution,
                    ]
                )
                + " |"
            )

    lines.extend(
        [
            "",
            "Population values are EU5 game units (one unit is 1,000 people in this profile). A threshold cycle means the scalar food residual changes sign at a discontinuous abundant/available/neutral pressure boundary; there is no exact fixed point, but the boundary supplies a narrow predicted resting range.",
            "",
            "## Simulator comparison",
            "",
            "Each containing province is simulated in isolation from the same game-start state. Population error is measured against the algebraic prediction, not against historical targets.",
            "",
            "| Anchor | Years | Sim pop | Quasi pop | Quasi error | Selected asymptotic pop | Selected error | Nearest asymptotic candidate | Candidate error | Sim dev | Asymptotic rest dev | Sim prosperity |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    final_candidate_errors: list[float] = []
    final_development_errors: list[float] = []
    final_year = max(int(year) for year in validation_years)
    for anchor, quasi, asymptotic in predictions:
        candidate_populations = _candidate_populations(asymptotic)
        for year in validation_years:
            observed = validations[quasi.province][int(year)]
            quasi_error = (
                observed["population"] / quasi.population - 1.0
                if quasi.population is not None and quasi.population > 0.0
                else None
            )
            asymptotic_error = (
                observed["population"] / asymptotic.population - 1.0
                if asymptotic.population is not None and asymptotic.population > 0.0
                else None
            )
            nearest_candidate = (
                min(
                    candidate_populations,
                    key=lambda candidate: abs(observed["population"] - candidate),
                )
                if candidate_populations
                else None
            )
            candidate_error = (
                observed["population"] / nearest_candidate - 1.0
                if nearest_candidate is not None and nearest_candidate > 0.0
                else None
            )
            if int(year) == final_year:
                if candidate_error is not None:
                    final_candidate_errors.append(abs(candidate_error))
                final_development_errors.append(
                    abs(observed["development"] - asymptotic.development)
                )
            lines.append(
                "| "
                + " | ".join(
                    [
                        anchor,
                        str(year),
                        f"{observed['population']:,.1f}",
                        _number(quasi.population),
                        _percent(quasi_error),
                        _number(asymptotic.population),
                        _percent(asymptotic_error),
                        _number(nearest_candidate),
                        _percent(candidate_error),
                        f"{observed['development']:.2f}",
                        f"{asymptotic.development:.2f}",
                        f"{observed['prosperity']:.2f}",
                    ]
                )
                + " |"
            )

    lines.extend(
        [
            "",
            "## Validation summary",
            "",
            (
                f"At {final_year:,} years, the nearest algebraic asymptotic population candidate "
                f"has median absolute error {_percent(median(final_candidate_errors) if final_candidate_errors else None)} "
                f"and maximum absolute error {_percent(max(final_candidate_errors) if final_candidate_errors else None)}."
            ),
            (
                f"The corresponding development resting point has median absolute error "
                f"{median(final_development_errors):.2f} points and maximum absolute error "
                f"{max(final_development_errors):.2f} points."
                if final_development_errors
                else "No development validation rows were available."
            ),
            "",
            "## Interpretation",
            "",
            "- Exact positive population fixed points require one non-tribal rank-growth requirement per shared-food province, or another location-specific growth term that offsets the rank difference.",
            "- Mixed-rank predictions are intended as 100–500 year aggregate setpoints. Over very long spans, the simulator slowly changes the rural/urban composition because their rank baselines differ by 0.1 percentage point per year.",
            "- Development converges slowly because its parsed decay is proportional to the current development stock. A large 100- or 200-year development error does not by itself contradict the resting point.",
            "- Discontinuous capacity-pressure bands can replace an exact root with a small threshold cycle. Smoothing those boundaries would turn many such cases into ordinary roots.",
            "- Existence and coordinates come from the algebraic equations. Full-system stability remains a separate Jacobian or perturbation question.",
            "",
        ]
    )
    return "\n".join(lines)


def _anchor_provinces(
    state: pl.DataFrame,
    location_tags: Sequence[str],
) -> list[tuple[str, str]]:
    province_by_tag = {
        str(row["location_tag"]): str(row["province"])
        for row in state.filter(pl.col("location_tag").is_in(location_tags))
        .select("location_tag", "province")
        .to_dicts()
    }
    seen: set[str] = set()
    rows: list[tuple[str, str]] = []
    for tag in location_tags:
        province = province_by_tag.get(str(tag))
        if province is None or province in seen:
            continue
        rows.append((str(tag), province))
        seen.add(province)
    return rows


def _state_summary(state: pl.DataFrame) -> dict[str, float]:
    return {
        "population": float(state["total_population"].sum()),
        "development": float(state["development"].mean()),
        "prosperity": float(state["prosperity"].mean()),
    }


def _number(value: float | None) -> str:
    return "—" if value is None else f"{value:,.1f}"


def _ratio(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}×"


def _percent(value: float | None) -> str:
    return "—" if value is None else f"{value:+.1%}"


def _candidate_populations(prediction: ProvinceEquilibrium) -> list[float]:
    multipliers = (
        *prediction.population_root_multipliers,
        *prediction.pressure_threshold_multipliers,
    )
    return [
        prediction.fixed_population + multiplier * prediction.movable_population
        for multiplier in multipliers
    ]
