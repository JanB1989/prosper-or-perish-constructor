"""Readable failure register built from evaluated artifacts, not hand-set passes."""
import json
from pathlib import Path

import polars as pl
import numpy as np
from run_historical_direct import OVERRIDES as BASE_OVERRIDES
from run_acceptance_round_25 import OVERRIDES
from prosper_or_perish_constructor.simulation.profile import load_population_simulation_profile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts/data/population_simulation/repair_round_25/reconciled_opportunities'


def run():
    acceptance = json.loads((OUT / 'acceptance.json').read_text())
    state = pl.read_parquet(OUT / 'starting_ledger.parquet')
    distributions = []
    starting = state.with_columns(
        (pl.col('total_population') / pl.col('local_population_capacity').clip(lower_bound=1e-12)).alias('fill'),
        (pl.col('total_population') * 1000 / pl.col('area_km2')).alias('density_people_km2'))
    for scope in ('province', 'region', 'macro_region', 'world'):
        scoped = starting.with_columns(pl.lit('world').alias('world')) if scope == 'world' else starting
        for metric in ('total_population', 'local_population_capacity', 'development', 'fill', 'density_people_km2',
                       'infrastructure_population_capacity', 'remaining_clearing_capacity'):
            distributions.append(scoped.group_by(scope).agg(pl.col(metric).min().alias('minimum'),
                pl.col(metric).quantile(.1).alias('p10'), pl.col(metric).median().alias('median'),
                pl.col(metric).quantile(.9).alias('p90'), pl.col(metric).max().alias('maximum'),
                pl.col(metric).sum().alias('sum_of_location_values'), pl.len().alias('locations')).rename({scope: 'scope_key'}).with_columns(
                    pl.lit(scope).alias('scope'), pl.lit(metric).alias('metric'), pl.lit(0).alias('year')))
    pl.concat(distributions).write_csv(OUT / 'starting_scope_distributions.csv')
    profile = load_population_simulation_profile(ROOT / 'population_capacity_simulation.toml', repo=ROOT,
                                                 overrides=(*BASE_OVERRIDES, *OVERRIDES))
    full_capacity = profile.capacity_formula.evaluate(base_capacity=state['base_population_capacity'].to_numpy(),
        infrastructure_capacity=(state['infrastructure_population_capacity'] + state['remaining_clearing_capacity']).to_numpy(),
        development=np.full(state.height, 100.))
    state.select('location_tag', 'province', 'area_km2').with_columns(
        pl.Series('full_clearing_D100_capacity', full_capacity),
        pl.lit('physical potential diagnostic; excludes new irrigation and urban allowances; not accepted maximum').alias('status')).write_csv(OUT / 'full_clearing_D100.csv')
    rows = []
    for path in sorted((OUT / 'evidence').glob('*.json')):
        group = json.loads(path.read_text())
        for case in group['cases']:
            horizon_checks = case.get('checks', [])
            for year in (100, 200):
                applicable = [c for c in horizon_checks if c.get('horizon', year) == year]
                if applicable:
                    status = 'passed' if all(c['passed'] for c in applicable) else 'failed'
                    failures = '; '.join(c['name'] for c in applicable if not c['passed'])
                else:
                    status = case['status']
                    failures = ''
                rows.append({'requirement': group['requirement'], 'case': case['name'],
                             'horizon': year if horizon_checks else None,
                             'status': status, 'failed_checks': failures, 'artifact': str(path.relative_to(ROOT))})
                if not horizon_checks:
                    break
        for missing in group['missing_cases']:
            rows.append({'requirement': group['requirement'], 'case': missing, 'horizon': None,
                         'status': 'not evaluated', 'failed_checks': '', 'artifact': str(path.relative_to(ROOT))})
    pl.DataFrame(rows).write_csv(OUT / 'criteria_case_results.csv')
    failures = [r for r in rows if r['status'] != 'passed']
    (OUT / 'failure_register.json').write_text(json.dumps({'model_accepted': acceptance['model_accepted'],
        'input_fingerprint': acceptance['input_fingerprint'], 'failures_and_missing_work': failures,
        'corrected_failures': [
            {'id': 'stale-historical-clearing-support', 'diagnosis': 'post-assignment hectares paired with pre-assignment support values',
             'correction': 'recalculate and consume the canonical per-pool net support', 'regression': 'test_investment_uses_reconciled_historical_opportunities_once'},
            {'id': 'negative-exhausted-open-pool', 'diagnosis': 'Wujiang floating-point remainder -2.842e-14 km2 rejected full investment',
             'correction': 'normalize numerical residue after rejecting material overclaims', 'regression': 'test_fully_consumed_fractional_pools_remain_nonnegative'}]}, indent=2))
    outcomes = pl.read_csv(OUT / 'province_horizon_results.csv').filter(pl.col('scenario') == 'stock_12_shock_False')
    table = ['| Province | Population retained, year 100 | Year 200 | Unmet location-months after startup, year 200 |',
             '|---|---:|---:|---:|']
    for province in outcomes['province'].unique().sort():
        a = outcomes.filter((pl.col('province') == province) & (pl.col('year') == 100)).row(0, named=True)
        b = outcomes.filter((pl.col('province') == province) & (pl.col('year') == 200)).row(0, named=True)
        table.append(f"| {province} | {a['population_retention']:.1%} | {b['population_retention']:.1%} | {b['unmet_location_months_after_startup']:.0f} |")
    text = '''# Round 25 acceptance results

**The model remains unaccepted.** This round evaluates complete provincial histories, adds reusable events and fixes a real progression-accounting defect. It does not complete historical calibration or all nine acceptance groups.

## Evaluated scope

One preparation combines the round-24 Bali assignments, observed country modifiers and 75% proposed agricultural hiring for slaves. Slave consumption is unchanged. There are 124 locations in 22 complete provinces, with 0/3/12/24 months of starting food and paired 12-month, 50% agricultural-output shocks. Monthly histories include both mandatory horizons. The starting food-budget diagnosis covers all 20,929 locations. No new world trajectory is used to override failed focused cases.

The compatible capacity CSV still means natural/static base. Component, development, opportunity and agricultural employment ledgers accompany it. Dated modifier activation names its recipients, prerequisites and modeled costs. Existing modifiers do not become active merely through eligibility. The later building pass still owns job implementation, costs and level limits.

## Outcomes

These are actual-composition no-import diagnostic runs, not historical population targets. The peaceful-heartland viability checks are explicitly recorded separately from dated agricultural evidence. A global average cannot certify these cases.

''' + '\n'.join(table) + '''

Patna passes its per-location retention and post-startup food checks across all four initial stocks. Bali remains a substantial failure. Its game province includes Lombok and Sasak: provincial sharing links their deficits to the historically improved Balinese locations. At year 200 Samprangan has a surplus while Lombok remains strongly deficient. Removing those neighbours would hide the failure.

Angkor's province-wide 92.9% retention also conceals a failure: the city itself retains only 78.3%, despite no unmet food. The per-location acceptance predicate correctly rejects that case.

The apparently extreme Arctic growth ratio requires its denominator: Qikiqtaaluk starts with only six people in the supplied snapshot (one peasant per location). It rises to roughly 54, not a large settlement. This actual-composition observation cannot substitute for a historically representative tribal coastal control; the latter remains required.

## Mechanisms and progression

At fixed development/prosperity, pure-peasant food break-even is at 110% fill. The separately solved population/stock equilibrium is at approximately 102.4812% fill with 6.336 months of food. Both native-equation residuals are below 1e-7 at development 0/25/50/75/100. These are controlled equilibria, not historical recovery estimates or coupled-economy predictions.

The historical model had updated remaining land areas while retaining earlier clearing-support columns. Those columns now use the historical model's weights, management normalization and remaining land. The full-world clearing test verifies land conservation, matching support gains and exhausted opportunity. Full clearing activated at month 301 produces no benefit before its date. Water-volume feasibility and full combined urban/agricultural maxima remain unresolved; the clearing result cannot certify them.

The reusable runner preserves cumulative food/growth counters across production shocks, modifier activation and land conversion. Paired recovery reports measure sustained halving of population, food-stock and development deviations through the observed horizon; they do not invent a universal historical recovery deadline.

The clearing-only D100 stress calculation totals roughly 24.7 billion game-supported people worldwide and exceeds 30 million in the largest Pampas example. These are hypothetical full-opportunity diagnostics, not accepted historical maxima. They identify why agronomic potential, attainable low-input yields and physically achievable improvement scope still require validation. No fixed global ceiling has been imposed to hide them.

In the separate native-offset comparison, compensating 50% of D50 decay changes Bali's year-200 retention only from 54.63% to 55.49%, and Cairo from 88.33% to 89.05%. Suzhou improves from 110.86% to 111.52%; Patna's population is unchanged while development improves. This supports treating the offset as modest retention assistance. It does not repair missing agricultural support, and no offset is accepted from these partial-scope experiments.

## Global urban-rank diagnosis

Parsed rural generic growth is -0.004/year, versus -0.005/year in towns, cities and megalopolises. With shared provincial food and no migration, the extra urban penalty can cause persistent relative decline even without famine. The global diagnostic retains 100%, 50% or 0% of that difference, while adjusting the tribal rank offset to preserve its exact cancellation. Consumption, capacity, subsistence and employment remain unchanged.

Removing the extra urban penalty raises Angkor city's retention to about 91% at both required horizons. It is nevertheless **not adopted as a standalone repair**: by year 200, 1,300 locations experience more unmet-food months than the unchanged scenario, and world population falls from 402.40 million to 398.58 million. Urban and rural populations compete through the shared food budget; faster urban growth is not a free global improvement. Every location's comparison and annual scope totals are saved under `repair_round_25/urban_rank_diagnosis/`. This separates a growth-coefficient failure from missing agricultural support without concealing the global tradeoff.

## Historical evidence constraint

The cached Christie chapter, *Water and rice in early Java and Bali*, supports early maintained irrigation and community coordination (printed pages 239–253). Its 200-hectare example is the present-day service area of a dam associated with a medieval inscription, not a measured medieval footprint. Medieval Balinese field units describe water infrastructure and cannot simply be converted to modern hectares. This review does not justify increasing Bali's cultivated area until the population result fits. Source hash and provenance remain in `repair_source_manifest.json` (`water_rice_early_java_bali.pdf`).

## Reproduce and inspect

- `uv run python research/population_capacity/run_acceptance_round_25.py`
- `uv run python research/population_capacity/run_acceptance_retention_comparisons.py`
- `uv run python research/population_capacity/run_rank_retention_diagnosis.py`
- `uv run python research/population_capacity/render_acceptance_round_25.py`
- `uv run python research/population_capacity/summarize_acceptance_round_25.py`
- `uv run ppc test -q --tb=short`

Artifacts: `artifacts/data/population_simulation/repair_round_25/reconciled_opportunities/`. Read `criteria_case_results.csv` for the evaluated case/horizon table and `failure_register.json` for exact failed and untested requirements. `candidate_maps.png` and `province_retention.png` show the map and outcomes. The root round-25 run predates the opportunity correction and is preserved as superseded evidence. Retention-offset/frozen runs have their own fingerprints under `retention_comparisons/`; they do not automatically certify the main candidate.

Building balancing, candidate game export and live deployment remain deferred. Missing dated benchmarks, holdouts, water budgets, demographic applicability and full sensitivity coverage are still substantive work, not waived criteria.

Final project validation: `uv run ppc test -q --tb=short` completed with **837 passed, 1 skipped**. The existing skip is the setup-building correction check when the local error log contains no such errors. `git diff --check` passes. Passing software regressions does not change the failed model-acceptance result.
'''
    (ROOT / 'research/population_capacity/round_25_findings.md').write_text(text)


if __name__ == '__main__':
    run()
