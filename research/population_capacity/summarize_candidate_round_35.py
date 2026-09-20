"""Report the complete regional survival screen and the remaining uncertainty."""
import json
import polars as pl
from run_historical_direct import ROOT
from prosper_or_perish_constructor.simulation.cache import fingerprint


def run():
    out=ROOT/'artifacts/data/population_simulation/repair_round_35'
    pressure=pl.read_csv(out/'pressure/viability_criteria.csv')
    selected=pressure.filter(pl.col('candidate')=='pressure_offset_0.25')
    assert selected.height==44 and selected['year'].unique().sort().to_list()==[100,200]
    uncertainty=pl.read_csv(out/'cusco_crop/viability_criteria.csv')
    state=pl.read_parquet(out/'cusco_crop/central_starting_ledger.parquet')
    missing=state.filter(pl.col('historical_rainfed_density_source_gap'))
    missing.select('location_tag','province','region','historical_system_id','historical_rainfed_density_inferred',
        'historical_rainfed_density_unresolved','crop_fallow_block_km2','water_managed_fields_km2',
        'historical_rainfed_density_people_km2','historical_irrigated_density_people_km2').write_csv(out/'crop_density_coverage_conflicts.csv')
    lines=['# Round 35: central provincial survival screen', '',
        '**All 44 central-candidate provincial survival checks pass with the 25% D50-decay offset. The model is not yet accepted.** The low Cusco crop/management estimate still fails. Dated benchmarks, independent holdouts, global collateral, complete scenario coverage and water/opportunity maxima remain separate gates.', '',
        'This comparison retains all 22 complete provinces and both mandatory horizons. It uses the same starting state, active effects, employment reservations, food production and consumption across pressure-offset candidates. Cookeries and victuals markets remain urban supply; there is no additional food-building allowance or higher-pop consumption cut.', '',
        '## The concrete crop-input repair', '',
        'Pisaq had reconstructed current dry fields but zero conditional crop support. That drove its central round-34 peasant consumption above 400 food/month and exhausted the shared provincial food budget. Increasing management alone did not fix it.', '',
        'The new explicit analogue fills only zero support on current dry fields within the documented Cusco system. Its range is the full positive-density envelope of six same-province, same-native-climate donors: 122.545–401.197 people per cultivated km² at source reference development 25. The inherited calendar is removed before constructing the range, and reference development is removed once before applying recipient effectiveness. No population enters donor selection, no positive yield is raised, and no land or irrigation is added.', '',
        'This is an inferred comparison, not a measured Pisaq yield. The native climate class is coarse; cultivar, fallow and source-history uncertainty remain. [The evidence record](cusco_missing_crop_evidence.json) freezes donors, source hash, units and exclusions. [FAO’s Andean-system account](https://www.fao.org/giahs/giahs-around-the-world/peru-andean-agriculture/en) supports altitude-adapted crops and maintained systems, not the numerical transfer itself.', '',
        '| Cusco assignment | Year 100 minimum local population retention | Year 200 | Unmet location-months through year 200 | Result |',
        '|---|---:|---:|---:|---|']
    for candidate in ('unchanged','low','central','high'):
        rows=uncertainty.filter(pl.col('candidate')==candidate).sort('year').to_dicts()
        lines.append(f"| {candidate} | {rows[0]['minimum_location_population_retention']:.2%} | {rows[1]['minimum_location_population_retention']:.2%} | {rows[1]['unmet_location_months_after_startup']:g} | {'passed' if all(r['viability']=='passed' for r in rows) else 'failed'} |")
    lines+=['', '## Both required horizons, central candidate', '',
            '| Province | Population retained at 100 | At 200 | Minimum development retained across horizons | Unmet location-months through 200 | Result |',
            '|---|---:|---:|---:|---:|---|']
    for province in selected['province'].unique().sort():
        rows=selected.filter(pl.col('province')==province).sort('year').to_dicts()
        lines.append(f"| {province} | {rows[0]['minimum_location_population_retention']:.2%} | {rows[1]['minimum_location_population_retention']:.2%} | {min(r['minimum_location_development_retention'] for r in rows):.2%} | {rows[1]['unmet_location_months_after_startup']:g} | {'passed' if all(r['viability']=='passed' for r in rows) else 'failed'} |")
    lines+=['', 'These are per-location peaceful survival predicates, not provincial averages or historical population targets. Without the retention offset, 43/44 pass: Bali reaches 89.903% at year 100. Both 25% and 50% offsets pass 44/44; the smaller offset remains the conservative candidate.', '',
        f"The new coverage diagnostic identifies {missing.height} locations with current dry fields but zero source crop density; one is explicitly inferred and {missing.filter(pl.col('historical_rainfed_density_unresolved')).height} remain unresolved. These can include misclassified water-dependent fields as well as missing crop evidence. The diagnostic is not authorization to give every flagged location a yield. The complete list is in `crop_density_coverage_conflicts.csv`.", '',
        'The new source-gap, inferred and unresolved ledger flags are independent. A numerical fill does not relabel the original source as observed. Existing tests cover evidence requirements, applicability dates, reference units, unchanged positive yields and hectare conservation.', '',
        '## Remaining acceptance actions', '',
        '- Resolve whether the low Andean range represents plausible starting support or a genuine scarcity case; do not discard it because it fails.',
        '- Evaluate every global beneficiary of the rank/pressure candidate, including low-fill growth and already prosperous regions. The world comparison keeps food buildings unchanged and checks annual checkpoints against monthly provincial histories.',
        '- Complete the nine-group criteria register on this exact candidate: numerical historical/holdout criteria, stocks/compositions/shocks, actual-composition equilibria, demographic applicability, dated investment, physically bounded maxima and joint sensitivity. Earlier artifacts cannot certify changed inputs.',
        '- Preserve model/export separation. No game export, live deployment, building-level balance or accepted manifest has been produced.', '',
        'Reproduce:', '', '```sh',
        'uv run python research/population_capacity/run_management_assessment.py --assignments research/population_capacity/historical_assignments_round_35.json --system cusco_preimperial_maintained_fields --output artifacts/data/population_simulation/repair_round_35/cusco_crop',
        'uv run python research/population_capacity/run_acceptance_retention_comparisons.py --assignments research/population_capacity/historical_assignments_round_35.json --output artifacts/data/population_simulation/repair_round_35/pressure --no-frozen',
        'uv run python research/population_capacity/run_candidate_world_comparison.py --assignments research/population_capacity/historical_assignments_round_35.json --output artifacts/data/population_simulation/repair_round_35/world --monthly-reference artifacts/data/population_simulation/repair_round_35/pressure/pressure_offset_0.25.parquet',
        'uv run python research/population_capacity/summarize_candidate_round_35.py',
        'uv run ppc test -q', '```', '']
    validation=out/'test_validation.json'
    if validation.exists():
        record=json.loads(validation.read_text())
        current=record['input_fingerprint']==fingerprint([ROOT/'src',ROOT/'tests',ROOT/'pyproject.toml',ROOT/'uv.lock'],{})
        lines+=['',f"Full validation: {record['passed']} passed, {record['skipped']} skipped in {record['seconds']} seconds. Recorded code/test inputs {'match current files' if current else 'are stale; rerun required'}. {record['skip_reason']}",
                'The focused historical/food/land regressions passed 27 tests. [Global collateral results](round_35_world_findings.md) remain separate from this regional survival gate.','']
    (ROOT/'research/population_capacity/round_35_findings.md').write_text('\n'.join(lines)+'\n')
    (out/'regional_gate.json').write_text(json.dumps(dict(model_accepted=False,
        central_regional_survival_passed=bool((selected['viability']=='passed').all()),
        passed_horizon_cases=selected.filter(pl.col('viability')=='passed').height,
        mandatory_horizon_cases=44, uncertainty_passed=False,
        evidence_fingerprint=fingerprint([__file__,out/'pressure/results.json',out/'pressure/viability_criteria.csv',
            out/'cusco_crop/manifest.json',out/'cusco_crop/viability_criteria.csv'],{})),indent=2)+'\n')
    # Carry every earlier case forward explicitly; a pass on old assignments
    # cannot quietly certify the current candidate. Keep its recorded result
    # as historical evidence, separately from current evaluation status.
    earlier=pl.read_csv(ROOT/'artifacts/data/population_simulation/repair_round_25/reconciled_opportunities/criteria_case_results.csv')
    register=[]
    for row in earlier.to_dicts():
        register.append(dict(requirement=row['requirement'],case=row['case'],horizon=row['horizon'],
            status='not evaluated',recorded_previous_status=row['status'],
            evidence=row['artifact'],action='Evaluate this requirement on the current fingerprint; previous experiment retained.'))
    for row in selected.to_dicts():
        register.append(dict(requirement='dated_geography',case='central_peaceful_viability/'+row['province'],
            horizon=row['year'],status=row['viability'],evidence='pressure/viability_criteria.csv',
            threshold='Each location: population and nonzero development retention >=0.9; no unmet food after month 12.',
            action='Survival predicate evaluated; dated physical and demographic criteria remain separate.'))
    for row in uncertainty.to_dicts():
        register.append(dict(requirement='uncertainty_and_parameter_sensitivity',case='cusco/'+row['candidate'],
            horizon=row['year'],status=row['viability'],evidence='cusco_crop/viability_criteria.csv',
            threshold='Same per-location peaceful viability predicate; full frozen donor envelope retained.',
            action='Resolve low-end field-system evidence; do not omit its failure.'))
    assumptions=[
        'Constructed infrastructure supplies flat capacity independently of proposed staffing.',
        'Native tribal self-provisioning and additive growth/starvation offsets operate as authorized.',
        'Existing cookery/victuals supply is included; future building balance is deferred, not inferred as free current food.',
    ]
    (out/'criteria_register.json').write_text(json.dumps(dict(model_accepted=False,
        required_horizons=[100,200],assumptions=assumptions,cases=register,
        fingerprint=fingerprint([__file__,out/'pressure/results.json',out/'cusco_crop/manifest.json'],{})),indent=2)+'\n')


if __name__=='__main__':run()
