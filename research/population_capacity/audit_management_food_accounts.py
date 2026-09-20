"""Reconcile a management experiment into local food and dated-land accounts.

Uses its saved overrides and canonical food evaluator. No alternative province
boundaries, population-derived assignments or balance changes are introduced.
"""
import argparse
from pathlib import Path
import json
import numpy as np
import polars as pl
from run_historical_direct import ROOT, prepare
from prosper_or_perish_constructor.simulation.agricultural_employment import attach_slave_agriculture
from prosper_or_perish_constructor.simulation.food_diagnosis import diagnose_provincial_food
from prosper_or_perish_constructor.simulation.cache import fingerprint


def run(experiment, candidate):
    manifest_path = experiment / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    cases = [x for x in manifest['cases'] if x['candidate'] == candidate]
    if len(cases) != 1:
        raise ValueError('Select exactly one saved management candidate')
    case = cases[0]
    _, (state, context, prep) = prepare(case['overrides'])
    state = attach_slave_agriculture(state, subsistence_output=context.subsistence_agriculture, hiring_fraction=.75)
    saved_path = experiment / f'{candidate}_starting_ledger.parquet'
    saved = pl.read_parquet(saved_path)
    # The saved state is evidence only if the current preparation reproduces it.
    if not state.sort('location_tag').equals(saved.sort('location_tag')):
        raise ValueError('Saved management state is stale; rerun the experiment')
    provinces = state.filter(pl.col('location_tag').is_in(case['target_tags']))['province'].unique()
    state = state.filter(pl.col('province').is_in(provinces.to_list()))
    locations, _, budgets = diagnose_provincial_food(state, context)
    previous = pl.read_csv(experiment / 'provincial_budgets.csv').filter(pl.col('candidate') == candidate)
    metrics = ['food_production', 'food_consumption', 'food_balance', 'subsistence_surplus',
               'non_subsistence_balance_after_other_pops', 'pressure_recoverable_consumption']
    left, right = budgets.sort('province'), previous.sort('province')
    if left['province'].to_list() != right['province'].to_list() or not np.allclose(
            left.select(metrics).to_numpy(), right.select(metrics).to_numpy(), rtol=0, atol=1e-8):
        raise ValueError('Local food audit does not reproduce saved provincial budget')
    actual = locations.filter(pl.col('scenario') == 'actual')
    probe = locations.filter(pl.col('scenario') == 'negligible_pressure').select('location_tag',
        pl.col('food_consumption').alias('low_pressure_consumption'))
    selected = ['location_tag','province','total_population','local_population_capacity',
        'development','subsistence_food_production','peasant_food_consumption','food_production',
        'food_consumption','food_balance','realized_building_food','employed_peasants','unemployed_peasants']
    selected += [c for c in actual.columns if c.startswith('food_consumption__')]
    food = actual.select(selected).join(probe,on='location_tag',validate='1:1').with_columns(
        (pl.col('subsistence_food_production')-pl.col('peasant_food_consumption')).alias('subsistence_surplus'),
        (pl.col('food_consumption')-pl.col('low_pressure_consumption')).alias('pressure_recoverable_consumption'))
    land = state.select('location_tag','province','area_km2','crop_fallow_block_km2',
        'baseline_open_cultivation_km2','water_managed_fields_km2','development',
        (pl.col('area_km2')*pl.col('cropland_fraction_1300')).alias('luh2_1300_cropland_km2'),
        'hyde_cropland_area_km2_1300','hyde_cropland_area_km2',
        'annual_crop_rainfed_people_per_field_km2_p50','annual_crop_irrigated_people_per_field_km2_p50')
    land = land.with_columns((pl.col('hyde_cropland_area_km2_1300')-
        pl.col('luh2_1300_cropland_km2')).alias('related_source_area_difference_km2'))
    output = experiment / f'{candidate}_food_audit'
    output.mkdir(exist_ok=True)
    food.write_csv(output/'local_food_accounts.csv')
    land.write_csv(output/'dated_land_comparison.csv')
    budgets.write_csv(output/'reconciled_provincial_budgets.csv')
    result = dict(accepted=False, candidate=candidate, provinces=provinces.to_list(),
        starting_state_reproduced=True, provincial_budget_reproduced=True,
        evidence_family='LUH2/HYDE; related reconstructions, not independent validation',
        years=dict(luh2=1300, comparison_hyde=1300,
                   starting_hyde={k:v['source_year'] for k,v in prep['hyde_raster_sources'].items()}),
        hyde_raster_sources=prep['hyde_raster_sources'],
        scope='Local contributions inside unchanged complete food-sharing provinces; no isolated-island simulation',
        limitations=['Land-source differences do not authorize replacing hectares',
            'Sources differ in version, spatial resolution and allocation; source labels are not field observations',
            'Low-pressure consumption is a diagnostic counterfactual, never a capacity assignment'],
        fingerprint=fingerprint([Path(__file__),manifest_path,saved_path,
            ROOT/'src/prosper_or_perish_constructor/simulation'],dict(preparation=prep,case=case)))
    (output/'manifest.json').write_text(json.dumps(result,indent=2,default=str)+'\n')
    return dict(output=str(output), **result)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment',required=True)
    parser.add_argument('--candidate',default='central')
    args=parser.parse_args()
    print(json.dumps(run(ROOT/args.experiment,args.candidate),indent=2))
