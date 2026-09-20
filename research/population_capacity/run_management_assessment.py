"""Isolate one documented management system without moving its neighbours.

Each uncertainty position is resolved into an assignment file before canonical
preparation. No population-derived assignment or acceptance threshold is used.
"""
import argparse
from dataclasses import asdict, replace
import json

import numpy as np
import polars as pl

from run_historical_direct import ROOT, prepare
from run_acceptance_round_25 import OVERRIDES
from prosper_or_perish_constructor.simulation.agricultural_employment import attach_slave_agriculture
from prosper_or_perish_constructor.simulation.behavior_acceptance import evaluate_trajectory
from prosper_or_perish_constructor.simulation.cache import fingerprint
from prosper_or_perish_constructor.simulation.food_diagnosis import diagnose_provincial_food
from prosper_or_perish_constructor.simulation.historical_scenarios import HistoricalScenario, run_historical_scenario


def run(assignments, system_id, output, *, extra_overrides=(), native_scenario=None):
    document = json.loads(assignments.read_text())
    matching = [s for s in document['systems'] if s['id'] == system_id]
    if len(matching) != 1:
        raise ValueError('exactly one named system is required')
    system = matching[0]
    output.mkdir(parents=True, exist_ok=True)
    cases = []; criteria = []; budgets = []; reference = None
    for name, quantile in [('unchanged', None), ('low', 0.), ('central', .5), ('high', 1.)]:
        resolved = json.loads(json.dumps(document))
        if quantile is None:
            resolved['systems'] = [s for s in resolved['systems'] if s['id'] != system_id]
        else:
            target = next(s for s in resolved['systems'] if s['id'] == system_id)
            for key in ('development_range', 'water_served_fraction_range',
                        'cultivated_fraction_range', 'cultivated_area_km2_range',
                        'missing_rainfed_support_at_reference_development_people_per_km2_range'):
                if key in target:
                    low, high = target[key]
                    value = low + quantile * (high-low)
                    target[key] = [value, value]
        path = output / f'{name}_assignments.json'
        if 'source_hashes' in resolved:
            resolved['source_hashes'] = {
                str((assignments.parent / key).resolve()): value
                for key, value in resolved['source_hashes'].items()}
        path.write_text(json.dumps(resolved, indent=2)+'\n')
        overrides = (*OVERRIDES,
            f'paths.historical_assignments="{path.relative_to(ROOT).as_posix()}"',
            'capacity.gaez_zero_development_fraction=3.0',
            'capacity.location_area_exponent=0.75',
            'capacity.urban_allowance_per_observed_worker=3.0', *extra_overrides)
        _, (state, context, prep) = prepare(overrides)
        state = attach_slave_agriculture(state, subsistence_output=context.subsistence_agriculture, hiring_fraction=.75)
        selected = pl.lit(True)
        for key, values in system['selector'].items():
            selected &= pl.col(key).is_in(values)
        for key, value in system.get('requires', {}).items():
            selected &= pl.col(key) == value
        target_tags = state.filter(selected)['location_tag'].to_list()
        if not target_tags:
            raise ValueError('system does not select any locations')
        provinces = state.filter(selected)['province'].unique().to_list()
        fields = ['location_tag', 'development', 'local_population_capacity', 'crop_fallow_block_km2',
                  'water_managed_fields_km2', 'building_food_output', 'total_population']
        snapshot = state.select(fields).sort('location_tag')
        if reference is None:
            reference = snapshot
        # Even source-adjacent countries and locations must not move in an
        # isolated uncertainty comparison. The full world start is checked.
        unchanged = ~pl.col('location_tag').is_in(target_tags)
        assert snapshot.filter(unchanged).equals(reference.filter(unchanged)), 'neighbouring assignments moved'
        assert snapshot.select('location_tag', 'building_food_output', 'total_population').equals(
            reference.select('location_tag', 'building_food_output', 'total_population'))
        if not any(k in system for k in ('cultivated_area_km2_range', 'cultivated_fraction_range',
                                         'recover_dated_cropland', 'recover_dated_irrigated_cropland')):
            assert np.array_equal(snapshot['crop_fallow_block_km2'].to_numpy(), reference['crop_fallow_block_km2'].to_numpy())
        state.write_parquet(output / f'{name}_starting_ledger.parquet')
        regional = state.filter(pl.col('province').is_in(provinces))
        _, _, budget = diagnose_provincial_food(regional, context)
        budgets.append(budget.with_columns(pl.lit(name).alias('candidate')))
        scenario = replace(native_scenario, name=name) if native_scenario else HistoricalScenario(name, remaining_urban_rank_penalty=0.)
        history, numerical = run_historical_scenario(regional, context, scenario)
        history.write_parquet(output / f'{name}_monthly.parquet')
        for province in provinces:
            result = evaluate_trajectory(history.filter(pl.col('province')==province), provisioned=True)
            for row in result['horizons']:
                passed = all(c['passed'] for c in result['checks'] if c.get('horizon', row['year'])==row['year'])
                criteria.append(dict(candidate=name, province=province, **row, viability='passed' if passed else 'failed'))
        cases.append(dict(candidate=name, quantile=quantile, overrides=overrides,
                          scenario=asdict(scenario), preparation=prep, numerical=numerical,
                          target_tags=target_tags, neighbours_unchanged=True))
        print('Finished isolated management assessment', name, flush=True)
    pl.DataFrame(criteria).write_csv(output / 'viability_criteria.csv')
    pl.concat(budgets, how='diagonal_relaxed').write_csv(output / 'provincial_budgets.csv')
    source_paths = [ROOT/'research/population_capacity'/s for s in system['source_ids']]
    identity = fingerprint([__file__, assignments, *source_paths, ROOT/'src/prosper_or_perish_constructor/simulation'],
                           dict(cases=cases, required_horizons=[100, 200]))
    (output/'manifest.json').write_text(json.dumps(dict(accepted=False, fingerprint=identity,
        system=system, cases=cases, contract='Isolated evidence uncertainty at unchanged neighbouring assignments; all building food and population-type consumption unchanged.'), indent=2, default=str)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assignments', required=True)
    parser.add_argument('--system', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--override', action='append', default=[])
    parser.add_argument('--scenario-file')
    parser.add_argument('--scenario')
    args = parser.parse_args()
    if bool(args.scenario_file) != bool(args.scenario):
        parser.error('--scenario-file and --scenario must be provided together')
    scenario = None
    if args.scenario_file:
        selected = [x for x in json.loads((ROOT/args.scenario_file).read_text())['scenarios'] if x['name']==args.scenario]
        if len(selected)!=1:
            parser.error('Select exactly one named scenario')
        scenario = HistoricalScenario(**selected[0])
    run(ROOT/args.assignments, args.system, ROOT/args.output, extra_overrides=args.override, native_scenario=scenario)
