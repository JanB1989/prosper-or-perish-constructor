"""Compare dated Taihu field yields using the canonical food simulation.

uv run python research/population_capacity/run_taihu_yield_experiment.py

The six intervention locations are research pointers, not a mapped adoption
dataset. Preserve complete provinces for food sharing. No game export is made.
"""
from __future__ import annotations

import inspect
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import polars as pl

from prosper_or_perish_constructor.simulation.cache import fingerprint
from prosper_or_perish_constructor.simulation.crop_intensification import historical_paddy_support, intensive_crop_capacity_increment
from prosper_or_perish_constructor.simulation.land_investment import apply_land_conversion_experiment, POOLS
from prosper_or_perish_constructor.simulation.physical_support import PhysicalSupportTransform
from prosper_or_perish_constructor.simulation.profile import load_population_simulation_profile, prepare_population_simulation_state
from prosper_or_perish_constructor.simulation.run import Simulation
from prosper_or_perish_population_capacity import carrying_capacity


ROOT = Path(__file__).resolve().parents[2]
YEARS = (0, 25, 100, 200, 300, 400, 500)
TAGS = ("wuxian", "wujiang", "kunshan", "changshu", "jiaxing", "huating")
OVERRIDES = ("capacity.gaez_zero_development_fraction=1.5", "capacity.location_area_exponent=0.5",
             "mechanics.subsistence_output=1.25", "mechanics.development_monthly_per_point=-0.000025")


def run(*, full_provinces: bool = False, output_path: Path | None = None,
        scenario_names: list[str] | None = None, dry_matter_fractions=(.8, .86, .9),
        initial_food_months: float = 24.) -> dict:
    source_path = Path(__file__).with_name("historical_rice_yields.json")
    source = json.loads(source_path.read_text())
    yields = {x["id"]: x for x in source["observations"]}
    overrides = (*OVERRIDES, f"simulation.initial_food_months={initial_food_months}")
    profile = load_population_simulation_profile(ROOT / "population_capacity_simulation.toml", repo=ROOT, overrides=overrides)
    world, context, preparation = prepare_population_simulation_state(ROOT, ROOT / "constructor.toml", profile)
    provinces = world.filter(pl.col("location_tag").is_in(TAGS))["province"].unique()
    state = world.filter(pl.col("province").is_in(provinces.to_list())).sort("location_tag")
    intervention_tags = state["location_tag"].to_list() if full_provinces else list(TAGS)
    active = state["location_tag"].is_in(intervention_tags).to_numpy()
    area = state["area_km2"].to_numpy()
    base_crops = state["crop_fallow_block_km2"].to_numpy()
    crop_density = state["crop_support_density_people_per_cultivated_km2_p50"].to_numpy()
    inherited_allowance = state["infrastructure_population_capacity"].to_numpy()
    base_capacity = state["base_population_capacity"].to_numpy()
    transform = PhysicalSupportTransform(scale=profile.gaez_zero_development_fraction,
        area_exponent=profile.location_area_exponent, reference_area_km2=profile.location_area_reference_km2,
        people_per_game_unit=profile.people_per_game_unit)
    weights = profile.physical_capacity_weights
    crop_weight = weights["open_rainfed_capacity_people_p50"]
    output = output_path or ROOT / "artifacts/data/population_simulation/repair_round_18/taihu_yields"
    output.mkdir(parents=True, exist_ok=True)
    # Hold population, workers and food coefficients fixed while evaluating
    # pressure. These artificial K/P ratios are mechanics probes, never map
    # calibration targets or exportable location potentials.
    pressure_rows = []
    for fill in (.100001, .5, 1., 2.):
        probe = Simulation(state.with_columns(
            (pl.col("total_population") / fill).alias("local_population_capacity")),
            replace(context, capacity_model=None))
        probe.evaluate_food_budget()
        pressure_rows.append(probe.diagnostic_state().with_columns(pl.lit(fill).alias("diagnostic_fill")))
    pl.concat(pressure_rows).write_csv(output / "starting_pressure_probe.csv")
    plans = {
        "baseline": (0., None, 0.),
        "song_half_fields": (.5, None, 0.),
        "song_all_fields": (1., None, 0.),
        "song_half_then_ming": (.5, 200, 0.),
        "half_land_plus_song_all_fields": (1., None, .5),
        "half_land_song_then_ming": (1., 200, .5),
    }
    if scenario_names is not None:
        if not scenario_names or set(scenario_names) - plans.keys():
            raise ValueError("unknown or empty Taihu scenario selection")
        plans = {key: plans[key] for key in scenario_names}
    if not dry_matter_fractions or any(not np.isfinite(x) or not 0 < x <= 1 for x in dry_matter_fractions):
        raise ValueError("dry-matter sensitivity assumptions must be in (0, 1]")
    histories, events = [], []
    support_benchmarks = []
    for dryness in dry_matter_fractions:
        for key in ("taihu_song", "taihu_ming"):
            numeric = historical_paddy_support(catties_per_mou=yields[key]["catties_per_mou"],
                kg_per_catty=source["kg_per_catty_explicit_in_source"],
                mou_per_hectare=source["mou_per_hectare_explicit_in_source"], dry_matter_fraction=dryness)
            if numeric["paddy_kg_per_ha_per_harvest"] != yields[key]["kg_paddy_per_ha_per_crop"]:
                raise ValueError("historical yield transcription disagrees with source metrology")
            support_benchmarks.append({"observation": key, **numeric})
    for name, (share, later_year, reclaimed_fraction) in plans.items():
        moistures = dry_matter_fractions if name != "baseline" else (dry_matter_fractions[0],)
        for dryness in moistures:
            candidate = f"{name}__dry_{dryness:g}"
            initial = state
            added_land = np.zeros(state.height)
            if reclaimed_fraction:
                requests = state.filter(pl.col("location_tag").is_in(intervention_tags)).select("location_tag",
                    (pl.col(POOLS["forest"][0]) * reclaimed_fraction).alias("forest_km2"),
                    (pl.col(POOLS["open"][0]) * reclaimed_fraction).alias("open_km2"),
                    pl.lit("diagnostic half of remaining land; not measured adoption").alias("evidence_id"))
                initial, land_ledger = apply_land_conversion_experiment(initial, requests, formula=profile.capacity_formula)
                added_land = state.select("location_tag").join(land_ledger, on="location_tag", how="left", maintain_order="left").select(
                    pl.col("forest_km2").fill_null(0.) + pl.col("open_km2").fill_null(0.)
                ).to_series().to_numpy()
            land_allowance = initial["infrastructure_population_capacity"].to_numpy()
            simulation = Simulation(initial, context)
            monthly = []
            for month in range(max(YEARS) * 12 + 1):
                if month:
                    simulation.run(1, progress=False, materialize=False)
                if share and month in (0, (later_year or -1) * 12):
                    observation = "taihu_song" if month == 0 else "taihu_ming"
                    benchmark = next(x for x in support_benchmarks if x["observation"] == observation and x["dry_matter_fraction_assumption"] == dryness)
                    target = benchmark["standalone_people_per_cultivated_km2"]
                    hectares_km2 = (base_crops + added_land) * share * active
                    current = simulation.state
                    relative = profile.capacity_formula.evaluate(base_capacity=np.ones(state.height),
                        development=current["development"].to_numpy())
                    addition = intensive_crop_capacity_increment(cultivated_area_km2=hectares_km2,
                        baseline_density=crop_density, target_density=target,
                        existing_agricultural_allowance=inherited_allowance, area_km2=area,
                        relative_factor=relative, transform=transform, crop_weight=crop_weight) * active
                    infrastructure = land_allowance + addition
                    capacity = profile.capacity_formula.evaluate(base_capacity=base_capacity,
                        infrastructure_capacity=infrastructure, development=current["development"].to_numpy())
                    simulation.state = current.with_columns(pl.Series("infrastructure_population_capacity", infrastructure),
                        pl.Series("local_population_capacity", capacity), pl.lit(True).alias("capacity_experiment_only"))
                    events.append(state.select("location_tag").with_columns(pl.lit(candidate).alias("scenario"),
                        pl.lit(month).alias("month"), pl.lit(observation).alias("observation"),
                        pl.Series("intensive_area_km2", hectares_km2), pl.Series("new_flat_capacity", addition),
                        pl.Series("relative_factor_at_attainment", relative),
                        pl.Series("total_infrastructure_capacity", infrastructure),
                        pl.lit(target).alias("target_people_per_cultivated_km2")))
                simulation.evaluate_food_budget()
                monthly.append(simulation.diagnostic_state().with_columns(
                    pl.lit(month).alias("month"), pl.lit(candidate).alias("scenario")))
            histories.append(pl.concat(monthly, how="diagonal_relaxed"))
            print(f"Taihu yield diagnostic completed: {candidate}", flush=True)
    history = pl.concat(histories, how="diagonal_relaxed")
    history.write_parquet(output / "monthly_locations.parquet")
    events_frame = pl.concat(events, how="diagonal_relaxed") if events else pl.DataFrame(schema={"location_tag": pl.String, "scenario": pl.String})
    events_frame.write_csv(output / "interventions.csv")
    checkpoints = history.filter(pl.col("month").is_in([x * 12 for x in YEARS]))
    checkpoints.write_csv(output / "checkpoints.csv")
    totals = checkpoints.group_by("scenario", "month").agg(pl.col("total_population", "local_population_capacity", "starvation_months").sum(),
        pl.col("development").mean().alias("mean_development")).sort("scenario", "month")
    totals.write_csv(output / "totals.csv")
    manifest = {"accepted": False, "source": source, "intervention_locations": intervention_tags,
        "simulated_provinces": provinces.to_list(), "overrides": overrides, "years": YEARS,
        "scenario_plans": plans, "field_adoption_shares_are_assumptions": True,
        "dry_matter_fractions_are_assumptions": list(dry_matter_fractions), "physical_benchmarks": support_benchmarks,
        "formula": "net calorie/protein support of one rice crop divided by the current native relative factor, minus already counted crop support; canonical area transform; replaces existing agricultural allowance before adding excess",
        "limitations": ["Numerical crop benchmark does not establish hectares at that intensity in 1337",
            "Province-wide scope is a spatial sensitivity assumption, not a completed historical footprint crosswalk" if full_provinces else "Only six diagnostic locations receive additional support; their neighbours still share provincial food and starvation",
            "Ming attainment at year 200 is an explicit schedule assumption",
            "All-field and half-land cases are diagnostic bounds; neither is a proposed starting map",
            "No second harvest bonus, new edible-food coefficients or population fitting",
            "No native construction costs, labour demands or building maximum validation",
            "Rice monoculture protein support is conservative; the mixed nutrient budget still needs a canonical recalculation"],
        "fingerprint": fingerprint([Path(__file__), source_path, Path(inspect.getfile(carrying_capacity)),
            ROOT / "src/prosper_or_perish_constructor/simulation/crop_intensification.py"],
            {"source_fingerprint": preparation["source_fingerprint"],
             "modifier_fingerprint": preparation["modifier_fingerprint"],
             "food_evidence_fingerprint": preparation["food_evidence_fingerprint"],
             "overrides": overrides, "years": YEARS, "intervention_locations": intervention_tags,
             "plans": plans, "moisture_fractions": list(dry_matter_fractions)}),
        "preparation": preparation}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str) + "\n")
    starting_people = state["total_population"].sum() * profile.people_per_game_unit / 1e6
    lines = ["# Taihu historical field-yield experiments", "", "Diagnostic only. One gross rice harvest; adoption areas and moisture assumptions are not historical measurements.", "",
        f"Totals cover all {state.height} locations in the {len(provinces)} complete food-sharing provinces. Starting population: {starting_people:.3f} million. {len(intervention_tags)} locations receive the intervention.", "",
        "| Scenario | Population, year 500 (million) | Capacity, year 500 (million) |", "|---|---:|---:|"]
    scale = profile.people_per_game_unit / 1e6
    for row in totals.filter(pl.col("month") == 6000).iter_rows(named=True):
        lines.append(f"| {row['scenario']} | {row['total_population']*scale:.3f} | {row['local_population_capacity']*scale:.3f} |")
    lines.extend(["", *["- " + value for value in manifest["limitations"]], ""])
    (output / "report.md").write_text("\n".join(lines))
    return {"output": str(output), "accepted": False, "scenarios": history["scenario"].n_unique()}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full-provinces", action="store_true", help="Test the entire three-province Taihu cluster; diagnostic spatial scope only")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--scenario", action="append")
    parser.add_argument("--dry-matter", action="append", type=float)
    parser.add_argument("--initial-food-months", type=float, default=24.)
    args = parser.parse_args()
    print(json.dumps(run(full_provinces=args.full_provinces, output_path=args.output,
        scenario_names=args.scenario, dry_matter_fractions=args.dry_matter or (.8, .86, .9),
        initial_food_months=args.initial_food_months), indent=2))
