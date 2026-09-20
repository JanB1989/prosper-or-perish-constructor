"""One candidate and reproducible monthly evidence; no game export.

Run with uv run python research/population_capacity/run_acceptance_round_25.py.
Unresolved historical coverage remains explicit rather than manufactured passes.
"""
from dataclasses import asdict, replace
import argparse
import json

import numpy as np
import polars as pl

from run_historical_direct import ROOT, prepare
from prosper_or_perish_constructor.simulation.agricultural_employment import attach_slave_agriculture
from prosper_or_perish_constructor.simulation.behavior_acceptance import (
    compare_recovery, evaluate_trajectory, write_evaluated_evidence)
from prosper_or_perish_constructor.simulation.cache import fingerprint
from prosper_or_perish_constructor.simulation.food_diagnosis import diagnose_provincial_food
from prosper_or_perish_constructor.simulation.historical_scenarios import (
    HistoricalScenario, ProductionShock, LandActivation, run_historical_scenario)
from prosper_or_perish_constructor.simulation.equilibrium_controls import measure_subsistence_equilibria
from prosper_or_perish_constructor.simulation.land_investment import apply_land_conversion_experiment
from prosper_or_perish_constructor.simulation.model_acceptance import evaluate_model_acceptance, REQUIRED_EVIDENCE
from prosper_or_perish_constructor.simulation.scenarios import run_food_scenarios


OVERRIDES = (
    'capacity.development_relative=0.05',
    'paths.historical_assignments="research/population_capacity/historical_assignments_round_24.json"',
    'paths.active_modifier_ledger="artifacts/data/population_simulation/repair_round_23/active_modifiers/active_modifier_ledger.parquet"',
)
TAGS = ('wuxian', 'jiaxing', 'huating', 'angkor', 'cairo', 'alexandria', 'patna',
        'delhi', 'kanauj', 'samprangan', 'trowulan', 'paris', 'timbuktu', 'kano',
        'tenochtitlan', 'qusqu', 'dadu', 'palembang', 'iqaluit', 'obdorsk', 'tuvicha_mini', 'fushun_liaoyang')
MISSING = {
    'dated_geography': ['dated numerical criteria for every required region and control; Bali crop extent; Nile basin geometry'],
    'independent_holdouts': ['frozen geographical and independent-source holdouts'],
    'food_controls': ['staffing-dependent cookery/victuals comparisons and complete population/employment shock cases', 'frozen development across historical cases'],
    'food_and_growth_equilibria': ['actual-composition equilibrium measurements and stability checks'],
    'historical_adjustment_comparisons': ['applicable frozen demographic rate ranges; population recovery evidence distinct from wages'],
    'typed_investment_progression': ['dated schedules through the canonical physical opportunity ledger'],
    'physical_maxima_and_urban_employment': ['verified water budget; full simultaneous improvements; urban worker/land competition'],
    'uncertainty_and_parameter_sensitivity': ['isolated regional uncertainty and shared-parameter/holdout comparisons'],
    'native_mechanics': ['applicable active modifier scope coverage and food account reconciliation'],
}


def run(overrides=OVERRIDES, *, output=None, native_scenario=None, include_frozen=False):
    out = output or ROOT / 'artifacts/data/population_simulation/repair_round_25/reconciled_opportunities'
    out.mkdir(parents=True, exist_ok=True)
    _, (state, context, prep) = prepare(overrides)
    state = attach_slave_agriculture(state, subsistence_output=context.subsistence_agriculture, hiring_fraction=.75)
    missing_requirements={key:list(values) for key,values in MISSING.items()}
    if include_frozen:
        missing_requirements['food_controls'].remove('frozen development across historical cases')
    template=native_scenario or HistoricalScenario('base')
    specs = [replace(template,name=f'stock_{stock}_shock_{shock}', stock_months=stock,
             shock=ProductionShock() if shock else None) for stock in (0, 3, 12, 24) for shock in (False, True)]
    if include_frozen:
        specs += [replace(template,name=f'frozen_stock_{stock}',stock_months=stock,frozen_development=True) for stock in (0,3,12,24)]
    identity = fingerprint([ROOT / 'src/prosper_or_perish_constructor/simulation', __file__,
        ROOT / 'research/population_capacity/demographic_adjustment_benchmarks.json'],
        {'preparation': prep, 'overrides': overrides, 'hiring_fraction': .75,
         'scenarios': [asdict(s) for s in specs], 'tags': TAGS, 'required_horizons': [100, 200],
         'missing_requirements': missing_requirements})
    manifest = {'model_accepted': False, 'input_fingerprint': identity, 'preparation': prep,
                'required_horizons': [100, 200], 'scenarios': [asdict(s) for s in specs],
                'hiring_fraction': .75, 'slave_consumption_changed': False,
                'assumptions': ['constructed infrastructure supplies flat capacity', 'native tribal offsets work as authorized',
                                'one agricultural job per current crop support unit is a balance assumption'],
                'game_export_ready': False}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2, default=str))
    state.write_parquet(out / 'starting_ledger.parquet')
    state.select('location_tag', pl.col('base_population_capacity').alias('population_capacity')).write_csv(out / 'candidate_capacity.csv')
    for name, columns in (
        ('components', [c for c in state.columns if c.startswith('capacity__') or c in ('base_population_capacity', 'infrastructure_population_capacity', 'local_population_capacity')]),
        ('development', [c for c in state.columns if 'development' in c or 'management' in c]),
        ('opportunity', [c for c in state.columns if c.startswith('opportunity__')]),
        ('employment_targets', [c for c in state.columns if c.startswith('candidate_agriculture_')])):
        state.select('location_tag', *columns).write_csv(out / f'{name}.csv')
    _, _, budgets = diagnose_provincial_food(state, context)
    budgets.write_csv(out / 'all_province_starting_food_budgets.csv')
    selected = state.filter(pl.col('location_tag').is_in(TAGS))['province'].unique().to_list()
    selected.sort()
    absent = sorted(set(TAGS) - set(state['location_tag']))
    initial = state.filter(pl.col('province').is_in(selected))
    print(f'Prepared {initial.height} locations in {len(selected)} complete provinces; absent tags: {absent}', flush=True)
    cases = []
    geographic_cases = []
    histories = {}
    table = []
    for spec in specs:
        history, result = run_historical_scenario(initial, context, spec)
        history.write_parquet(out / f'{spec.name}.parquet')
        histories[spec.name] = history
        for province in selected:
            # Only Patna was nominated as an adequately provisioned control.
            # Other provinces get diagnostic retention screens, not invented
            # historical acceptance criteria.
            part = history.filter(pl.col('province') == province)
            evaluated = evaluate_trajectory(part, provisioned=province == 'patna_province' and spec.shock is None)
            evaluated.update(name=f'{province}/{spec.name}', scenario=spec.name, province=province)
            if province == 'patna_province' and spec.shock is None:
                cases.append(evaluated)
            if spec.shock is None and (native_scenario is not None or province in {'bali_province', 'cairo_province', 'alexandria_province',
                    'suzhou_province', 'jiaxing_province', 'songjiang_province', 'angkor_province'}):
                # User's peaceful-heartland guardrail is separate from sourced
                # cultivated-area/yield benchmarks; report both requirements.
                viability = evaluate_trajectory(part, provisioned=True)
                viability['name'] = f'heartland_food_viability/{province}/{spec.name}'
                geographic_cases.append(viability)
            for row in evaluated['horizons']:
                table.append({'province': province, 'scenario': spec.name, **row,
                              'behavior_status': evaluated['status'], 'provisioned_control': evaluated['provisioned']})
        print('Finished', spec.name, flush=True)
    pl.DataFrame(table).write_csv(out / 'province_horizon_results.csv')
    recovery = []
    for stock in (0, 3, 12, 24):
        for province in selected:
            recovery.append({'stock_months': stock, 'province': province, 'measurements': compare_recovery(
                histories[f'stock_{stock}_shock_True'].filter(pl.col('province') == province),
                histories[f'stock_{stock}_shock_False'].filter(pl.col('province') == province), end_month=312)})
    (out / 'paired_recovery.json').write_text(json.dumps(recovery, indent=2))
    controls = run_food_scenarios(context, output=out / 'mechanism_controls',native_scenario=native_scenario)
    cases.append({'name': 'default_mechanism_controls', 'status': 'passed' if controls['passed'] else 'failed', 'checks': controls['checks']})
    if include_frozen:
        frozen_controls=run_food_scenarios(context,output=out/'frozen_mechanism_controls',frozen_development=True,native_scenario=native_scenario)
        cases.append({'name':'frozen_mechanism_controls','status':'passed' if frozen_controls['passed'] else 'failed','checks':frozen_controls['checks']})
    equilibria = [measure_subsistence_equilibria(context, development=d,native_scenario=native_scenario) for d in (0., 25., 50., 75., 100.)]
    (out / 'subsistence_equilibria.json').write_text(json.dumps(equilibria, indent=2))
    requests = state.select('location_tag', pl.col('clearable_wild_land_km2_p50').alias('forest_km2'),
                            pl.col('open_conversion_land_km2_p50').alias('open_km2'),
                            pl.lit('full remaining clearing budget; diagnostic, no historical construction date').alias('evidence_id'))
    maximum, ledger = apply_land_conversion_experiment(state, requests, formula=context.capacity_model)
    ledger.write_csv(out / 'full_clearing_activation_ledger.csv')
    def land_sum(frame):
        return frame.select(pl.sum_horizontal('crop_fallow_block_km2', 'extensive_grazing_land_km2', 'retained_wild_land_km2') +
                            pl.col('area_km2') * pl.col('urban_fraction_1300')).to_series().to_numpy()
    physical = [{'name': 'world_current_land_reconciliation', 'status': 'passed' if np.allclose(land_sum(state), state['area_km2'], atol=1e-7) else 'failed'},
                {'name': 'world_full_clearing_conserves_land', 'status': 'passed' if np.allclose(land_sum(state), land_sum(maximum), atol=1e-7) else 'failed'},
                {'name': 'world_clearing_gain_matches_remaining_budget', 'status': 'passed' if np.allclose(
                    maximum['infrastructure_population_capacity']-state['infrastructure_population_capacity'], state['remaining_clearing_capacity']) else 'failed'},
                {'name': 'world_no_clearing_opportunity_left_after_full_activation', 'status': 'passed' if maximum['remaining_clearing_capacity'].max() < 1e-8 else 'failed'}]
    # Explicit date is an experiment setting, not a historical claim.
    investment_requests = tuple((r['location_tag'], r['forest_km2'], r['open_km2']) for r in
        requests.filter(pl.col('location_tag').is_in(initial['location_tag'].to_list())).to_dicts())
    investment_spec = replace(template,name='full_clearing_at_year_25', investments=(LandActivation(301, investment_requests, 'physical-maximum-experiment'),))
    invested, investment_result = run_historical_scenario(initial, context, investment_spec)
    invested.write_parquet(out / 'full_clearing_at_year_25.parquet')
    before = histories['stock_12_shock_False'].filter(pl.col('month') < 301)
    exact_before = before.equals(invested.filter(pl.col('month') < 301))
    investment_result['checks'].append({'name': 'no_investment_benefit_before_activation', 'passed': exact_before})
    investment_result['status'] = 'passed' if all(c['passed'] for c in investment_result['checks']) else 'failed'
    evidence = {}
    evaluated_groups = {'food_controls': cases, 'dated_geography': geographic_cases,
                        'food_and_growth_equilibria': equilibria,
                        'physical_maxima_and_urban_employment': physical,
                        'typed_investment_progression': [investment_result]}
    for group in REQUIRED_EVIDENCE:
        evidence[group] = write_evaluated_evidence(out / 'evidence' / f'{group}.json',
            requirement=group, input_fingerprint=identity,
            cases=evaluated_groups.get(group, []), missing_cases=missing_requirements[group])
    reference = histories['stock_12_shock_False']
    snapshots = {y: reference.filter(pl.col('month') == y * 12) for y in (0, 25, 100, 200)}
    snapshots[0] = snapshots[0].join(initial.select('location_tag', 'historical_area_conflict_km2'), on='location_tag', validate='1:1')
    report = evaluate_model_acceptance(snapshots, evidence, input_fingerprint=identity)
    report['coverage'] = {'complete_provinces': selected, 'absent_requested_tags': absent,
                          'world_starting_budget_locations': state.height,
                          'world_trajectory_evaluated': False}
    (out / 'acceptance.json').write_text(json.dumps(report, indent=2))
    lines = ['# Candidate criteria register', '', '| Requirement | Status | Remaining work |', '|---|---|---|']
    for group in REQUIRED_EVIDENCE:
        lines.append(f"| {group} | {evidence[group]['status']} | {'; '.join(missing_requirements[group])} |")
    (out / 'criteria_register.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assignments')
    parser.add_argument('--output')
    parser.add_argument('--scenario-file')
    parser.add_argument('--scenario')
    parser.add_argument('--include-frozen',action='store_true')
    parser.add_argument('--override',action='append',default=[])
    args=parser.parse_args()
    if (args.assignments or args.scenario_file or args.override) and not args.output:
        parser.error('changed inputs require a separate output directory')
    scenario=None
    if args.scenario_file:
        document=json.loads((ROOT/args.scenario_file).read_text())
        matched=[s for s in document['scenarios'] if s['name']==args.scenario]
        if len(matched)!=1:parser.error('select one exact named scenario')
        scenario=HistoricalScenario(**matched[0])
    overrides=OVERRIDES
    if args.assignments:
        overrides=(*overrides,f'paths.historical_assignments="{args.assignments}"',
                   'capacity.gaez_zero_development_fraction=3.0','capacity.location_area_exponent=0.75',
                   'capacity.urban_allowance_per_observed_worker=3.0')
    run((*overrides,*args.override),output=ROOT/args.output if args.output else None,
        native_scenario=scenario,include_frozen=args.include_frozen)
