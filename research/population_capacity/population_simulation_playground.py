import marimo

__generated_with = "0.24.0"
app = marimo.App(
    width="medium",
    css_file="population_simulation_playground.css",
)


@app.cell(hide_code=True)
def _():
    from dataclasses import replace
    from pathlib import Path
    from time import perf_counter

    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np
    import polars as pl
    import rasterio
    from matplotlib.colors import Normalize, TwoSlopeNorm

    from prosper_or_perish_constructor.savegame_maps import (
        Log1pNorm,
        load_map_assets,
    )
    from prosper_or_perish_constructor.simulation.notebook_outputs import (
        SIMULATION_METRICS,
        macro_region_statistics,
        prepare_simulation_analysis_state,
        write_simulation_metric_geotiff,
    )

    from prosper_or_perish_constructor.simulation.profile import (
        load_population_simulation_profile,
        prepare_population_simulation_state,
    )
    from prosper_or_perish_constructor.simulation.run import Simulation

    return (
        Log1pNorm,
        Normalize,
        Path,
        SIMULATION_METRICS,
        Simulation,
        TwoSlopeNorm,
        load_map_assets,
        load_population_simulation_profile,
        macro_region_statistics,
        mo,
        np,
        perf_counter,
        pl,
        plt,
        prepare_population_simulation_state,
        prepare_simulation_analysis_state,
        rasterio,
        replace,
        write_simulation_metric_geotiff,
    )


@app.cell(hide_code=True)
def _(
    Path,
    load_population_simulation_profile,
    prepare_population_simulation_state,
):
    repo = Path(__file__).resolve().parents[2]
    profile = load_population_simulation_profile(
        repo / "population_capacity_simulation.toml",
        repo=repo,
    )
    starting_locations, parsed, _preparation = prepare_population_simulation_state(
        repo,
        repo / "constructor.toml",
        profile,
    )
    rank_population_growth = {
        str(row["location_rank"]): float(row["local_population_growth"])
        for row in parsed.rank_baselines.select(
            "location_rank", "local_population_growth"
        ).to_dicts()
    }

    def _capacity_pressure_value(band, effect):
        return float(parsed.capacity_pressure[band].get(effect, 0.0))

    parsed_constants = {
        "rural_settlement_population_growth": rank_population_growth[
            "rural_settlement"
        ],
        "town_population_growth": rank_population_growth["town"],
        "city_population_growth": rank_population_growth["city"],
        "megalopolis_population_growth": rank_population_growth["megalopolis"],
        "food_storage_population_growth_per_stored_year": parsed.food_growth_baselines[
            "local_population_growth"
        ],
        "food_storage_prosperity_gain_per_stored_year": parsed.prosperity.food_growth_monthly_prosperity,
        "food_storage_cap_in_years": parsed.growth_cap_years,
        "base_monthly_prosperity_gain": parsed.prosperity.base_monthly_prosperity,
        "global_prosperity_decay_rate": parsed.prosperity.global_prosperity_decay,
        "local_prosperity_decay_rate_at_full_prosperity": parsed.prosperity.local_prosperity_decay,
        "monthly_development_gain_at_full_prosperity": parsed.prosperity.get_effect(
            "local_monthly_development"
        ),
        "development_decay_rate_per_point": -parsed.prosperity.development_monthly_per_point,
        "monthly_development_modifier_at_full_prosperity": parsed.prosperity.get_effect(
            "local_monthly_development_modifier"
        ),
        "development_population_capacity_modifier_per_point": profile.capacity_formula.development_relative,
        "abundant_free_land_population_growth": _capacity_pressure_value(
            "abundant_free_land", "local_population_growth"
        ),
        "abundant_free_land_peasants_food_consumption": _capacity_pressure_value(
            "abundant_free_land", "local_peasants_food_consumption"
        ),
        "abundant_free_land_monthly_food": _capacity_pressure_value(
            "abundant_free_land", "local_monthly_food"
        ),
        "available_free_land_population_growth": _capacity_pressure_value(
            "available_free_land", "local_population_growth"
        ),
        "available_free_land_peasants_food_consumption": _capacity_pressure_value(
            "available_free_land", "local_peasants_food_consumption"
        ),
        "available_free_land_monthly_food": _capacity_pressure_value(
            "available_free_land", "local_monthly_food"
        ),
        "overpopulation_population_growth": _capacity_pressure_value(
            "overpopulation", "local_population_growth"
        ),
        "overpopulation_peasants_food_consumption": _capacity_pressure_value(
            "overpopulation", "local_peasants_food_consumption"
        ),
        "overpopulation_monthly_food": _capacity_pressure_value(
            "overpopulation", "local_monthly_food"
        ),
        "subsistence_agriculture": parsed.subsistence_agriculture,
        "nobles_base_food_consumption": parsed.pop_food_rates["nobles"],
        "clergy_base_food_consumption": parsed.pop_food_rates["clergy"],
        "burghers_base_food_consumption": parsed.pop_food_rates["burghers"],
        "soldiers_base_food_consumption": parsed.pop_food_rates["soldiers"],
        "laborers_base_food_consumption": parsed.pop_food_rates["laborers"],
        "peasants_base_food_consumption": parsed.pop_food_rates["peasants"],
        "slaves_base_food_consumption": parsed.pop_food_rates["slaves"],
        "tribesmen_base_food_consumption": parsed.pop_food_rates["tribesmen"],
    }
    return parsed, parsed_constants, profile, repo, starting_locations


@app.cell(hide_code=True)
def _(mo, parsed_constants):
    def _number(parsed_name, step):
        return mo.ui.number(
            step=step,
            value=parsed_constants[parsed_name],
            full_width=True,
        )

    rural_population_growth_input = _number(
        "rural_settlement_population_growth", 0.001
    )
    town_population_growth_input = _number("town_population_growth", 0.001)
    city_population_growth_input = _number("city_population_growth", 0.001)
    megalopolis_population_growth_input = _number(
        "megalopolis_population_growth", 0.001
    )
    food_storage_population_growth_input = _number(
        "food_storage_population_growth_per_stored_year", 0.0005
    )
    food_storage_prosperity_gain_input = _number(
        "food_storage_prosperity_gain_per_stored_year", 0.0005
    )
    food_storage_cap_input = _number("food_storage_cap_in_years", 0.25)
    base_monthly_prosperity_gain_input = _number(
        "base_monthly_prosperity_gain", 0.0005
    )
    global_prosperity_decay_rate_input = _number(
        "global_prosperity_decay_rate", 0.001
    )
    local_prosperity_decay_rate_input = _number(
        "local_prosperity_decay_rate_at_full_prosperity", 0.001
    )
    monthly_development_gain_input = _number(
        "monthly_development_gain_at_full_prosperity", 0.001
    )
    development_decay_rate_input = _number(
        "development_decay_rate_per_point", 0.00001
    )
    monthly_development_modifier_input = _number(
        "monthly_development_modifier_at_full_prosperity", 0.01
    )
    development_population_capacity_modifier_input = _number(
        "development_population_capacity_modifier_per_point", 0.005
    )
    abundant_free_land_population_growth_input = _number(
        "abundant_free_land_population_growth", 0.001
    )
    abundant_free_land_peasants_food_consumption_input = _number(
        "abundant_free_land_peasants_food_consumption", 0.01
    )
    abundant_free_land_monthly_food_input = _number(
        "abundant_free_land_monthly_food", 0.1
    )
    available_free_land_population_growth_input = _number(
        "available_free_land_population_growth", 0.001
    )
    available_free_land_peasants_food_consumption_input = _number(
        "available_free_land_peasants_food_consumption", 0.01
    )
    available_free_land_monthly_food_input = _number(
        "available_free_land_monthly_food", 0.1
    )
    overpopulation_population_growth_input = _number(
        "overpopulation_population_growth", 0.001
    )
    overpopulation_peasants_food_consumption_input = _number(
        "overpopulation_peasants_food_consumption", 0.01
    )
    overpopulation_monthly_food_input = _number(
        "overpopulation_monthly_food", 0.1
    )
    subsistence_agriculture_input = _number("subsistence_agriculture", 0.1)
    nobles_food_consumption_input = _number(
        "nobles_base_food_consumption", 0.1
    )
    clergy_food_consumption_input = _number(
        "clergy_base_food_consumption", 0.1
    )
    burghers_food_consumption_input = _number(
        "burghers_base_food_consumption", 0.1
    )
    soldiers_food_consumption_input = _number(
        "soldiers_base_food_consumption", 0.1
    )
    laborers_food_consumption_input = _number(
        "laborers_base_food_consumption", 0.1
    )
    peasants_food_consumption_input = _number(
        "peasants_base_food_consumption", 0.1
    )
    slaves_food_consumption_input = _number(
        "slaves_base_food_consumption", 0.1
    )
    tribesmen_food_consumption_input = _number(
        "tribesmen_base_food_consumption", 0.1
    )
    simulation_years_input = mo.ui.number(
        start=0,
        stop=10_000,
        step=25,
        value=100,
        full_width=True,
    )

    def _parameter_row(name, parsed_name, control):
        return mo.hstack(
            [
                mo.md(name),
                mo.md(f"`{parsed_constants[parsed_name]:g}`"),
                mo.md("{" + parsed_name + "}"),
            ],
            align="center",
            justify="start",
            gap=0.5,
            widths=[4, 1, 1.5],
        )

    def _parameter_group(title, rows):
        return mo.vstack(
            [mo.md(f"#### {title}"), *rows],
            gap=0.05,
        )

    parameter_layout = mo.vstack(
        [
            mo.hstack(
                [mo.md("**Parameter**"), mo.md("**Parsed**"), mo.md("**Value**")],
                align="center",
                justify="start",
                gap=0.5,
                widths=[4, 1, 1.5],
            ),
            _parameter_group(
                "Base population growth by location rank",
                [
                    _parameter_row(
                        "Rural settlement",
                        "rural_settlement_population_growth",
                        rural_population_growth_input,
                    ),
                    _parameter_row(
                        "Town",
                        "town_population_growth",
                        town_population_growth_input,
                    ),
                    _parameter_row(
                        "City",
                        "city_population_growth",
                        city_population_growth_input,
                    ),
                    _parameter_row(
                        "Megalopolis",
                        "megalopolis_population_growth",
                        megalopolis_population_growth_input,
                    ),
                    mo.md(
                        "Tribesmen currently ignore negative rank growth; other pop types use it."
                    ),
                ],
            ),
            _parameter_group(
                "Stored food",
                [
                    _parameter_row(
                        "Population growth per stored year",
                        "food_storage_population_growth_per_stored_year",
                        food_storage_population_growth_input,
                    ),
                    _parameter_row(
                        "Monthly prosperity gain per stored year",
                        "food_storage_prosperity_gain_per_stored_year",
                        food_storage_prosperity_gain_input,
                    ),
                    _parameter_row(
                        "Maximum stored years counted",
                        "food_storage_cap_in_years",
                        food_storage_cap_input,
                    ),
                ],
            ),
            _parameter_group(
                "Prosperity",
                [
                    _parameter_row(
                        "Base monthly gain",
                        "base_monthly_prosperity_gain",
                        base_monthly_prosperity_gain_input,
                    ),
                    _parameter_row(
                        "Global decay",
                        "global_prosperity_decay_rate",
                        global_prosperity_decay_rate_input,
                    ),
                    _parameter_row(
                        "Local decay at 100 prosperity",
                        "local_prosperity_decay_rate_at_full_prosperity",
                        local_prosperity_decay_rate_input,
                    ),
                ],
            ),
            _parameter_group(
                "Development",
                [
                    _parameter_row(
                        "Monthly gain at 100 prosperity",
                        "monthly_development_gain_at_full_prosperity",
                        monthly_development_gain_input,
                    ),
                    _parameter_row(
                        "Decay per development point",
                        "development_decay_rate_per_point",
                        development_decay_rate_input,
                    ),
                    _parameter_row(
                        "Monthly modifier at 100 prosperity",
                        "monthly_development_modifier_at_full_prosperity",
                        monthly_development_modifier_input,
                    ),
                ],
            ),
            _parameter_group(
                "Development to population capacity",
                [
                    _parameter_row(
                        "Capacity modifier per development point",
                        "development_population_capacity_modifier_per_point",
                        development_population_capacity_modifier_input,
                    ),
                ],
            ),
            _parameter_group(
                "Abundant free land",
                [
                    _parameter_row(
                        "Yearly population growth",
                        "abundant_free_land_population_growth",
                        abundant_free_land_population_growth_input,
                    ),
                    _parameter_row(
                        "Peasants food-consumption modifier",
                        "abundant_free_land_peasants_food_consumption",
                        abundant_free_land_peasants_food_consumption_input,
                    ),
                    _parameter_row(
                        "Absolute monthly food",
                        "abundant_free_land_monthly_food",
                        abundant_free_land_monthly_food_input,
                    ),
                ],
            ),
            _parameter_group(
                "Available free land",
                [
                    _parameter_row(
                        "Yearly population growth",
                        "available_free_land_population_growth",
                        available_free_land_population_growth_input,
                    ),
                    _parameter_row(
                        "Peasants food-consumption modifier",
                        "available_free_land_peasants_food_consumption",
                        available_free_land_peasants_food_consumption_input,
                    ),
                    _parameter_row(
                        "Absolute monthly food",
                        "available_free_land_monthly_food",
                        available_free_land_monthly_food_input,
                    ),
                ],
            ),
            _parameter_group(
                "Overpopulation",
                [
                    _parameter_row(
                        "Yearly population growth",
                        "overpopulation_population_growth",
                        overpopulation_population_growth_input,
                    ),
                    _parameter_row(
                        "Peasants food-consumption modifier",
                        "overpopulation_peasants_food_consumption",
                        overpopulation_peasants_food_consumption_input,
                    ),
                    _parameter_row(
                        "Absolute monthly food",
                        "overpopulation_monthly_food",
                        overpopulation_monthly_food_input,
                    ),
                ],
            ),
            _parameter_group(
                "Subsistence",
                [
                    _parameter_row(
                        "Subsistence agriculture output",
                        "subsistence_agriculture",
                        subsistence_agriculture_input,
                    ),
                ],
            ),
            _parameter_group(
                "Base food consumption",
                [
                    _parameter_row(
                        "Nobles",
                        "nobles_base_food_consumption",
                        nobles_food_consumption_input,
                    ),
                    _parameter_row(
                        "Clergy",
                        "clergy_base_food_consumption",
                        clergy_food_consumption_input,
                    ),
                    _parameter_row(
                        "Burghers",
                        "burghers_base_food_consumption",
                        burghers_food_consumption_input,
                    ),
                    _parameter_row(
                        "Soldiers",
                        "soldiers_base_food_consumption",
                        soldiers_food_consumption_input,
                    ),
                    _parameter_row(
                        "Laborers",
                        "laborers_base_food_consumption",
                        laborers_food_consumption_input,
                    ),
                    _parameter_row(
                        "Peasants",
                        "peasants_base_food_consumption",
                        peasants_food_consumption_input,
                    ),
                    _parameter_row(
                        "Slaves",
                        "slaves_base_food_consumption",
                        slaves_food_consumption_input,
                    ),
                    _parameter_row(
                        "Tribesmen",
                        "tribesmen_base_food_consumption",
                        tribesmen_food_consumption_input,
                    ),
                ],
            ),
            mo.md("#### Global simulation"),
            mo.hstack(
                [
                    mo.md("Years to simulate (0 = starting conditions)"),
                    mo.md(""),
                    mo.md("{simulation_years}"),
                ],
                align="center",
                justify="start",
                gap=0.5,
                widths=[4, 1, 1.5],
            ),
        ],
        gap=0.5,
    )
    simulation_form = parameter_layout.batch(
        rural_settlement_population_growth=rural_population_growth_input,
        town_population_growth=town_population_growth_input,
        city_population_growth=city_population_growth_input,
        megalopolis_population_growth=megalopolis_population_growth_input,
        food_storage_population_growth_per_stored_year=food_storage_population_growth_input,
        food_storage_prosperity_gain_per_stored_year=food_storage_prosperity_gain_input,
        food_storage_cap_in_years=food_storage_cap_input,
        base_monthly_prosperity_gain=base_monthly_prosperity_gain_input,
        global_prosperity_decay_rate=global_prosperity_decay_rate_input,
        local_prosperity_decay_rate_at_full_prosperity=local_prosperity_decay_rate_input,
        monthly_development_gain_at_full_prosperity=monthly_development_gain_input,
        development_decay_rate_per_point=development_decay_rate_input,
        monthly_development_modifier_at_full_prosperity=monthly_development_modifier_input,
        development_population_capacity_modifier_per_point=development_population_capacity_modifier_input,
        abundant_free_land_population_growth=abundant_free_land_population_growth_input,
        abundant_free_land_peasants_food_consumption=abundant_free_land_peasants_food_consumption_input,
        abundant_free_land_monthly_food=abundant_free_land_monthly_food_input,
        available_free_land_population_growth=available_free_land_population_growth_input,
        available_free_land_peasants_food_consumption=available_free_land_peasants_food_consumption_input,
        available_free_land_monthly_food=available_free_land_monthly_food_input,
        overpopulation_population_growth=overpopulation_population_growth_input,
        overpopulation_peasants_food_consumption=overpopulation_peasants_food_consumption_input,
        overpopulation_monthly_food=overpopulation_monthly_food_input,
        subsistence_agriculture=subsistence_agriculture_input,
        nobles_base_food_consumption=nobles_food_consumption_input,
        clergy_base_food_consumption=clergy_food_consumption_input,
        burghers_base_food_consumption=burghers_food_consumption_input,
        soldiers_base_food_consumption=soldiers_food_consumption_input,
        laborers_base_food_consumption=laborers_food_consumption_input,
        peasants_base_food_consumption=peasants_food_consumption_input,
        slaves_base_food_consumption=slaves_food_consumption_input,
        tribesmen_base_food_consumption=tribesmen_food_consumption_input,
        simulation_years=simulation_years_input,
    ).form(
        submit_button_label="Run global simulation",
        clear_on_submit=False,
    )
    simulation_form
    return (simulation_form,)


@app.cell(hide_code=True)
def _(parsed, parsed_constants, pl, replace, simulation_form):
    parameter_values = simulation_form.value or parsed_constants
    rank_growth = {
        "rural_settlement": parameter_values["rural_settlement_population_growth"],
        "town": parameter_values["town_population_growth"],
        "city": parameter_values["city_population_growth"],
        "megalopolis": parameter_values["megalopolis_population_growth"],
    }
    rank_growth_expression = pl.col("local_population_growth")
    for _rank, _growth in rank_growth.items():
        rank_growth_expression = (
            pl.when(pl.col("location_rank") == _rank)
            .then(pl.lit(float(_growth)))
            .otherwise(rank_growth_expression)
        )
    simulation_rank_baselines = parsed.rank_baselines.with_columns(
        rank_growth_expression.alias("local_population_growth")
    )

    simulation_food_growth = dict(parsed.food_growth_baselines)
    simulation_food_growth["local_population_growth"] = float(
        parameter_values["food_storage_population_growth_per_stored_year"]
    )
    simulation_food_growth["local_monthly_prosperity"] = float(
        parameter_values["food_storage_prosperity_gain_per_stored_year"]
    )

    simulation_food_rates = dict(parsed.pop_food_rates)
    simulation_food_rates.update(
        {
            "nobles": float(parameter_values["nobles_base_food_consumption"]),
            "clergy": float(parameter_values["clergy_base_food_consumption"]),
            "burghers": float(parameter_values["burghers_base_food_consumption"]),
            "soldiers": float(parameter_values["soldiers_base_food_consumption"]),
            "laborers": float(parameter_values["laborers_base_food_consumption"]),
            "peasants": float(parameter_values["peasants_base_food_consumption"]),
            "slaves": float(parameter_values["slaves_base_food_consumption"]),
            "tribesmen": float(parameter_values["tribesmen_base_food_consumption"]),
        }
    )

    simulation_prosperity_effects = dict(parsed.prosperity.effects)
    simulation_prosperity_effects.update(
        {
            "local_monthly_development": float(
                parameter_values["monthly_development_gain_at_full_prosperity"]
            ),
            "local_monthly_development_modifier": float(
                parameter_values["monthly_development_modifier_at_full_prosperity"]
            ),
        }
    )
    simulation_prosperity = replace(
        parsed.prosperity,
        base_monthly_prosperity=float(
            parameter_values["base_monthly_prosperity_gain"]
        ),
        food_growth_monthly_prosperity=float(
            parameter_values["food_storage_prosperity_gain_per_stored_year"]
        ),
        global_prosperity_decay=float(
            parameter_values["global_prosperity_decay_rate"]
        ),
        local_prosperity_decay=float(
            parameter_values["local_prosperity_decay_rate_at_full_prosperity"]
        ),
        effects=simulation_prosperity_effects,
        development_monthly_per_point=-float(
            parameter_values["development_decay_rate_per_point"]
        ),
    )
    simulation_capacity = replace(
        parsed.capacity_model,
        development_relative=float(
            parameter_values[
                "development_population_capacity_modifier_per_point"
            ]
        ),
    )
    simulation_capacity_pressure = {}
    for _band in (
        "abundant_free_land",
        "available_free_land",
        "overpopulation",
    ):
        _effects = dict(parsed.capacity_pressure[_band].effects)
        _effects.update(
            {
                "local_population_growth": float(
                    parameter_values[f"{_band}_population_growth"]
                ),
                "local_peasants_food_consumption": float(
                    parameter_values[f"{_band}_peasants_food_consumption"]
                ),
                "local_monthly_food": float(
                    parameter_values[f"{_band}_monthly_food"]
                ),
            }
        )
        simulation_capacity_pressure[_band] = replace(
            parsed.capacity_pressure[_band],
            effects=_effects,
        )
    simulation_context = replace(
        parsed,
        pop_food_rates=simulation_food_rates,
        growth_cap_years=float(parameter_values["food_storage_cap_in_years"]),
        food_growth_baselines=simulation_food_growth,
        rank_baselines=simulation_rank_baselines,
        capacity_pressure=simulation_capacity_pressure,
        subsistence_agriculture=float(parameter_values["subsistence_agriculture"]),
        prosperity=simulation_prosperity,
        capacity_model=simulation_capacity,
    )
    return parameter_values, simulation_context


@app.cell(hide_code=True)
def _(mo):
    get_simulation_result, set_simulation_result = mo.state(None)
    return get_simulation_result, set_simulation_result


@app.cell(hide_code=True)
def _(
    Simulation,
    parameter_values,
    perf_counter,
    set_simulation_result,
    simulation_context,
    simulation_form,
    starting_locations,
):
    if simulation_form.value is not None:
        _years = int(parameter_values["simulation_years"])
        _months = _years * 12
        _started = perf_counter()
        _simulation = Simulation(starting_locations, simulation_context)
        if _months == 0:
            _display_state = _simulation.state.clone()
            _food_change_from_state = _display_state
            _simulation.run(1, progress=False)
            _food_change_to_state = _simulation.state
        else:
            _simulation.run(_months - 1, progress=False)
            _food_change_from_state = _simulation.state.clone()
            _simulation.run(1, progress=False)
            _display_state = _simulation.state
            _food_change_to_state = _display_state
        set_simulation_result(
            {
                "state": _display_state,
                "food_change_from_state": _food_change_from_state,
                "food_change_to_state": _food_change_to_state,
                "years": _years,
                "elapsed_seconds": perf_counter() - _started,
            }
        )
    return


@app.cell(hide_code=True)
def _(
    Simulation,
    get_simulation_result,
    mo,
    prepare_simulation_analysis_state,
    simulation_context,
    starting_locations,
):
    simulation_result = get_simulation_result()
    _current_locations = (
        simulation_result["state"]
        if simulation_result is not None
        else Simulation(starting_locations, simulation_context).state
    )
    displayed_locations = prepare_simulation_analysis_state(
        starting_locations,
        _current_locations,
        food_change_from_locations=(
            simulation_result["food_change_from_state"]
            if simulation_result is not None
            else None
        ),
        food_change_to_locations=(
            simulation_result["food_change_to_state"]
            if simulation_result is not None
            else None
        ),
    )
    _start_population = float(starting_locations["total_population"].sum())
    _end_population = float(displayed_locations["total_population"].sum())
    _start_development = float(starting_locations["development"].mean())
    _end_development = float(displayed_locations["development"].mean())

    if simulation_result is None:
        simulation_summary = mo.callout(
            mo.md(
                "No simulation has been run yet. The lookup below is showing the 1337 starting state."
            ),
            kind="info",
        )
    else:
        simulation_summary = mo.callout(
            mo.md(
                f"""
    **Latest global run:** {simulation_result['years']:,} years in {simulation_result['elapsed_seconds']:.2f} seconds

    **Population:** {_start_population:,.1f} → {_end_population:,.1f} ({_end_population / _start_population:.3f}×)

    **Mean development:** {_start_development:.2f} → {_end_development:.2f}
    """
            ),
            kind="success",
        )
    simulation_summary
    return displayed_locations, simulation_result


@app.cell(hide_code=True)
def _(mo):
    def hierarchy_dropdown(values, preferred, label):
        ordered_values = sorted(values)
        options = {
            value.replace("_", " ").title(): value
            for value in ordered_values
        }
        selected = preferred if preferred in ordered_values else ordered_values[0]
        selected_label = next(
            option_label
            for option_label, value in options.items()
            if value == selected
        )
        return mo.ui.dropdown(
            options=options,
            value=selected_label,
            searchable=True,
            label=label,
            full_width=True,
        )

    return (hierarchy_dropdown,)


@app.cell(hide_code=True)
def _(hierarchy_dropdown, starting_locations):
    super_region_selector = hierarchy_dropdown(
        starting_locations["super_region"].drop_nulls().unique().to_list(),
        "europe",
        "Super-region",
    )
    return (super_region_selector,)


@app.cell(hide_code=True)
def _(hierarchy_dropdown, pl, starting_locations, super_region_selector):
    macro_region_values = (
        starting_locations.filter(
            pl.col("super_region") == super_region_selector.value
        )["macro_region"]
        .drop_nulls()
        .unique()
        .to_list()
    )
    macro_region_selector = hierarchy_dropdown(
        macro_region_values,
        "western_europe",
        "Macro-region",
    )
    return (macro_region_selector,)


@app.cell(hide_code=True)
def _(
    hierarchy_dropdown,
    macro_region_selector,
    pl,
    starting_locations,
    super_region_selector,
):
    region_values = (
        starting_locations.filter(
            (pl.col("super_region") == super_region_selector.value)
            & (pl.col("macro_region") == macro_region_selector.value)
        )["region"]
        .drop_nulls()
        .unique()
        .to_list()
    )
    region_selector = hierarchy_dropdown(
        region_values,
        "north_german_region",
        "Region",
    )
    return (region_selector,)


@app.cell(hide_code=True)
def _(
    hierarchy_dropdown,
    macro_region_selector,
    pl,
    region_selector,
    starting_locations,
    super_region_selector,
):
    area_values = (
        starting_locations.filter(
            (pl.col("super_region") == super_region_selector.value)
            & (pl.col("macro_region") == macro_region_selector.value)
            & (pl.col("region") == region_selector.value)
        )["area"]
        .drop_nulls()
        .unique()
        .to_list()
    )
    area_selector = hierarchy_dropdown(
        area_values,
        "lower_saxony_area",
        "Area",
    )
    return (area_selector,)


@app.cell(hide_code=True)
def _(
    area_selector,
    hierarchy_dropdown,
    macro_region_selector,
    pl,
    region_selector,
    starting_locations,
    super_region_selector,
):
    province_values = (
        starting_locations.filter(
            (pl.col("super_region") == super_region_selector.value)
            & (pl.col("macro_region") == macro_region_selector.value)
            & (pl.col("region") == region_selector.value)
            & (pl.col("area") == area_selector.value)
        )["province"]
        .drop_nulls()
        .unique()
        .to_list()
    )
    province_selector = hierarchy_dropdown(
        province_values,
        "luneburger_heide_province",
        "Province",
    )
    return (province_selector,)


@app.cell(hide_code=True)
def _(
    area_selector,
    macro_region_selector,
    mo,
    province_selector,
    region_selector,
    super_region_selector,
):
    mo.vstack(
        [
            mo.md("## Location attributes"),
            mo.hstack(
                [super_region_selector, macro_region_selector],
                widths="equal",
                gap=0.5,
            ),
            mo.hstack(
                [region_selector, area_selector, province_selector],
                widths="equal",
                gap=0.5,
            ),
        ],
        gap=0.35,
    )
    return


@app.cell(hide_code=True)
def _(displayed_locations, mo, pl, province_selector, simulation_result):
    population_columns = [
        "population_nobles",
        "population_clergy",
        "population_burghers",
        "population_soldiers",
        "population_laborers",
        "population_peasants",
        "population_slaves",
        "population_tribesmen",
    ]
    selected_state = displayed_locations.filter(
        pl.col("province") == province_selector.value
    )
    selected_locations = (
        selected_state
        .select(
            [
                "location_tag",
                "location_rank",
                "irrigation_systems_levels",
                "starting_development",
                "development",
                "development_change",
                "prosperity",
                "population_capacity",
                "capacity_fill",
                "starting_population",
                "total_population",
                "population_change",
                *population_columns,
            ]
        )
        .sort("location_tag")
        .rename(
            {
                "location_tag": "Location",
                "location_rank": "Rank",
                "irrigation_systems_levels": "Irrigation systems",
                "development": "Simulated development",
                "starting_development": "Starting development",
                "development_change": "Development change",
                "prosperity": "Prosperity",
                "population_capacity": "Population capacity",
                "capacity_fill": "Capacity fill",
                "total_population": "Simulated population",
                "starting_population": "Starting population",
                "population_change": "Population change",
                "population_nobles": "Nobles",
                "population_clergy": "Clergy",
                "population_burghers": "Burghers",
                "population_soldiers": "Soldiers",
                "population_laborers": "Laborers",
                "population_peasants": "Peasants",
                "population_slaves": "Slaves",
                "population_tribesmen": "Tribesmen",
            }
        )
    )

    def _two_decimals(value):
        return "" if value is None else f"{float(value):,.2f}"

    location_table = mo.ui.table(
        selected_locations,
        selection=None,
        pagination=False,
        show_column_summaries=False,
        show_data_types=False,
        show_search=False,
        show_download=False,
        freeze_columns_left=["Location"],
        format_mapping={
            "Irrigation systems": lambda value: (
                "" if value is None else f"{int(value)}"
            ),
            "Simulated development": _two_decimals,
            "Starting development": _two_decimals,
            "Development change": _two_decimals,
            "Prosperity": _two_decimals,
            "Population capacity": _two_decimals,
            "Capacity fill": lambda value: (
                "" if value is None else f"{float(value):.1%}"
            ),
            "Simulated population": _two_decimals,
            "Starting population": _two_decimals,
            "Population change": _two_decimals,
            "Nobles": _two_decimals,
            "Clergy": _two_decimals,
            "Burghers": _two_decimals,
            "Soldiers": _two_decimals,
            "Laborers": _two_decimals,
            "Peasants": _two_decimals,
            "Slaves": _two_decimals,
            "Tribesmen": _two_decimals,
        },
        column_widths={
            "Location": 150,
            "Rank": 120,
            "Population capacity": 170,
        },
        max_height=500,
    )
    mo.vstack(
        [
            mo.md(
                "## Simulated location results"
                if simulation_result is not None
                else "## Starting location values"
            ),
            mo.md(
                f"Showing the global simulation after {simulation_result['years']:,} years."
                if simulation_result is not None
                else "Run the global simulation above to replace these starting values with simulated results."
            ),
            location_table,
        ],
        gap=0.35,
    )
    return


@app.cell(hide_code=True)
def _(SIMULATION_METRICS, mo):
    simulation_metric_selector = mo.ui.dropdown(
        options=SIMULATION_METRICS,
        value="Total population",
        label="Simulation metric",
        full_width=True,
    )
    mo.vstack(
        [
            mo.md("## Global simulation map and macro-region statistics"),
            mo.md(
                "Choose one metric for both the map and the descriptive-statistics table."
            ),
            mo.md(
                "Province food surplus/deficit is the change in stored food over the latest month. At 0 years, it is projected one month forward from the untouched starting state."
            ),
            simulation_metric_selector,
        ],
        gap=0.35,
    )
    return (simulation_metric_selector,)


@app.cell(hide_code=True)
def _(load_map_assets, repo, simulation_metric_selector, simulation_result):
    _startup_irrigation_map = (
        simulation_metric_selector.value == "irrigation_systems_levels"
    )
    simulation_map_assets = (
        None
        if simulation_result is None and not _startup_irrigation_map
        else load_map_assets(
            repo=repo,
            project=repo / "constructor.toml",
            map_width=2400,
        )
    )
    return (simulation_map_assets,)


@app.cell(hide_code=True)
def _(
    Log1pNorm,
    Normalize,
    SIMULATION_METRICS,
    TwoSlopeNorm,
    displayed_locations,
    mo,
    np,
    plt,
    profile,
    rasterio,
    repo,
    simulation_map_assets,
    simulation_metric_selector,
    simulation_result,
    write_simulation_metric_geotiff,
):
    _metric = simulation_metric_selector.value
    _startup_irrigation_map = _metric == "irrigation_systems_levels"
    if (
        simulation_result is None
        and not _startup_irrigation_map
    ) or simulation_map_assets is None:
        simulation_map_output = mo.callout(
            mo.md(
                "Run the global simulation to generate and display this metric's GeoTIFF. "
                "The startup irrigation map is available before a simulation run."
            ),
            kind="info",
        )
    else:
        _years = (
            0
            if _startup_irrigation_map
            else int(simulation_result["years"])
        )
        _map_year = profile.start_year + _years
        _tiff_name = (
            f"startup_irrigation_systems_levels_{profile.start_year}.tif"
            if _startup_irrigation_map
            else f"{_metric}_{_map_year}.tif"
        )
        _tiff_path = (
            repo
            / "artifacts/data/population_simulation/notebook_maps"
            / _tiff_name
        )
        _tiff_result = write_simulation_metric_geotiff(
            displayed_locations,
            metric=_metric,
            assets=simulation_map_assets,
            output_path=_tiff_path,
            simulation_years=_years,
            start_year=profile.start_year,
        )
        with rasterio.open(_tiff_result.path) as _source:
            _map_values = _source.read(1, masked=True)

        _finite_values = np.asarray(
            displayed_locations[_metric].drop_nulls().to_numpy(),
            dtype=float,
        )
        _finite_values = _finite_values[np.isfinite(_finite_values)]
        _metric_label = next(
            label
            for label, value in SIMULATION_METRICS.items()
            if value == _metric
        )
        if _metric.endswith("_change"):
            _limit = max(
                float(np.quantile(np.abs(_finite_values), 0.98)),
                1e-9,
            )
            _norm = TwoSlopeNorm(vmin=-_limit, vcenter=0.0, vmax=_limit)
            _cmap = "RdYlGn"
            _scale_note = "symmetric at the 98th percentile of absolute change"
        elif _metric in {"total_population", "population_capacity"}:
            _upper = max(float(np.quantile(_finite_values, 0.98)), 1.0)
            _norm = Log1pNorm(vmin=0.0, vmax=_upper)
            _cmap = "viridis"
            _scale_note = "log1p, capped visually at the 98th percentile"
        elif _metric in {"development", "prosperity"}:
            _norm = Normalize(vmin=0.0, vmax=100.0)
            _cmap = "viridis"
            _scale_note = "linear from 0 to 100"
        elif _startup_irrigation_map:
            _upper = max(float(np.max(_finite_values)), 1.0)
            _norm = Normalize(vmin=0.0, vmax=_upper)
            _cmap = "Blues"
            _scale_note = f"linear from 0 to {_upper:g} irrigation levels"
        else:
            _upper = max(float(np.quantile(_finite_values, 0.98)), 1.0)
            _norm = Normalize(vmin=0.0, vmax=_upper)
            _cmap = "YlOrRd"
            _scale_note = "linear, capped visually at the 98th percentile"

        _figure, _axis = plt.subplots(figsize=(16, 8), constrained_layout=True)
        _image = _axis.imshow(_map_values, cmap=_cmap, norm=_norm)
        _axis.set_title(
            f"Startup irrigation systems levels ({profile.start_year})"
            if _startup_irrigation_map
            else f"{_metric_label} after {_years:,} simulated years ({_map_year})"
        )
        _axis.set_axis_off()
        _figure.colorbar(_image, ax=_axis, shrink=0.72, label=_metric_label)
        simulation_map_output = mo.vstack(
            [
                mo.md(
                    f"""
    **GeoTIFF:** `{_tiff_result.path}`

    **Coverage:** {_tiff_result.mapped_locations:,} locations / {_tiff_result.mapped_pixels:,} map pixels

    **Display scale:** {_scale_note}

        This is the same numeric single-band TIFF displayed below and opened by QGIS. It reuses the existing EU5 `locations.png` geometry and pixel mapping. Its coordinate space is EU5 game-map pixels, so no false geographic CRS is assigned.
        """
                ),
                _figure,
            ],
            gap=0.35,
        )
    simulation_map_output
    return


@app.cell(hide_code=True)
def _(
    displayed_locations,
    macro_region_statistics,
    mo,
    simulation_metric_selector,
    simulation_result,
):
    _metric = simulation_metric_selector.value
    _province_metric = _metric == "province_food_storage_change"
    _statistics = macro_region_statistics(
        displayed_locations,
        _metric,
        unit_column="province" if _province_metric else None,
    ).rename(
        {
            "macro_region": "Macro-region",
            "count": "Count",
            "min": "Min",
            "max": "Max",
            "mean": "Mean",
            "median": "Median",
            "std_dev": "Std. dev.",
            "sum": "Sum",
        }
    )

    def _format_stat(value):
        return "" if value is None else f"{float(value):,.2f}"

    _statistics_table = mo.ui.table(
        _statistics,
        selection=None,
        pagination=True,
        page_size=25,
        show_column_summaries=False,
        show_data_types=False,
        show_search=True,
        show_download=True,
        freeze_columns_left=["Macro-region"],
        format_mapping={
            "Count": lambda value: "" if value is None else f"{int(value):,}",
            "Min": _format_stat,
            "Max": _format_stat,
            "Mean": _format_stat,
            "Median": _format_stat,
            "Std. dev.": _format_stat,
            "Sum": _format_stat,
        },
        max_height=650,
    )
    mo.vstack(
        [
            mo.md("### Macro-region statistics"),
            mo.md(
                f"{'Province' if _province_metric else 'Location'}-level statistics for the latest {_metric.replace('_', ' ')} values."
                if simulation_result is not None
                else f"{'Province' if _province_metric else 'Location'}-level statistics for the 1337 {_metric.replace('_', ' ')} values."
            ),
            _statistics_table,
        ],
        gap=0.35,
    )
    return


if __name__ == "__main__":
    app.run()
