"""Global collateral checks for one historical assignment candidate.

Use the canonical Simulation and verify its checkpoints against the separately
saved monthly provincial scenario. No historical or overall acceptance implied.
"""
import argparse
from dataclasses import asdict
import json

import numpy as np
import polars as pl

from run_historical_direct import ROOT, prepare
from run_acceptance_round_25 import OVERRIDES, TAGS
from prosper_or_perish_constructor.simulation.agricultural_employment import attach_slave_agriculture
from prosper_or_perish_constructor.simulation.cache import fingerprint
from prosper_or_perish_constructor.simulation.development import decay_offset
from prosper_or_perish_constructor.simulation.historical_scenarios import HistoricalScenario, configure_historical_scenario, run_historical_scenario
from prosper_or_perish_constructor.simulation.behavior_acceptance import evaluate_trajectory
from prosper_or_perish_constructor.simulation.food_diagnosis import diagnose_provincial_food
from prosper_or_perish_constructor.simulation.land_experiments import _totals
from prosper_or_perish_constructor.simulation.run import Simulation


def run(assignments, output, monthly_reference=None, *, scenario_file=None, regional_only=False, extra_overrides=(), additional_tags=()):
    overrides = (*OVERRIDES, f'paths.historical_assignments="{assignments}"',
                 'capacity.gaez_zero_development_fraction=3.0',
                 'capacity.location_area_exponent=0.75',
                 'capacity.urban_allowance_per_observed_worker=3.0', *extra_overrides)
    _, (state, context, preparation) = prepare(overrides)
    state = attach_slave_agriculture(state, subsistence_output=context.subsistence_agriculture, hiring_fraction=.75)
    output.mkdir(parents=True, exist_ok=True)
    state.write_parquet(output/'starting_ledger.parquet')
    _, _, budget = diagnose_provincial_food(state, context)
    budget.write_csv(output/'all_provincial_food_budgets.csv')
    plans = [HistoricalScenario('native_rank_no_offset'), HistoricalScenario('equal_rank_no_offset',remaining_urban_rank_penalty=0.),
             HistoricalScenario('equal_rank_quarter_offset',remaining_urban_rank_penalty=0.,pressure_decay_compensation=.25)]
    if scenario_file:
        document=json.loads(scenario_file.read_text())
        plans=[HistoricalScenario(**s) for s in document['scenarios']]
    if len({s.name for s in plans})!=len(plans):
        raise ValueError('scenario names must be unique')
    selected_tags=sorted(set(TAGS) | set(additional_tags))
    if set(selected_tags)-set(state['location_tag']):
        raise ValueError('Unknown diagnostic location tag')
    province_names=sorted(state.filter(pl.col('location_tag').is_in(selected_tags))['province'].unique().to_list())
    regional=state.filter(pl.col('province').is_in(province_names))
    cases = []; criteria=[]
    for spec in plans:
        name=spec.name
        initial,configured=configure_historical_scenario(state,context,spec)
        ranks=configured.rank_baselines
        bonus=decay_offset(context.prosperity.development_monthly_per_point,spec.pressure_decay_compensation)
        if monthly_reference and name=='equal_rank_quarter_offset' and not scenario_file:
            history=pl.read_parquet(monthly_reference)
        else:
            history,_=run_historical_scenario(regional,context,spec)
        history.write_parquet(output/f'{name}_monthly.parquet')
        for province in province_names:
            checked=evaluate_trajectory(history.filter(pl.col('province')==province),provisioned=True)
            for row in checked['horizons']:
                passed=all(c['passed'] for c in checked['checks'] if c.get('horizon',row['year'])==row['year'])
                criteria.append(dict(candidate=name,province=province,**row,viability='passed' if passed else 'failed'))
        reference=history.filter(pl.col('month').is_in([0,300,1200,2400]))
        ranks.write_csv(output/f'{name}_rank_configuration.csv')
        case=dict(name=name,scenario=asdict(spec),remaining_urban_penalty=spec.remaining_urban_rank_penalty,
                  common_rank_growth=spec.common_rank_growth,decay_compensation_fraction=spec.pressure_decay_compensation,
                  full_pressure_development_offset=bonus,monthly_replay=[])
        if regional_only:
            cases.append(case)
            print('Finished regional',name,flush=True)
            continue
        sim = Simulation(initial, configured)
        aggregates = []; provinces = []; checkpoints = []; replay = []
        for year in range(201):
            if year:
                sim.run(12, progress=False, materialize=False)
            sim.evaluate_food_budget()
            frame = sim.diagnostic_state()
            counters = ['starvation_months','unmet_food_months','food_growth_cap_months',
                        'population_maximum_drawdown','maximum_consecutive_starvation_months']
            absent = [key for key in counters if key not in frame.columns]
            if absent:
                assert year == 0, f'missing post-start trajectory counters: {absent}'
                # No elapsed months at the starting snapshot. This initializes
                # report counters only; no missing food/mechanics is imputed.
                frame = frame.with_columns(*[pl.lit(0.).alias(key) for key in absent])
            aggregates.append(_totals(frame,year))
            provinces.append(frame.group_by('province').agg(
                pl.col('total_population','local_population_capacity','food_production','food_consumption','food_balance',
                       'food','starvation_months','unmet_food_months','food_growth_cap_months').sum(),
                pl.col('development').mean().alias('mean_development'),
                pl.col('development').min().alias('minimum_development'),
                pl.col('population_maximum_drawdown','maximum_consecutive_starvation_months').max(),
            ).with_columns(pl.lit(year).alias('year')))
            if year in (0,25,100,200):
                checkpoints.append(frame.with_columns(pl.lit(year).alias('year')))
                if reference.height:
                    metrics = ['total_population','development','local_population_capacity','food','food_production','food_consumption']
                    expected = reference.filter(pl.col('month')==year*12).sort('location_tag')
                    actual = frame.filter(pl.col('location_tag').is_in(expected['location_tag'].to_list())).sort('location_tag')
                    assert actual['location_tag'].to_list()==expected['location_tag'].to_list()
                    for metric in metrics:
                        a,b=actual[metric].to_numpy(),expected[metric].to_numpy()
                        residual=float(np.max(np.abs(a-b)))
                        assert np.allclose(a,b,rtol=1e-10,atol=1e-8), f'monthly/world replay differs: {year} {metric}'
                        replay.append(dict(year=year,metric=metric,maximum_absolute_residual=residual))
            if year in (25,100,200):
                print(name,year,flush=True)
        pl.concat(aggregates,how='diagonal_relaxed').write_parquet(output/f'{name}_annual_scopes.parquet')
        pl.concat(provinces,how='diagonal_relaxed').write_parquet(output/f'{name}_annual_provinces.parquet')
        pl.concat(checkpoints,how='diagonal_relaxed').write_parquet(output/f'{name}_checkpoints.parquet')
        case['monthly_replay']=replay
        cases.append(case)
    pl.DataFrame(criteria).write_csv(output/'viability_criteria.csv')
    paths=[__file__, ROOT/assignments, ROOT/'src/prosper_or_perish_constructor/simulation']
    paths += [p for p in (monthly_reference,scenario_file) if p is not None]
    identity=fingerprint(paths,
                         dict(preparation=preparation,overrides=overrides,cases=cases,horizons=[100,200],regional_provinces=province_names))
    (output/'manifest.json').write_text(json.dumps(dict(model_accepted=False,fingerprint=identity,
        preparation=preparation,overrides=overrides,cases=cases,regional_only=regional_only,
        regional_provinces=province_names,diagnostic_tags=selected_tags,
        contract='Identical geographical candidate, starting populations, jobs, food production and consumption. Native growth and partial pressure retention use canonical scenario configuration. Regional scope: explicit complete provinces listed in this manifest. World runs include every location and verify every scenario against monthly provincial checkpoints.'),indent=2,default=str)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--assignments',required=True)
    p.add_argument('--output',required=True)
    p.add_argument('--monthly-reference')
    p.add_argument('--scenario-file')
    p.add_argument('--regional-only',action='store_true')
    p.add_argument('--override',action='append',default=[])
    p.add_argument('--additional-tag',action='append',default=[])
    args=p.parse_args()
    run(args.assignments, ROOT/args.output, ROOT/args.monthly_reference if args.monthly_reference else None,
        scenario_file=ROOT/args.scenario_file if args.scenario_file else None,regional_only=args.regional_only,extra_overrides=args.override,additional_tags=args.additional_tag)
