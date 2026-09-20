"""Compare the bounded hierarchy experiment at every saved required horizon."""
import json
import hashlib
from pathlib import Path

import numpy as np
import polars as pl

ROOT=Path(__file__).resolve().parents[2]
ROUND=ROOT/'artifacts/data/population_simulation/repair_round_56'
BASE=ROOT/'artifacts/data/population_simulation/repair_round_55/grouped_world'
NAME='common_slower_quarter'


def check_accounts(frame):
    populations=[c for c in frame.columns if c.startswith('population_') and c not in
                 ['population_maximum_drawdown']]
    # Diagnostic counters have different units from population components.
    populations=[c for c in populations if c in ['population_'+p for p in
        ['peasants','slaves','tribesmen','laborers','burghers','clergy','nobles','soldiers','unknown']]]
    consumption=[c for c in frame.columns if c.startswith('food_consumption__')]
    residuals={
        'population':float(frame.select((pl.sum_horizontal(populations)-pl.col('total_population')).abs().max()).item()),
        'consumption':float(frame.select((pl.sum_horizontal(consumption)-pl.col('food_consumption')).abs().max()).item()),
        'subsistence_surplus':float(frame.select((pl.col('subsistence_food_production')-
            pl.col('peasant_food_consumption')-pl.col('subsistence_surplus')).abs().max()).item()),
    }
    if any(v>1e-7 for v in residuals.values()):
        raise ValueError('Trajectory accounts do not reconcile: '+str(residuals))
    return residuals


def main(world=None, out=None, assignments=None, evidence=None):
    world=world or ROUND/'world'
    out=out or ROUND/'comparison';out.mkdir(parents=True,exist_ok=True)
    old,new=[pl.read_parquet(p/f'{NAME}_checkpoints.parquet') for p in [BASE,world]]
    old_manifest,new_manifest=[json.loads((p/'manifest.json').read_text()) for p in [BASE,world]]
    def parameters(m):
        return {k:v for k,v in (s.split('=',1) for s in m['overrides']) if k!='paths.historical_assignments'}
    assert parameters(old_manifest)==parameters(new_manifest)
    assert old_manifest['cases'][0]['scenario']==new_manifest['cases'][0]['scenario']
    keys=['location_tag','year']
    metrics=['total_population','local_population_capacity','development','unmet_food_months',
        'food_growth_at_cap','food_growth_cap_months','population_maximum_drawdown',
        'maximum_consecutive_starvation_months','food_production','food_consumption','food_balance']
    paired=new.select(keys+['province','region','macro_region']+metrics).join(
        old.select(keys+metrics),on=keys,suffix='_before',validate='1:1')
    assert paired.height==old.height==new.height
    paired.write_parquet(out/'paired_checkpoints.parquet')
    summaries=[]
    for scope in ['macro_region','region','province']:
        aggregates=paired.group_by('year',scope).agg(
            pl.col('total_population','total_population_before','local_population_capacity','local_population_capacity_before',
                   'food_production','food_production_before','food_consumption','food_consumption_before').sum(),
            pl.col('development','development_before').mean(),
            (pl.col('unmet_food_months')>0).sum().alias('ever_unmet'),
            ((pl.col('unmet_food_months')>0)&(pl.col('unmet_food_months_before')==0)).sum().alias('new_unmet'),
            ((pl.col('unmet_food_months')==0)&(pl.col('unmet_food_months_before')>0)).sum().alias('resolved_unmet'),
            (pl.col('unmet_food_months')>pl.col('unmet_food_months_before')).sum().alias('worse_unmet'),
            (pl.col('unmet_food_months')<pl.col('unmet_food_months_before')).sum().alias('better_unmet'))
        aggregates.sort('year',scope).write_csv(out/f'{scope}_horizon_comparison.csv')
    for year in [0,25,100,200]:
        a=old.filter(pl.col('year')==year);b=new.filter(pl.col('year')==year)
        p=paired.filter(pl.col('year')==year)
        row=dict(year=year,population_before_million=float(a['total_population'].sum()/1000),
            population_after_million=float(b['total_population'].sum()/1000),
            capacity_before_million=float(a['local_population_capacity'].sum()/1000),
            capacity_after_million=float(b['local_population_capacity'].sum()/1000),
            development_before=float(a['development'].mean()),development_after=float(b['development'].mean()),
            ever_unmet_before=int((a['unmet_food_months']>0).sum()),ever_unmet_after=int((b['unmet_food_months']>0).sum()),
            new_unmet=int(((p['unmet_food_months']>0)&(p['unmet_food_months_before']==0)).sum()),
            resolved_unmet=int(((p['unmet_food_months']==0)&(p['unmet_food_months_before']>0)).sum()),
            unmet_now_before=int(a['unmet_food_this_month'].sum()),unmet_now_after=int(b['unmet_food_this_month'].sum()),
            at_growth_cap_before=int(a['food_growth_at_cap'].sum()),at_growth_cap_after=int(b['food_growth_at_cap'].sum()))
        summaries.append(row)
    pl.DataFrame(summaries).write_csv(out/'world_horizons.csv')
    final=paired.filter(pl.col('year')==200)
    final.filter((pl.col('unmet_food_months')>0)&(pl.col('unmet_food_months_before')==0)).write_csv(out/'new_unmet_locations.csv')
    a,b=[pl.read_csv(p/'viability_criteria.csv') for p in [ROUND/'baseline_expanded_controls',world]]
    criteria=b.join(a,on=['candidate','province','year'],suffix='_before',validate='1:1')
    criteria.write_csv(out/'evaluated_criteria.csv')
    criteria.filter((pl.col('viability')=='failed')|(pl.col('viability_before')=='failed')).write_csv(out/'failure_register.csv')
    core=pl.read_csv(BASE/'viability_criteria.csv')['province'].unique().to_list()
    old_budget=pl.read_csv(BASE/'all_provincial_food_budgets.csv')
    new_budget=pl.read_csv(world/'all_provincial_food_budgets.csv')
    budgets=new_budget.join(old_budget,on=['province','scenario'],suffix='_before',validate='1:1')
    budgets.write_csv(out/'starting_provincial_food_comparison.csv')
    # Every additional monthly control must replay the archived unchanged world,
    # not merely the old smaller diagnostic subset.
    history=pl.read_parquet(ROUND/'baseline_expanded_controls'/f'{NAME}_monthly.parquet')
    checks={}
    for year in [0,25,100,200]:
        h=history.filter(pl.col('month')==year*12).sort('location_tag')
        expected=old.filter((pl.col('year')==year)&pl.col('location_tag').is_in(h['location_tag'].to_list())).sort('location_tag')
        assert h['location_tag'].to_list()==expected['location_tag'].to_list()
        cols=['total_population','local_population_capacity','development','food','food_production','food_consumption']
        assert np.allclose(h.select(cols).to_numpy(),expected.select(cols).to_numpy(),rtol=1e-10,atol=1e-8)
    checks['baseline_expanded_monthly_replays_world']=True
    checks['candidate_checkpoints']=check_accounts(new)
    checks['candidate_monthly']=check_accounts(pl.read_parquet(world/f'{NAME}_monthly.parquet'))
    checks['baseline_monthly']=check_accounts(history)
    checks['unchanged_food_growth_and_physical_scale_parameters']=True
    checks['original_core']=b.filter(pl.col('province').is_in(core)).group_by('viability').len().to_dicts()
    checks['expanded_before']=a.group_by('year','viability').len().sort('year','viability').to_dicts()
    checks['expanded_after']=b.group_by('year','viability').len().sort('year','viability').to_dicts()
    checks['model_accepted']=False
    checks['round_decision']='Physical-accounting correction and explicit named systems are supported candidate improvements. The global management replacement remains unaccepted: expanded/global food regressions are visible. No numerical range or acceptance threshold changed after the run.'
    paths=[Path(__file__),world/'manifest.json',BASE/'manifest.json',world/f'{NAME}_checkpoints.parquet',
           assignments or ROOT/'research/population_capacity/historical_assignments_round_56.json',
           evidence or ROOT/'research/population_capacity/hierarchical_management_round_56_evidence.json']
    checks['hashes']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    (out/'manifest.json').write_text(json.dumps(checks,indent=2)+'\n')
    print(json.dumps(dict(world=summaries,checks=checks),indent=2))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archaeoglobe',action='store_true')
    args=parser.parse_args()
    if args.archaeoglobe:
        main(world=ROUND/'archaeoglobe/world',out=ROUND/'archaeoglobe/comparison',
            assignments=ROOT/'research/population_capacity/historical_assignments_round_56_archaeoglobe.json',
            evidence=ROOT/'research/population_capacity/archaeoglobe_round_56_evidence.json')
    else:
        main()
