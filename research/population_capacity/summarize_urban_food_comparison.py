"""Reconcile round-27 global effects and report each required horizon."""
from pathlib import Path
import json
import numpy as np
import polars as pl

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'artifacts/data/population_simulation/repair_round_27/urban_food'


def run():
    manifest=json.loads((OUT/'manifest.json').read_text())
    base=pl.read_parquet(OUT/'unchanged_all_location_checkpoints.parquet')
    initial=pl.read_parquet(OUT/'unchanged_starting_ledger.parquet')
    effects=[];invariants=[]
    for candidate in manifest['candidates']:
        name=candidate['name']
        checkpoints=pl.read_parquet(OUT/f'{name}_all_location_checkpoints.parquet')
        state=pl.read_parquet(OUT/f'{name}_starting_ledger.parquet').sort('location_tag')
        reference=initial.sort('location_tag')
        columns=[c for c in state.columns if c.startswith(('capacity__natural_crop','capacity__cultivated_land',
             'capacity__water_control','opportunity__')) or c in ('crop_fallow_block_km2','unemployed_peasants',
             'candidate_agriculture_jobs__slaves','candidate_agriculture_land_job_budget','total_population')]
        unchanged=all(np.allclose(state[c].to_numpy(),reference[c].to_numpy(),equal_nan=True) for c in columns)
        monthly=pl.read_parquet(OUT/f'{name}_monthly.parquet')
        replay=True
        for year in (100,200):
            a=monthly.filter(pl.col('month')==year*12).sort('location_tag')
            b=checkpoints.filter((pl.col('year')==year) & pl.col('location_tag').is_in(a['location_tag'].to_list())).sort('location_tag')
            replay &= all(np.allclose(a[c].to_numpy(),b[c].to_numpy(),rtol=1e-10,atol=1e-8) for c in ('total_population','development','food','local_population_capacity'))
            joined=checkpoints.filter(pl.col('year')==year).select('location_tag','total_population','unmet_food_months').join(
                base.filter(pl.col('year')==year).select('location_tag',pl.col('total_population').alias('baseline_population'),
                    pl.col('unmet_food_months').alias('baseline_unmet')),on='location_tag',validate='1:1')
            joined=joined.with_columns((pl.col('total_population')-pl.col('baseline_population')).alias('population_difference'),
                (pl.col('unmet_food_months')-pl.col('baseline_unmet')).alias('additional_unmet_months'))
            joined.write_csv(OUT/f'{name}_global_effects_{year}.csv')
            effects.append({'candidate':name,'year':year,'world_population_delta_people':joined['population_difference'].sum()*1000,
                'locations_more_unmet_food':joined.filter(pl.col('additional_unmet_months')>0).height,
                'locations_less_unmet_food':joined.filter(pl.col('additional_unmet_months')<0).height})
        invariants.append({'candidate':name,'agricultural_resources_and_initial_population_unchanged':unchanged,
            'monthly_and_world_replay_match':bool(replay)})
    pl.DataFrame(effects).write_csv(OUT/'global_effect_summary.csv')
    (OUT/'accounting_checks.json').write_text(json.dumps(invariants,indent=2)+'\n')
    if not all(r['agricultural_resources_and_initial_population_unchanged'] and r['monthly_and_world_replay_match'] for r in invariants):
        raise ValueError('urban experiment accounting or replay mismatch')
    criteria=pl.read_csv(OUT/'viability_criteria.csv')
    lines=['# Round 27: urban food and accommodation','',
        '**Model remains unaccepted.** This round separates urban food buildings from accommodation. Current victuals-market output is retained in every comparison. No food consumption coefficient, imports, building count or cultivated area is changed.','',
        'The aligned snapshot contains 2,345 cookery records, 335 without recorded employment. The baseline gives those records no staffed output. The staffing scenario fills existing vacancies only from available labourers after reserving their existing employment. Across the world it hires 6,601 additional people in six locations and adds 132.0244 monthly food units. Recipe inputs and wages are assumed supplied; autonomous promotion, hiring and market supply are not simulated.','',
        'Accommodation is tested separately at zero, one and three flat game population units per observed non-agricultural worker unit, before native relative capacity modifiers. These are shared experimental coefficients, not historical household-size estimates or accepted building bonuses. Agricultural opportunity and agricultural job reservations remain unchanged.','',
        'Every location is simulated through 200 years. Monthly histories for 22 complete provinces reproduce the world checkpoints within numerical tolerance. The companion accounting artifact checks that accommodation creates no crop support or agricultural jobs.','',
        '| Candidate | Year | World population difference | Locations with more unmet food |',
        '|---|---:|---:|---:|']
    for r in effects:
        lines.append(f"| {r['candidate']} | {r['year']} | {r['world_population_delta_people']:,.0f} | {r['locations_more_unmet_food']} |")
    lines += ['', '| Candidate | Province | Year | Population retention | Post-startup unmet location-months | Viability |',
              '|---|---|---:|---:|---:|---|']
    for r in criteria.filter(pl.col('province').is_in(['bali_province','trowulan_province','timbuktu_province','pays_france_province','jiaxing_province'])).sort('province','candidate','year').to_dicts():
        lines.append(f"| {r['candidate']} | {r['province']} | {r['year']} | {r['population_retention']:.1%} | {r['unmet_location_months_after_startup']:g} | {r['status']} |")
    lines += ['', 'Viability uses per-location population and development checks, not the province total printed above. Neither a larger world total nor an urban accommodation improvement certifies unresolved geographical, water, holdout or demographic gates.','',
        'Food-budget diagnosis: the major Bali/Java deficits remain pressure-recoverable peasant consumption. Additional urban cookery staffing cannot repair those land-support assignments. Urban food shortages are downstream requirements for cookeries and victuals markets; they must not be converted into agricultural capacity boosts.','',
        'Reproduce:', '', '```sh',
        'uv run python research/population_capacity/run_urban_food_comparison.py',
        'uv run python research/population_capacity/summarize_urban_food_comparison.py',
        'uv run ppc test','```','',
        'All source/preparation parameters, monthly histories, annual world aggregates, reconciled provincial budgets, per-location global effects and horizon-specific viability checks are in `artifacts/data/population_simulation/repair_round_27/urban_food/`. Both new profile options remain disabled by default. No game export or live deployment occurred.']
    (ROOT/'research/population_capacity/round_27_findings.md').write_text('\n'.join(lines)+'\n')


if __name__=='__main__':run()
