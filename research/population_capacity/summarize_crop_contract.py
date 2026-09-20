"""Write the round-26 diagnosis from completed paired evidence, never a pass claim."""
from pathlib import Path
import json
import polars as pl

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'artifacts/data/population_simulation/repair_round_26/crop_contract'


def run():
    manifest=json.loads((OUT/'manifest.json').read_text())
    cases=pl.read_csv(OUT/'viability_criteria.csv')
    rows=cases.filter(pl.col('province').is_in(['suzhou_province','jiaxing_province','songjiang_province']))
    lines=['# Round 26: crop sources and dated Taihu yields','',
        '**Model status: not accepted.** These are paired diagnostics over the same 22 complete provinces. Building balance and game export remain deferred.','',
        'The legacy historical model combines joint-scenario rainfed support with static irrigated sample support. The matching-source candidate uses static calorie/protein and suitable-area denominators for both modes. This corrects comparability, but is not itself proof of medieval yield accuracy. It worsens several heartlands and is not accepted as a global replacement.','',
        'The Taihu attained-yield candidate uses the cached Liu (1991) Song observation: 450 source catties per mou × 0.6 kg × 15 mou/ha = 4,050 kg gross paddy/ha for one harvest. Dry matter of 0.80–0.90 is an explicit sensitivity assumption. Existing crop retention and calorie/protein requirements give 704.63–792.71 standalone people per cultivated km² before game scaling. The scenario carries that Song system to 1337; it does not borrow later Ming yields.','',
        'The attained density replaces support on assigned water-managed fields. It is divided by the assessed starting development factor before flat infrastructure is calculated, so management is not multiplied twice. No extra harvest or adoption hectare is added. The unchanged cultivated range remains inferred, not a measured medieval cadastral total.','',
        'Rank experiments preserve native tribal cancellation. They are diagnostic and unaccepted; neither demand nor capacity changes. Extent experiments vary only Taihu within the previously documented 35–55% range, holding neighbouring assignments fixed.','',
        '| Candidate | Province | Year | Minimum location population retention | Unmet location-months after startup | Viability |',
        '|---|---|---:|---:|---:|---|']
    for r in rows.sort('candidate','province','year').to_dicts():
        lines.append(f"| {r['candidate']} | {r['province']} | {r['year']} | {r['minimum_location_population_retention']:.1%} | {r['unmet_location_months_after_startup']:g} | {r['status']} |")
    lines += ['',
        'Viability applies the user’s peaceful-control food, population and development checks independently at each horizon. It does not certify geographical evidence, water budgets, holdouts, demographic plausibility or the remaining scenario matrix. A province total cannot override a failing location.','',
        'All candidates preserve slave consumption and reserve workers/land for the 75% agricultural-employment diagnostic. Current building employment and food remain separate from direct infrastructure.','',
        'Artifacts: `artifacts/data/population_simulation/repair_round_26/crop_contract/` contains each starting ledger, provincial food budget and monthly trajectory; `viability_criteria.csv` covers every compared province at both horizons; `province_comparison.csv` records totals; `crop_density_comparison.parquet` records the physical/game-unit comparison. `manifest.json` binds scenarios and preparation to the input fingerprint.','',
        f"Evidence fingerprint: `{manifest['fingerprint']}`.",'',
        'Reproduce from the repository:', '', '```sh',
        'uv run python research/population_capacity/run_matched_crop_contract.py',
        'uv run python research/population_capacity/summarize_crop_contract.py',
        'uv run ppc test tests/test_behavior_acceptance.py tests/test_historical_model.py tests/test_crop_intensification.py',
        'uv run ppc test','```','',
        'Remaining work: resolve Bali/Java and other regional food deficits; complete dated physical and demographic benchmarks, water opportunity validation, holdouts and sensitivity; rerun the full mandatory acceptance matrix for a defensible shared candidate. No accepted manifest is issued by this report.']
    validation=OUT/'validation.json'
    if validation.exists():
        v=json.loads(validation.read_text())
        lines += ['',f"Validation: `{v['command']}` — {v['passed']} passed, {v['skipped']} skipped. {v['skip_reason']}"]
    lines += ['', 'Additional Bali research: [Mediani (1989) evidence ledger](bali_mediani_1989_evidence.json) records medieval cooperative clearing and irrigation, the 12th–19th-century documentation gap, and unresolved historical area units. It supplies no automatic hectare or capacity increase.']
    (ROOT/'research/population_capacity/round_26_findings.md').write_text('\n'.join(lines)+'\n')


if __name__=='__main__':run()
