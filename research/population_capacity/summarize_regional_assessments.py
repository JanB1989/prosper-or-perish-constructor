"""Summarize isolated regional evidence without certifying a joint candidate."""
import json

import polars as pl

from run_historical_direct import ROOT
from prosper_or_perish_constructor.simulation.cache import fingerprint


CASES = (
    (31, 'niger', 'Timbuktu: water-dependent existing fields'),
    (32, 'shuntian', 'Shuntian: management alone'),
    (33, 'shuntian_fields', 'Shuntian: management and restored current fields'),
    (34, 'cusco_fields', 'Cusco: management and restored current fields'),
)


def run():
    out = ROOT / 'artifacts/data/population_simulation/repair_round_34'
    records = []
    sources = []
    lines = [
        '# Regional assessment results: rounds 31–34', '',
        '**Model not accepted.** These isolated comparisons test historical assignments at unchanged neighbouring assignments. They do not replace a joint candidate run, dated numerical benchmarks, holdouts or the complete acceptance suite.', '',
        'All comparisons retain slave and higher-pop consumption, existing food-building supply, and population composition. Cookeries and victuals markets are the intended urban food supply; no urban food deficit is converted into extra land capacity.', '',
    ]
    for number, folder, title in CASES:
        base = ROOT / f'artifacts/data/population_simulation/repair_round_{number}' / folder
        criteria_path = base / 'viability_criteria.csv'
        manifest_path = base / 'manifest.json'
        sources += [criteria_path, manifest_path, base / 'provincial_budgets.csv']
        criteria = pl.read_csv(criteria_path)
        budget = pl.read_csv(base / 'provincial_budgets.csv')
        manifest = json.loads(manifest_path.read_text())
        lines += [f'## {title}', '',
                  '| Assignment | Minimum local population, year 100 | Year 200 | Unmet location-months through year 200 | Both survival screens |',
                  '|---|---:|---:|---:|---|']
        for name in ('unchanged', 'low', 'central', 'high'):
            part = criteria.filter(pl.col('candidate') == name).sort('year')
            assert part['year'].to_list() == [100, 200]
            rows = part.to_dicts()
            lines.append(f"| {name} | {rows[0]['minimum_location_population_retention']:.2%} | {rows[1]['minimum_location_population_retention']:.2%} | {rows[1]['unmet_location_months_after_startup']:g} | {'passed' if all(r['viability']=='passed' for r in rows) else 'failed'} |")
            for row in rows:
                records.append(dict(round=number, assessment=folder, **row,
                                    evidence=str(criteria_path.relative_to(ROOT)),
                                    recorded_input_fingerprint=manifest['fingerprint']))
        lines += ['', '| Assignment | Peasant subsistence surplus | Other net supply after other-pop consumption | Total monthly balance |',
                  '|---|---:|---:|---:|']
        for row in budget.to_dicts():
            residual = row['subsistence_surplus'] + row['non_subsistence_balance_after_other_pops'] - row['food_balance']
            assert abs(residual) < 1e-8
            lines.append(f"| {row['candidate']} | {row['subsistence_surplus']:.3f} | {row['non_subsistence_balance_after_other_pops']:.3f} | {row['food_balance']:.3f} |")
        lines += ['', f"Evidence: [{folder} criteria](../../{criteria_path.relative_to(ROOT).as_posix()}). Recorded candidate/source/simulator identity: `{manifest['fingerprint']}`.", '']
    lines += [
        '## Interpretation and remaining work', '',
        '- Niger: the new assignment changes the treatment of existing fields, not their hectares. Its water-served fraction is an explicitly inferred northern-delta analogue. Flood-recession farming is not proof of modern controlled-irrigation reliability; this source interpretation still needs a physical yield/water check.',
        '- Shuntian: management alone fails at the low estimate. Restoring the dated current dry-field footprint resolves that comparison. This recovery consumes known land and displaces livelihoods; it grants no irrigation. The crop-mixture mask is not a historical measurement of abandoned farmland. Yield transfer to restored hectares remains uncertain.',
        '- Cusco: management and restoration of dated fields do not resolve the failure, even at the high estimate. Pisaq still has zero crop-density support. This is a missing crop-system input, not evidence of zero Andean agricultural potential. Later imperial terraces and yields remain excluded from the starting assignment.',
        '- Shared scale 3, area exponent 0.75, development coefficient 0.05, subsistence output 1.25, urban allowance 3 per observed worker and removal of the extra urban rank penalty are experimental joint settings. Their geographical and global growth consequences still need joint verification.',
        '- The previous 25% land-pressure offset helped Bali but is absent from these isolated runs. No combined pass total is inferred by stitching these separate comparisons together.',
        '- World starting capacity exceeds 1.85 billion under these experimental parameters. This is a diagnostic total, not a ceiling or an accepted result. High-density and low-fill outliers require physical and 100/200-year plausibility checks.', '',
        'Reproduce each row with the same canonical runner, for example:', '',
        '```sh',
        'uv run python research/population_capacity/run_management_assessment.py --assignments research/population_capacity/historical_assignments_round_33.json --system shuntian_maintained_dryland_cultivation --output artifacts/data/population_simulation/repair_round_33/shuntian_fields',
        'uv run python research/population_capacity/run_management_assessment.py --assignments research/population_capacity/historical_assignments_round_34.json --system cusco_preimperial_maintained_fields --output artifacts/data/population_simulation/repair_round_34/cusco_fields',
        'uv run python research/population_capacity/summarize_regional_assessments.py',
        '```', '',
        'Each directory retains all four resolved assignments, complete-world starting ledgers, monthly complete-province histories, budgets and original fingerprints. These are reproducible experiments; none is an accepted parameter manifest or game export.',
    ]
    out.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(records).write_csv(out / 'isolated_regional_criteria.csv')
    (out / 'regional_evidence_index.json').write_text(json.dumps(dict(
        model_accepted=False, scope='isolated regional comparisons; no joint certification',
        required_horizons=[100, 200], report_fingerprint=fingerprint([__file__, *sources], {})), indent=2)+'\n')
    (ROOT / 'research/population_capacity/round_34_findings.md').write_text('\n'.join(lines)+'\n')


if __name__ == '__main__':
    run()
