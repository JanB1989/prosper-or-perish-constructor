"""Frozen-development and native land-pressure retention comparisons, round 25."""
from dataclasses import asdict, replace
import json
import argparse

import polars as pl

from run_historical_direct import ROOT, prepare
from run_acceptance_round_25 import OVERRIDES, TAGS
from prosper_or_perish_constructor.simulation.agricultural_employment import attach_slave_agriculture
from prosper_or_perish_constructor.simulation.cache import fingerprint
from prosper_or_perish_constructor.simulation.capacity_pressure import ABUNDANT_FREE_LAND, AVAILABLE_FREE_LAND, CapacityPressureBand
from prosper_or_perish_constructor.simulation.development import FLAT, decay_offset
from prosper_or_perish_constructor.simulation.historical_scenarios import HistoricalScenario, run_historical_scenario
from prosper_or_perish_constructor.simulation.behavior_acceptance import evaluate_trajectory


def run(overrides=OVERRIDES, *, output=None, remaining_urban_rank_penalty=1., include_frozen=True):
    _, (state, context, prep) = prepare(overrides)
    state = attach_slave_agriculture(state, subsistence_output=context.subsistence_agriculture, hiring_fraction=.75)
    provinces = state.filter(pl.col('location_tag').is_in(TAGS))['province'].unique().to_list()
    state = state.filter(pl.col('province').is_in(provinces))
    out = output or ROOT / 'artifacts/data/population_simulation/repair_round_25/retention_comparisons'
    out.mkdir(parents=True, exist_ok=True)
    plans = [(HistoricalScenario(f'frozen_stock_{stock}', stock_months=stock, frozen_development=True), 0.) for stock in (0,3,12,24)] if include_frozen else []
    plans += [(HistoricalScenario(f'pressure_offset_{fraction:g}'), fraction) for fraction in (0., .25, .5)]
    plans = [(replace(spec, remaining_urban_rank_penalty=remaining_urban_rank_penalty), fraction) for spec, fraction in plans]
    identity = fingerprint([__file__, ROOT / 'src/prosper_or_perish_constructor/simulation'],
        {'preparation': prep, 'scenarios': [(asdict(spec), fraction) for spec, fraction in plans],
         'hiring_fraction': .75, 'tags': TAGS, 'required_horizons': [100, 200]})
    results = []; criteria = []
    for spec, fraction in plans:
        bonus = decay_offset(context.prosperity.development_monthly_per_point, fraction)
        bands = dict(context.capacity_pressure)
        for name in (ABUNDANT_FREE_LAND, AVAILABLE_FREE_LAND):
            bands[name] = CapacityPressureBand(name, {**bands[name].effects, FLAT: bands[name].get(FLAT) - bonus})
        initial = state.with_columns(((pl.col(FLAT) if FLAT in state.columns else pl.lit(0.)) + bonus).alias(FLAT))
        history, result = run_historical_scenario(initial, replace(context, capacity_pressure=bands), spec)
        history.write_parquet(out / f'{spec.name}.parquet')
        for province in provinces:
            check = evaluate_trajectory(history.filter(pl.col('province')==province), provisioned=True)
            for row in check['horizons']:
                passed = all(c['passed'] for c in check['checks'] if c.get('horizon', row['year'])==row['year'])
                criteria.append(dict(candidate=spec.name, province=province, **row, viability='passed' if passed else 'failed'))
        result['full_pressure_flat_offset'] = bonus
        result['scope'] = '22 diagnostic provinces; not all global beneficiaries; offset not accepted'
        results.append(result)
        print('Finished', spec.name, flush=True)
    pl.DataFrame(criteria).write_csv(out/'viability_criteria.csv')
    (out / 'results.json').write_text(json.dumps({'input_fingerprint': identity, 'preparation': prep,
        'model_accepted': False, 'required_horizons': [100, 200], 'results': results}, indent=2, default=str))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assignments')
    parser.add_argument('--output')
    parser.add_argument('--no-frozen', action='store_true')
    args = parser.parse_args()
    if args.assignments and not args.output:
        parser.error('a changed candidate requires a separate output directory')
    overrides = OVERRIDES
    if args.assignments:
        overrides = (*overrides, f'paths.historical_assignments="{args.assignments}"',
            'capacity.gaez_zero_development_fraction=3.0', 'capacity.location_area_exponent=0.75',
            'capacity.urban_allowance_per_observed_worker=3.0')
    run(overrides, output=ROOT/args.output if args.output else None,
        remaining_urban_rank_penalty=0. if args.assignments else 1., include_frozen=not args.no_frozen)
