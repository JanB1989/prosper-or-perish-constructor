import marimo

__generated_with = "0.24.0"
app = marimo.App(width="full", css_file="location_capacity_playground.css")


@app.cell(hide_code=True)
def _():
    from dataclasses import asdict
    import hashlib
    import json
    from pathlib import Path

    import marimo as mo
    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize, TwoSlopeNorm
    import numpy as np
    import polars as pl

    from prosper_or_perish_constructor.savegame_maps import (
        load_map_assets,
        paint_location_metric_raster,
    )
    from prosper_or_perish_constructor.simulation.location_capacity_calibration import (
        LocationCapacityWeights,
        diagnostic_groups,
        evaluate_location_capacity,
        export_location_capacity_run,
        macro_region_attribution,
        prepare_location_capacity_inputs,
        summarize_location_capacity,
        weights_from_profile,
    )
    from prosper_or_perish_constructor.simulation.profile import (
        load_population_simulation_profile,
        prepare_population_simulation_state,
    )
    from prosper_or_perish_constructor.simulation.notebook_outputs import (
        attach_theoretical_max_population_capacity,
        macro_region_statistics,
    )

    return (
        LocationCapacityWeights,
        Normalize,
        Path,
        TwoSlopeNorm,
        asdict,
        attach_theoretical_max_population_capacity,
        diagnostic_groups,
        evaluate_location_capacity,
        export_location_capacity_run,
        hashlib,
        json,
        load_map_assets,
        load_population_simulation_profile,
        macro_region_attribution,
        macro_region_statistics,
        mo,
        np,
        paint_location_metric_raster,
        pl,
        plt,
        prepare_location_capacity_inputs,
        prepare_population_simulation_state,
        summarize_location_capacity,
        weights_from_profile,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Global population-capacity calibration

    This is a **1337 calibration**, not a time simulation. Every location uses one formula and one set of weights. China, India, the Nile, Iceland, the steppes, and Central Africa are diagnostics; they never receive overrides.

    Internal capacities are people. EU5 modifier values are converted with the current simulator profile's `people_per_game_unit`.
    """)
    return


@app.cell(hide_code=True)
def _(
    Path,
    attach_theoretical_max_population_capacity,
    hashlib,
    json,
    load_population_simulation_profile,
    pl,
    prepare_location_capacity_inputs,
    prepare_population_simulation_state,
    weights_from_profile,
):
    repo = Path(__file__).resolve().parents[2]
    profile = load_population_simulation_profile(
        repo / "population_capacity_simulation.toml",
        repo=repo,
    )
    starting_locations, parsed_modifiers, preparation = (
        prepare_population_simulation_state(
            repo,
            repo / "constructor.toml",
            profile,
        )
    )
    starting_locations = attach_theoretical_max_population_capacity(
        starting_locations,
        capacity_per_level=profile.infrastructure_capacity_per_level,
        development_relative=profile.capacity_formula.development_relative,
        global_relative=profile.capacity_formula.global_relative,
    ).with_columns(
        pl.col("development").alias("accepted_starting_development"),
        pl.col("deployed_static_population_capacity").alias(
            "accepted_location_potential"
        ),
        pl.col("infrastructure_population_capacity").alias(
            "accepted_infrastructure_capacity"
        ),
        pl.col("local_population_capacity").alias(
            "accepted_starting_population_capacity"
        ),
        pl.when(pl.col("local_population_capacity") > 0.0)
        .then(pl.col("total_population") / pl.col("local_population_capacity"))
        .otherwise(None)
        .alias("accepted_capacity_fill"),
    )
    candidate_source_path = profile.candidates_path
    landcover_source_path = (
        repo
        / "artifacts/data/population_capacity/location_landcover_capacity.parquet"
    )
    landcover_manifest_path = (
        repo
        / "artifacts/data/population_capacity/landcover_sources/landcover_source_manifest.json"
    )
    candidate_source = pl.read_parquet(candidate_source_path)
    landcover_source = pl.read_parquet(landcover_source_path)
    capacity_inputs = prepare_location_capacity_inputs(
        starting_locations,
        candidate_source,
        landcover_source,
    )
    profile_defaults = weights_from_profile(profile)

    def file_sha256(path):
        digest = hashlib.sha256()
        with Path(path).open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    landcover_manifest = json.loads(
        landcover_manifest_path.read_text(encoding="utf-8")
    )
    source_hashes = {
        "location_candidates": file_sha256(candidate_source_path),
        "location_landcover_capacity": file_sha256(landcover_source_path),
        "luh2_1300_slice": landcover_manifest["luh2"]["slice_sha256"],
        "sage_pnv_netcdf": landcover_manifest["sage_pnv"]["netcdf_sha256"],
    }
    return (
        capacity_inputs,
        landcover_manifest,
        landcover_source_path,
        profile,
        profile_defaults,
        repo,
        source_hashes,
        starting_locations,
    )


@app.cell(hide_code=True)
def _(
    asdict,
    landcover_manifest,
    landcover_source_path,
    mo,
    profile,
    profile_defaults,
):
    mo.hstack(
        [
            mo.stat(
                label="Start year",
                value=str(profile.start_year),
                caption="Static calibration",
            ),
            mo.stat(
                label="Locations",
                value="20,929",
                caption="One global formula",
            ),
            mo.stat(
                label="EU5 unit",
                value=f"{profile.people_per_game_unit:,.0f} people",
                caption="Per game population unit",
            ),
            mo.stat(
                label="LUH2 slice",
                value=str(landcover_manifest["luh2"]["year"]),
                caption=landcover_manifest["luh2"]["slice_sha256"][:12],
            ),
        ],
        widths="equal",
        gap=1,
    )
    mo.accordion(
        {
            "Resolved source contract": mo.md(
                f"""
                - LUH2 year: `{landcover_manifest['luh2']['year']}`
                - LUH2 frozen slice: `{landcover_manifest['luh2']['slice_sha256']}`
                - SAGE PNV: `{landcover_manifest['sage_pnv']['netcdf_sha256']}`
                - Location land-cover artifact: `{landcover_source_path}`
                - Parsed defaults: `{asdict(profile_defaults)}`
                """
            )
        }
    )
    return


@app.cell(hide_code=True)
def _(mo, profile_defaults):
    def number(value, step, start=None, stop=None):
        return mo.ui.number(
            value=float(value),
            step=step,
            start=start,
            stop=stop,
            full_width=True,
        )

    physical_quantile_input = mo.ui.dropdown(
        options={"Conservative p10": "p10", "Median p50": "p50", "High p90": "p90"},
        value="Median p50",
        full_width=True,
    )
    crop_weight_input = number(profile_defaults.crop_weight, 0.05, 0.0, 5.0)
    livestock_weight_input = number(profile_defaults.livestock_weight, 0.05, 0.0, 5.0)
    wild_weight_input = number(profile_defaults.wild_weight, 0.05, 0.0, 5.0)
    freshwater_weight_input = number(profile_defaults.freshwater_weight, 0.05, 0.0, 5.0)
    marine_weight_input = number(profile_defaults.marine_weight, 0.05, 0.0, 5.0)

    development_base_input = number(profile_defaults.development_base, 0.25, 0.0, 100.0)
    development_minimum_manageable_input = number(
        profile_defaults.development_minimum_manageable_cropland_fraction,
        0.005,
        0.001,
        1.0,
    )
    development_crop_points_input = number(profile_defaults.development_crop_points, 0.5, 0.0, 100.0)
    development_crop_saturation_input = number(
        profile_defaults.development_crop_saturation_rate, 0.1, 0.0, 20.0
    )
    development_pasture_points_input = number(
        profile_defaults.development_pasture_points, 0.25, 0.0, 100.0
    )
    development_minimum_input = number(profile_defaults.development_minimum, 0.25, 0.0, 100.0)
    development_maximum_input = number(profile_defaults.development_maximum, 0.5, 0.0, 200.0)
    development_relative_input = number(profile_defaults.development_relative, 0.001, 0.0, 1.0)
    global_relative_input = number(profile_defaults.global_relative, 0.01, -0.5, 0.0)

    clearing_realization_input = number(profile_defaults.clearing_realization, 0.01, 0.0, 1.0)
    irrigation_scale_input = number(profile_defaults.irrigation_scale, 0.05, 0.0, 20.0)
    irrigation_exponent_input = number(profile_defaults.irrigation_exponent, 0.05, 0.0, 5.0)
    tsetse_weight_input = number(profile_defaults.tsetse_weight, 0.05, 0.0, 1.0)
    minimum_capacity_input = number(profile_defaults.minimum_capacity_game_units, 1.0, 0.0, 10000.0)
    map_lower_percentile_input = number(1.0, 0.5, 0.0, 99.0)
    map_upper_percentile_input = number(99.0, 0.5, 1.0, 100.0)

    def row(label, control):
        return mo.hstack([mo.md(label), control], widths=[2, 1], align="center")

    control_layout = mo.vstack(
        [
            mo.md("## Accepted simulation defaults and calibration controls"),
            mo.md(
                "The fields open with the accepted values from `population_capacity_simulation.toml`. Clearing and continuous irrigation are neutral because the accepted model now realizes them through flat-capacity buildings."
            ),
            mo.md("#### Physical uncertainty and base resources"),
            row("Physical quantile", physical_quantile_input),
            row("Open rainfed crop weight", crop_weight_input),
            row("Extensive livestock weight", livestock_weight_input),
            row("Retained wild / forest-food weight", wild_weight_input),
            row("Freshwater weight", freshwater_weight_input),
            row("Marine weight", marine_weight_input),
            mo.md("#### HYDE-derived starting development"),
            row("Base development", development_base_input),
            row("Minimum manageable cropland fraction", development_minimum_manageable_input),
            row("Cropland development points", development_crop_points_input),
            row("Cropland saturation rate", development_crop_saturation_input),
            row("Pasture development points", development_pasture_points_input),
            row("Development lower bound", development_minimum_input),
            row("Development upper bound", development_maximum_input),
            row("Relative capacity per development point", development_relative_input),
            row("Global population-capacity modifier", global_relative_input),
            mo.md("#### Clearing, irrigation, and experiment"),
            row("Clearing realization", clearing_realization_input),
            row("Irrigation scale", irrigation_scale_input),
            row("Irrigation exponent", irrigation_exponent_input),
            row("Experimental tsetse effect", tsetse_weight_input),
            row("Minimum capacity (game units)", minimum_capacity_input),
            mo.md("#### Map display range"),
            row("Lower percentile", map_lower_percentile_input),
            row("Upper percentile", map_upper_percentile_input),
        ],
        gap=0.2,
    )
    calibration_form = control_layout.batch(
        physical_quantile=physical_quantile_input,
        crop_weight=crop_weight_input,
        livestock_weight=livestock_weight_input,
        wild_weight=wild_weight_input,
        freshwater_weight=freshwater_weight_input,
        marine_weight=marine_weight_input,
        development_base=development_base_input,
        development_minimum_manageable_cropland_fraction=development_minimum_manageable_input,
        development_crop_points=development_crop_points_input,
        development_crop_saturation_rate=development_crop_saturation_input,
        development_pasture_points=development_pasture_points_input,
        development_minimum=development_minimum_input,
        development_maximum=development_maximum_input,
        development_relative=development_relative_input,
        global_relative=global_relative_input,
        clearing_realization=clearing_realization_input,
        irrigation_scale=irrigation_scale_input,
        irrigation_exponent=irrigation_exponent_input,
        tsetse_weight=tsetse_weight_input,
        minimum_capacity_game_units=minimum_capacity_input,
        map_lower_percentile=map_lower_percentile_input,
        map_upper_percentile=map_upper_percentile_input,
    ).form(submit_button_label="Evaluate global formula", clear_on_submit=False)
    calibration_form
    return (calibration_form,)


@app.cell(hide_code=True)
def _(
    LocationCapacityWeights,
    asdict,
    calibration_form,
    capacity_inputs,
    evaluate_location_capacity,
    profile,
    profile_defaults,
    summarize_location_capacity,
):
    submitted_values = (
        asdict(profile_defaults)
        | {"map_lower_percentile": 1.0, "map_upper_percentile": 99.0}
        | (calibration_form.value or {})
    )
    resolved_weights = LocationCapacityWeights(
        **{
            key: submitted_values[key]
            for key in asdict(profile_defaults)
        }
    )
    location_results = evaluate_location_capacity(
        capacity_inputs,
        resolved_weights,
        people_per_game_unit=profile.people_per_game_unit,
    )
    capacity_summary = summarize_location_capacity(
        location_results,
        profile=profile,
    )
    map_lower_percentile = float(submitted_values["map_lower_percentile"])
    map_upper_percentile = float(submitted_values["map_upper_percentile"])
    return (
        capacity_summary,
        location_results,
        map_lower_percentile,
        map_upper_percentile,
        resolved_weights,
    )


@app.cell(hide_code=True)
def _(capacity_summary, location_results, mo, pl, profile):
    current_total = float(location_results["current_capacity_people"].sum())
    candidate_total = float(location_results["candidate_capacity_people"].sum())
    current_fill = float(location_results["starting_population_people"].sum()) / max(
        current_total, 1e-12
    )
    current_within_capacity = float(
        (
            location_results["starting_population_people"]
            <= location_results["current_capacity_people"]
        ).mean()
    )
    current_maximum = float(
        (
            location_results["current_capacity_people"]
            / profile.people_per_game_unit
        ).max()
    )
    comparison_table = pl.DataFrame(
        {
            "Measure": [
                "Total capacity (people)",
                "Global starting fill",
                "Locations within capacity",
                "Maximum location capacity (game units)",
            ],
            "Current": [
                f"{current_total:,.0f}",
                f"{current_fill:.1%}",
                f"{current_within_capacity:.1%}",
                f"{current_maximum:,.1f}",
            ],
            "Candidate": [
                f"{candidate_total:,.0f}",
                f"{capacity_summary['global_population_fill']:.1%}",
                f"{capacity_summary['location_within_capacity_fraction']:.1%}",
                f"{capacity_summary['max_location_capacity_game_units']:,.1f}",
            ],
        }
    )
    gate_table = pl.DataFrame(
        {
            "Configured simulator sanity gate": list(capacity_summary["sanity_gates"]),
            "Pass": list(capacity_summary["sanity_gates"].values()),
        }
    )
    fill_distribution_table = pl.DataFrame(
        {
            "Population-weighted fill statistic": ["p10", "p50", "p90"],
            "Candidate": [
                capacity_summary["population_weighted_fill_p10"],
                capacity_summary["population_weighted_fill_p50"],
                capacity_summary["population_weighted_fill_p90"],
            ],
        }
    )
    mo.vstack(
        [
            mo.md("## Current versus candidate"),
            mo.ui.table(comparison_table, selection=None, pagination=False),
            mo.md("### Population-weighted fill distribution"),
            mo.ui.table(
                fill_distribution_table,
                selection=None,
                pagination=False,
                format_mapping={
                    "Candidate": lambda value: f"{float(value):.1%}"
                },
            ),
            mo.md(
                f"**Configured sanity result:** {'PASS' if capacity_summary['sanity_passed'] else 'FAIL'}"
            ),
            mo.ui.table(gate_table, selection=None, pagination=False),
        ],
        gap=0.5,
    )
    return


@app.cell(hide_code=True)
def _(diagnostic_groups, location_results, macro_region_attribution, mo):
    attribution_table = macro_region_attribution(location_results)
    diagnostic_table = diagnostic_groups(location_results)
    _diagnostic_people_columns = (
        "base_location_potential_people",
        "candidate_capacity_people",
        "starting_population_people",
        "crop_contribution_people",
        "livestock_contribution_people",
        "wild_contribution_people",
        "freshwater_contribution_people",
        "marine_contribution_people",
        "development_total_contribution_people",
        "clearing_contribution_people",
        "irrigation_contribution_people",
        "minimum_floor_contribution_people",
    )
    diagnostic_formatting = {
        "locations": lambda value: f"{int(value):,}",
        "population_fill": lambda value: f"{float(value):.1%}",
        "median_base_density_people_per_km2": lambda value: f"{float(value):,.1f}",
        **{
            column: lambda value: f"{float(value):,.0f}"
            for column in _diagnostic_people_columns
            if column in diagnostic_table.columns
        },
    }
    attribution_formatting = {
        "population_fill": lambda value: f"{float(value):.1%}",
        **{
            column: lambda value: f"{float(value):,.0f}"
            for column in _diagnostic_people_columns
            if column in attribution_table.columns
        },
    }
    mo.vstack(
        [
            mo.md("## Global attribution and geographic diagnostics"),
            mo.md(
                "Diagnostics expose where the one formula succeeds or fails. They do not change any location value."
            ),
            mo.ui.table(
                diagnostic_table,
                selection=None,
                pagination=False,
                format_mapping=diagnostic_formatting,
            ),
            mo.accordion(
                {
                    "Macro-region attribution": mo.ui.table(
                        attribution_table,
                        selection=None,
                        pagination=True,
                        page_size=15,
                        format_mapping=attribution_formatting,
                    )
                }
            ),
        ],
        gap=0.5,
    )
    return


@app.cell(hide_code=True)
def _(location_results, mo):
    macro_options = sorted(
        str(value)
        for value in location_results["macro_region"].drop_nulls().unique().to_list()
    )
    macro_region_selector = mo.ui.dropdown(
        options=["All", *macro_options], value="All", label="Macro-region"
    )
    macro_region_selector
    return (macro_region_selector,)


@app.cell(hide_code=True)
def _(location_results, macro_region_selector, mo, pl):
    hierarchy_subset = (
        location_results
        if macro_region_selector.value == "All"
        else location_results.filter(
            pl.col("macro_region") == macro_region_selector.value
        )
    )
    region_options = sorted(
        str(value)
        for value in hierarchy_subset["region"].drop_nulls().unique().to_list()
    )
    region_selector = mo.ui.dropdown(
        options=["All", *region_options], value="All", label="Region"
    )
    region_selector
    return hierarchy_subset, region_selector


@app.cell(hide_code=True)
def _(hierarchy_subset, mo, pl, region_selector):
    region_subset = (
        hierarchy_subset
        if region_selector.value == "All"
        else hierarchy_subset.filter(pl.col("region") == region_selector.value)
    )
    location_options = sorted(region_subset["location_tag"].to_list())
    default_locations = location_options[: min(10, len(location_options))]
    location_selector = mo.ui.multiselect(
        options=location_options,
        value=default_locations,
        label="Locations",
        max_selections=50,
        full_width=True,
    )
    location_selector
    return location_selector, region_subset


@app.cell(hide_code=True)
def _(location_selector, mo, pl, region_subset):
    selected_tags = location_selector.value or []
    detailed_columns = [
        "location_tag",
        "macro_region",
        "region",
        "area_km2",
        "forest_fraction_1300",
        "cropland_fraction_1300",
        "pasture_fraction_1300",
        "rangeland_fraction_1300",
        "open_crop_suitability_share",
        "base_location_potential_people",
        "candidate_starting_development",
        "development_total_contribution_people",
        "clearing_potential_people",
        "clearing_contribution_people",
        "irrigation_potential_people",
        "irrigation_contribution_people",
        "current_capacity_people",
        "candidate_capacity_people",
        "starting_population_people",
        "population_fill",
    ]
    detailed_locations = (
        region_subset.filter(pl.col("location_tag").is_in(selected_tags))
        .select(detailed_columns)
        .sort("candidate_capacity_people", descending=True)
    )
    _detail_fraction_columns = (
        "forest_fraction_1300",
        "cropland_fraction_1300",
        "pasture_fraction_1300",
        "rangeland_fraction_1300",
        "open_crop_suitability_share",
        "population_fill",
    )
    _detail_people_columns = (
        "base_location_potential_people",
        "development_total_contribution_people",
        "clearing_potential_people",
        "clearing_contribution_people",
        "irrigation_potential_people",
        "irrigation_contribution_people",
        "current_capacity_people",
        "candidate_capacity_people",
        "starting_population_people",
    )
    detailed_formatting = {
        "area_km2": lambda value: f"{float(value):,.1f}",
        "candidate_starting_development": lambda value: f"{float(value):,.2f}",
        **{
            column: lambda value: f"{float(value):.1%}"
            for column in _detail_fraction_columns
        },
        **{
            column: lambda value: f"{float(value):,.0f}"
            for column in _detail_people_columns
        },
    }
    mo.vstack(
        [
            mo.md("## Location detail"),
            mo.ui.table(
                detailed_locations,
                selection=None,
                pagination=False,
                show_download=True,
                freeze_columns_left=["location_tag"],
                format_mapping=detailed_formatting,
            ),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    map_metrics = {
        "Starting development": "accepted_starting_development",
        "Location potential": "accepted_location_potential",
        "Infrastructure capacity": "accepted_infrastructure_capacity",
        "Starting population capacity": "accepted_starting_population_capacity",
        "Capacity fill": "accepted_capacity_fill",
        "Maximum population capacity": "theoretical_max_population_capacity",
    }
    map_metric_selector = mo.ui.dropdown(
        options=map_metrics,
        value="Starting population capacity",
        label="Map layer",
        full_width=True,
    )
    map_metric_selector
    return map_metric_selector, map_metrics


@app.cell(hide_code=True)
def _(load_map_assets, repo):
    map_assets = load_map_assets(
        repo=repo,
        project=repo / "constructor.toml",
        map_width=2400,
    )
    return (map_assets,)


@app.cell(hide_code=True)
def _(
    Normalize,
    map_assets,
    map_metric_selector,
    map_upper_percentile,
    mo,
    np,
    paint_location_metric_raster,
    plt,
    starting_locations,
):
    selected_metric = map_metric_selector.value
    painted_metric = paint_location_metric_raster(
        map_assets,
        starting_locations,
        value_column=selected_metric,
        nodata=float("nan"),
    )
    metric_values = starting_locations[selected_metric].to_numpy()
    finite_metric_values = metric_values[np.isfinite(metric_values)]
    display_low = 0.0
    if selected_metric == "accepted_capacity_fill":
        display_high = float(finite_metric_values.max())
        metric_norm = Normalize(vmin=0.0, vmax=max(display_high, 1e-12))
        metric_cmap = "YlOrRd"
        range_note = "The observed maximum is mapped to red."
    elif selected_metric == "accepted_starting_development":
        display_high = 100.0
        metric_norm = Normalize(vmin=0.0, vmax=100.0)
        metric_cmap = "viridis"
        range_note = "Development uses its full 0–100 gameplay range."
    else:
        display_high = float(np.percentile(finite_metric_values, map_upper_percentile))
        metric_norm = Normalize(vmin=0.0, vmax=max(display_high, 1e-12))
        metric_cmap = "viridis"
        range_note = (
            f"Linear scale from zero to the {map_upper_percentile:g}th percentile; "
            "only higher outliers use the top colour."
        )
    map_figure, map_axis = plt.subplots(figsize=(16, 7.5), constrained_layout=True)
    map_image = map_axis.imshow(
        np.ma.masked_invalid(painted_metric.values),
        cmap=metric_cmap,
        norm=metric_norm,
        interpolation="nearest",
    )
    map_axis.set_axis_off()
    map_axis.set_title(map_metric_selector.selected_key)
    map_figure.colorbar(map_image, ax=map_axis, shrink=0.72)
    mo.vstack(
        [
            mo.md("## In-memory EU5 location-pixel preview"),
            mo.md(
                f"Display range: **{display_low:,.3g}** to **{display_high:,.3g}**. "
                f"{range_note} No TIFF was written."
            ),
            map_figure,
        ]
    )
    return


@app.cell(hide_code=True)
def _(macro_region_statistics, map_metric_selector, mo, pl, starting_locations):
    _selected_metric = map_metric_selector.value
    _global_statistics = starting_locations.select(
        pl.lit("Global").alias("macro_region"),
        pl.col(_selected_metric).count().alias("count"),
        pl.col(_selected_metric).min().alias("min"),
        pl.col(_selected_metric).max().alias("max"),
        pl.col(_selected_metric).mean().alias("mean"),
        pl.col(_selected_metric).median().alias("median"),
        pl.col(_selected_metric).std(ddof=1).alias("std_dev"),
        pl.col(_selected_metric).sum().alias("sum"),
    )
    _macro_statistics = macro_region_statistics(starting_locations, _selected_metric)
    mo.vstack(
        [
            mo.md(f"## Statistics — {map_metric_selector.selected_key}"),
            mo.ui.table(
                pl.concat([_global_statistics, _macro_statistics]),
                selection=None,
                pagination=False,
            ),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo, repo):
    anchor_stats_path = (
        repo / "artifacts/data/population_capacity/current_capacity_map/anchor_stats.csv"
    )
    evidence_anchor_stats_path = (
        repo
        / "artifacts/data/population_capacity/current_capacity_map/evidence_anchor_stats.csv"
    )
    mo.accordion(
        {
            "Existing evidence-anchor results": mo.md(
                f"""
                These remain the current pipeline's evidence results; the notebook does
                not silently reinterpret or train on them.

                - `{anchor_stats_path}`
                - `{evidence_anchor_stats_path}`
                """
            )
        }
    )
    return anchor_stats_path, evidence_anchor_stats_path


@app.cell(hide_code=True)
def _(map_metrics, mo):
    geotiff_layer_selector = mo.ui.multiselect(
        options=map_metrics,
        value=[],
        label="GeoTIFF layers to export",
        full_width=True,
    )
    export_button = mo.ui.run_button(label="Export hash-addressed run")
    mo.vstack(
        [
            mo.md("## Explicit export"),
            mo.md(
                "Only this button writes outputs. It never changes the simulator profile, accepted capacity table, mod files, or game installation."
            ),
            geotiff_layer_selector,
            export_button,
        ]
    )
    return export_button, geotiff_layer_selector


@app.cell(hide_code=True)
def _(
    anchor_stats_path,
    capacity_summary,
    evidence_anchor_stats_path,
    export_button,
    export_location_capacity_run,
    geotiff_layer_selector,
    location_results,
    map_assets,
    mo,
    profile,
    repo,
    resolved_weights,
    source_hashes,
):
    if export_button.value:
        export_directory = export_location_capacity_run(
            location_results,
            resolved_weights,
            output_root=(
                repo
                / "artifacts/data/population_capacity/location_capacity_playground"
            ),
            people_per_game_unit=profile.people_per_game_unit,
            summary=capacity_summary,
            source_hashes=source_hashes,
            existing_anchor_results=(
                anchor_stats_path,
                evidence_anchor_stats_path,
            ),
            assets=map_assets,
            geotiff_layers=geotiff_layer_selector.value or (),
        )
        windows_export_path = (
            r"\\wsl.localhost\Ubuntu" + str(export_directory)
        )
        export_status = mo.callout(
            mo.md(f"Export complete: `{windows_export_path}`"),
            kind="success",
        )
    else:
        export_status = mo.callout(
            mo.md("No files have been exported in this session."),
            kind="info",
        )
    export_status
    return

if __name__ == "__main__":
    app.run()
