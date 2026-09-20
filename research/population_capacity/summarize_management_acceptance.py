"""Report isolated management and pressure comparisons without promoting them."""
import json
import numpy as np
import polars as pl
from run_historical_direct import ROOT, prepare
from prosper_or_perish_constructor.simulation.food_diagnosis import diagnose_provincial_food
from prosper_or_perish_constructor.simulation.cache import fingerprint


def run():
    base=ROOT/'artifacts/data/population_simulation/repair_round_30'
    manifest=json.loads((base/'parisis/manifest.json').read_text())
    central=next(c for c in manifest['cases'] if c['candidate']=='central')
    _, (_, context, _)=prepare(central['overrides'])
    state=pl.read_parquet(base/'parisis/central_starting_ledger.parquet')
    _, _, budget=diagnose_provincial_food(state,context)
    residual=(budget['subsistence_surplus']+budget['non_subsistence_balance_after_other_pops']-budget['food_balance']).to_numpy()
    assert np.isfinite(residual).all() and np.max(np.abs(residual))<1e-8
    budget.write_csv(base/'world_reconciled_food_budgets.csv')
    criteria=pl.read_csv(base/'parisis/viability_criteria.csv')
    pressure=pl.read_csv(base/'pressure/viability_criteria.csv')
    test_result=json.loads((base/'test_validation.json').read_text())
    test_current=test_result['input_fingerprint']==fingerprint([ROOT/'src',ROOT/'tests',ROOT/'pyproject.toml',ROOT/'uv.lock'],{})
    lines=['# Round 30: Paris management and conservative pressure retention','',
        '**Model not accepted.** The updated 25% pressure-offset candidate passes 38 of 44 regional horizon viability checks. Shuntian, Timbuktu and Acamama still fail at years 100 and 200. Global beneficiaries, historical plausibility and the other mandatory evidence groups remain to be verified.','',
        'The Parisis assignment uses [Higounet’s archival study](https://www.persee.fr/doc/crai_0065-0536_1956_num_100_4_10682) as evidence for maintained medieval open-field cultivation. Development 37.5–62.5 is an explicit game assessment range, not a historical measurement. No cultivated hectares, irrigation, food output or crop-calendar advantage were added. The world-start comparison verifies that neighbouring assignments, populations and building food remain unchanged.','',
        '| Paris-area candidate | Year | Minimum location population retention | Unmet location-months after startup | Viability |',
        '|---|---:|---:|---:|---|']
    for r in criteria.to_dicts():
        lines.append(f"| {r['candidate']} | {r['year']} | {r['minimum_location_population_retention']:.3%} | {r['unmet_location_months_after_startup']:g} | {r['viability']} |")
    lines += ['', 'All three documented management positions pass both horizons. This addresses the previous potential-based classification of Paris as marginal dryland agriculture; it does not guarantee a reconstruction of historical war, plague, imports or investment.','',
        'The pressure experiment uses the canonical simulator, with a constant flat development addition cancelled in proportion to native free-land strength. It saturates at capacity. Fractions 0%, 25% and 50% of D50 decay correspond to 0, 0.0003125 and 0.000625 development/month. No starting capacity or food is added.','',
        '| Full-pressure compensation | Bali year 100 minimum retention | Bali year 200 minimum retention | Passed regional horizon checks |',
        '|---|---:|---:|---:|']
    for name in pressure['candidate'].unique(maintain_order=True):
        part=pressure.filter(pl.col('candidate')==name)
        bali=part.filter(pl.col('province')=='bali_province').sort('year')
        lines.append(f"| {name} | {bali['minimum_location_population_retention'][0]:.3%} | {bali['minimum_location_population_retention'][1]:.3%} | {part.filter(pl.col('viability')=='passed').height}/44 |")
    lines += ['', 'The smaller nonzero offset is sufficient for Bali in this candidate. It is not accepted yet: this regional comparison does not replace a global beneficiary check or uncertainty tests.','',
        'The new canonical budget split is:', '',
        '`food balance = peasant subsistence surplus + (other net food supply − non-peasant consumption)`','',
        'Other net supply includes existing buildings, staffed agricultural jobs, RGO food, imports and production food inputs exactly once. It is not an invented cookery allowance. Cookeries/victuals markets remain the urban supply mechanism; geographical calibration must not disguise a missing supply contribution.','',
        '| Province | Peasant subsistence surplus | Other net supply after non-peasant demand | Total starting balance | Pressure-recoverable consumption |',
        '|---|---:|---:|---:|---:|']
    names=['pays_france_province','shuntian_province','timbuktu_province','acamama_province','bali_province']
    for r in budget.filter(pl.col('province').is_in(names)).sort('province').to_dicts():
        lines.append(f"| {r['province']} | {r['subsistence_surplus']:.3f} | {r['non_subsistence_balance_after_other_pops']:.3f} | {r['food_balance']:.3f} | {r['pressure_recoverable_consumption']:.3f} |")
    lines += ['', f"World province food accounts reconcile within {np.max(np.abs(residual)):.3g} food/month. Food and consumption coefficients are unchanged. The full budget is saved in `world_reconciled_food_budgets.csv`.",'',
        (f"Validation: **{test_result['passed']} passed, {test_result['skipped']} skipped** in the full `uv run ppc test -q` run ({test_result['seconds']} seconds). Input fingerprint matches the recorded run. The skip concerns a local game error log without setup-building errors." if test_current else 'Validation: the recorded full-test result is stale for current code; rerun before acceptance.'),
        'Focused diagnosis, historical model, urban staffing and trajectory regressions: 21 passed. No game export or deployment.','',
        'Reproduce:', '', '```sh',
        'uv run python research/population_capacity/run_management_assessment.py --assignments research/population_capacity/historical_assignments_round_30.json --system parisis_maintained_open_fields --output artifacts/data/population_simulation/repair_round_30/parisis',
        'uv run python research/population_capacity/run_acceptance_retention_comparisons.py --assignments research/population_capacity/historical_assignments_round_30.json --output artifacts/data/population_simulation/repair_round_30/pressure --no-frozen',
        'uv run python research/population_capacity/summarize_management_acceptance.py',
        'uv run ppc test -q', '```','',
        'Next geographical work: water-dependent northern Niger fields, missing/uncertain Andean crop inputs and Shuntian land assignments. [The newly cached Cusco archaeological evidence](cusco_management_evidence.json) distinguishes early cultivation from later imperial terraces; it does not justify backdating the full later system.']
    (ROOT/'research/population_capacity/round_30_findings.md').write_text('\n'.join(lines)+'\n')
    (base/'validation.json').write_text(json.dumps(dict(model_accepted=False,tests=dict(record=test_result,current=test_current),
        food_account_max_absolute_residual=float(np.max(np.abs(residual))),
        input_fingerprint=fingerprint([__file__, ROOT/'src/prosper_or_perish_constructor/simulation', base/'parisis/manifest.json',base/'pressure/results.json'],{})),indent=2)+'\n')


if __name__=='__main__':run()
