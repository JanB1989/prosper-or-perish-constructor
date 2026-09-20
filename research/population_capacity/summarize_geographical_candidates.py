"""Report round-29 viability without conflating it with model acceptance."""
import json
import numpy as np
import polars as pl
from run_historical_direct import ROOT


def run():
    out=ROOT/'artifacts/data/population_simulation/repair_round_29/geography'
    manifest=json.loads((out/'manifest.json').read_text())
    results=pl.read_csv(out/'viability_criteria.csv')
    baseline=pl.read_parquet(out/'baseline_starting_ledger.parquet').sort('location_tag')
    accounting=[]
    for candidate in manifest['candidates']:
        name=candidate['candidate']
        state=pl.read_parquet(out/f'{name}_starting_ledger.parquet').sort('location_tag')
        unchanged=np.allclose(state['crop_fallow_block_km2'].to_numpy(),baseline['crop_fallow_block_km2'].to_numpy())
        land=state.select(pl.sum_horizontal('crop_fallow_block_km2','extensive_grazing_land_km2','retained_wild_land_km2')+
            pl.col('area_km2')*pl.col('urban_fraction_1300')).to_series().to_numpy()
        reconciled=np.allclose(land,state['area_km2'].to_numpy(),atol=1e-7)
        accounting.append({'candidate':name,'cultivated_extent_unchanged':bool(unchanged),'land_reconciles':bool(reconciled)})
    if not all(x['cultivated_extent_unchanged'] and x['land_reconciles'] for x in accounting):
        raise ValueError('geographical comparison changed cultivated extent or violated land accounting')
    (out/'physical_accounting.json').write_text(json.dumps(accounting,indent=2)+'\n')
    lines=['# Round 29: regional management and shared scaling','',
        '**Model not accepted.** The strongest tested combination passes 35 of 44 province/horizon peaceful-viability screens, compared with 22 for the baseline. These screens are not substitutes for historical, demographic, holdout, sensitivity or full-scenario acceptance.','',
        'Eastern Java now has a shared maintained-rice-system assessment on its existing fields. Direct evidence is strongest for Malang and the Brantas basin; other eastern locations are explicit regional analogues. The assignment range is development 45–70 with 25–75% water service, below the core Trowulan/Bali range. No extra cultivated hectares or second rice harvest are assumed. See [the frozen evidence interpretation](eastern_java_rice_management_evidence.json).','',
        'The comparisons then vary the shared physical/game scale from 1.5 to 3 and the area exponent from 0.5 to 0.75. These modify game capacity, not physical hectares. The subdivision bias for two equal locations falls from 41.42% at exponent 0.5 to 18.92% at 0.75. It is still present and explicit.','',
        'Joint comparisons add the previously tested urban accommodation coefficient of 3, then remove the extra urban rank growth penalty while preserving tribal cancellation. Subsistence production, population-type consumption and existing food-building output are unchanged. Neither joint change is accepted or exported.','',
        '| Candidate | Passed horizon screens | Failed horizon screens |',
        '|---|---:|---:|']
    for name in results['candidate'].unique(maintain_order=True):
        part=results.filter(pl.col('candidate')==name)
        lines.append(f"| {name} | {part.filter(pl.col('viability')=='passed').height} | {part.filter(pl.col('viability')=='failed').height} |")
    lines += ['', '| Province | Year | Minimum location population retention | Post-startup unmet location-months | Viability |',
              '|---|---:|---:|---:|---|']
    for r in results.filter(pl.col('candidate')=='joint_rank').sort('province','year').to_dicts():
        lines.append(f"| {r['province']} | {r['year']} | {r['minimum_location_population_retention']:.3%} | {r['unmet_location_months_after_startup']:g} | {r['viability']} |")
    lines += ['',
        'Bali remains failed at year 100: 89.903% retention is below 90%, despite passing year 200. It is not rounded into a pass. The other remaining failures are Acamama, Pays de France, Shuntian and Timbuktu at both horizons. Trowulan passes both horizons only in the joint rank comparison.','',
        'The Arctic snapshot includes only six people in the Qikiqtaaluk case; its roughly ninefold growth is about 54 people at year 200. A viability pass is not independent validation of either Arctic carrying capacity or demographic rates.','',
        'Land accounting passes for all candidates and cultivated hectares remain identical. Starting cropland comes from the LUH2-derived land-cover fractions; the separately sampled HYDE series supplies related comparison/progression evidence. They are related evidence, not independent validation, and their local area estimates differ. No source series was swapped simply because it increased support.','',
        'Next diagnoses: maintained agriculture around Paris, water/crop assignments in Shuntian, Andean managed fields and Niger floodplain support. Regional uncertainty, demographic plausibility, full physical opportunities and all nine acceptance groups still need evaluation for the eventual candidate. World starting food budgets are saved, but world trajectories for these changed parameters are deferred until the focused failures are repaired.','',
        'Reproduce:', '', '```sh',
        'uv run python research/population_capacity/run_geographical_candidates.py',
        'uv run python research/population_capacity/summarize_geographical_candidates.py',
        '```','',
        f"Evidence fingerprint: `{manifest['fingerprint']}`.", '',
        'Artifacts: `artifacts/data/population_simulation/repair_round_29/geography/` contains full starting ledgers and world food budgets, monthly histories for 22 complete provinces, the horizon-specific criteria register, and physical-accounting checks. The previous full project suite remains 842 passed with one existing environment-dependent skip; this round changes research assignments and comparison runners, not game output.']
    (ROOT/'research/population_capacity/round_29_findings.md').write_text('\n'.join(lines)+'\n')


if __name__=='__main__':run()
