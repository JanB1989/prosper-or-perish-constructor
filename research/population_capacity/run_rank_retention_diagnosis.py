"""Global beneficiary diagnosis for the food-independent urban growth penalty.

No rates are adopted or exported. Tribal rank cancellation is preserved.
"""
from dataclasses import replace
import json

import polars as pl

from run_historical_direct import ROOT, prepare
from run_acceptance_round_25 import OVERRIDES
from prosper_or_perish_constructor.simulation.agricultural_employment import attach_slave_agriculture
from prosper_or_perish_constructor.simulation.cache import fingerprint
from prosper_or_perish_constructor.simulation.land_experiments import _totals
from prosper_or_perish_constructor.simulation.run import Simulation


def run():
    _, (state, context, prep) = prepare(OVERRIDES)
    state = attach_slave_agriculture(state, subsistence_output=context.subsistence_agriculture, hiring_fraction=.75)
    out = ROOT / 'artifacts/data/population_simulation/repair_round_25/urban_rank_diagnosis'
    out.mkdir(parents=True, exist_ok=True)
    rural = context.rank_baselines.filter(pl.col('location_rank') == 'rural_settlement')['local_population_growth'][0]
    rows, totals = [], []
    for remaining in (1., .5, 0.):
        original = context.rank_baselines
        adjusted = original.with_columns(
            (pl.lit(rural) + (pl.col('local_population_growth') - rural) * remaining).alias('_new_growth'))
        adjusted = adjusted.with_columns(
            (pl.col('local_tribesmen_pop_growth') + pl.col('local_population_growth') - pl.col('_new_growth')).alias('local_tribesmen_pop_growth'),
            pl.col('_new_growth').alias('local_population_growth')).drop('_new_growth')
        adjusted.write_csv(out / f'rank_coefficients_{remaining:g}.csv')
        sim = Simulation(state, replace(context, rank_baselines=adjusted))
        for year in range(201):
            if year:
                sim.run(12, progress=False, materialize=False)
            sim.evaluate_food_budget()
            diagnostic = sim.diagnostic_state()
            totals.append(_totals(diagnostic, year).with_columns(pl.lit(remaining).alias('remaining_urban_penalty')))
            if year in (0, 25, 100, 200):
                rows.append(diagnostic.with_columns(pl.lit(year).alias('year'), pl.lit(remaining).alias('remaining_urban_penalty')))
        print('Finished global urban penalty fraction', remaining, flush=True)
    checkpoints = pl.concat(rows, how='diagonal_relaxed')
    checkpoints.write_parquet(out / 'all_location_checkpoints.parquet')
    pl.concat(totals, how='diagonal_relaxed').write_parquet(out / 'annual_scope_history.parquet')
    initial = state.select('location_tag', 'location_rank', pl.col('total_population').alias('initial_population'))
    checkpoints.filter(pl.col('year').is_in([100, 200])).join(initial, on='location_tag', validate='m:1').with_columns(
        (pl.col('total_population') / pl.col('initial_population')).alias('population_retention')).write_csv(out / 'all_beneficiary_comparison.csv')
    (out / 'manifest.json').write_text(json.dumps({'accepted': False, 'input_fingerprint': fingerprint(
        [__file__, ROOT / 'src/prosper_or_perish_constructor/simulation'], {'preparation': prep,
        'remaining_urban_penalty': [1., .5, 0.], 'hiring_fraction': .75, 'required_horizons': [100, 200]}),
        'preparation': prep, 'diagnosis': 'Urban ranks have -0.001/year extra generic decline relative to rural ranks. Shared provincial food cannot independently offset rank differences.',
        'expected_effect': 'Reduce urban attrition without changing food demand, subsistence, capacity or native tribal rank cancellation.',
        'coverage': 'Every location, including rural provinces sharing food with urban beneficiaries. Fixed construction and jobs; no migration or autonomous investment.',
        'decision': 'Diagnostic only. Geography is not repaired by changing rank growth.'}, indent=2, default=str))


if __name__ == '__main__':
    run()
