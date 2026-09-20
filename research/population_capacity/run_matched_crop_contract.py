"""Round 26: compare matching crop-source contracts before calibrating yields."""
from pathlib import Path
import json
from dataclasses import asdict
import numpy as np
import polars as pl

from run_historical_direct import ROOT, prepare
from run_acceptance_round_25 import OVERRIDES, TAGS
from prosper_or_perish_constructor.simulation.agricultural_employment import attach_slave_agriculture
from prosper_or_perish_constructor.simulation.cache import fingerprint
from prosper_or_perish_constructor.simulation.food_diagnosis import diagnose_provincial_food
from prosper_or_perish_constructor.simulation.historical_scenarios import HistoricalScenario, run_historical_scenario
from prosper_or_perish_constructor.simulation.behavior_acceptance import evaluate_trajectory


def run():
    out=ROOT/'artifacts/data/population_simulation/repair_round_26/crop_contract'
    out.mkdir(parents=True,exist_ok=True)
    manifests=[]; summaries=[]; densities=[]; criteria=[]
    taihu=('paths.historical_assignments="research/population_capacity/historical_assignments_round_26_taihu.json"',)
    for name,extra,rank in [('legacy',(),1.),('matched',('paths.historical_assignments="research/population_capacity/historical_assignments_round_26.json"',),1.),
                       ('taihu_attained',taihu,1.),('taihu_half_rank_penalty',taihu,.5),('taihu_no_rank_penalty',taihu,0.),
                       *[(f'taihu_{label}',(f'paths.historical_assignments="research/population_capacity/historical_assignments_round_26_taihu_{label}.json"',),1.)
                         for label in ('extent_low','extent_high')]]:
        profile,(state,context,prep)=prepare((*OVERRIDES,*extra))
        state=attach_slave_agriculture(state,subsistence_output=context.subsistence_agriculture,hiring_fraction=.75)
        state.write_parquet(out/f'{name}_starting_ledger.parquet')
        _,_,budget=diagnose_provincial_food(state,context)
        budget.write_csv(out/f'{name}_provincial_food.csv')
        maximum=profile.capacity_formula.evaluate(base_capacity=state['base_population_capacity'].to_numpy(),
            infrastructure_capacity=(state['infrastructure_population_capacity']+state['remaining_clearing_capacity']).to_numpy(),
            development=np.full(state.height,100.))
        densities.append(state.select('location_tag','province','area_km2','historical_crop_density_contract',
            'historical_rainfed_density_people_km2','historical_irrigated_density_people_km2',
            'crop_fallow_block_km2','water_managed_fields_km2','base_population_capacity',
            'infrastructure_population_capacity','local_population_capacity','development').with_columns(
                pl.lit(name).alias('candidate'),pl.Series('full_clearing_D100',maximum)))
        provinces=state.filter(pl.col('location_tag').is_in(TAGS))['province'].unique().to_list()
        selected=state.filter(pl.col('province').is_in(provinces))
        scenario=HistoricalScenario(name,remaining_urban_rank_penalty=rank)
        history,result=run_historical_scenario(selected,context,scenario)
        history.write_parquet(out/f'{name}_monthly.parquet')
        for province in provinces:
            check=evaluate_trajectory(history.filter(pl.col('province')==province),provisioned=True)
            for horizon in check['horizons']:
                passed=all(c['passed'] for c in check['checks'] if c.get('horizon',horizon['year'])==horizon['year'])
                criteria.append({'candidate':name,'province':province,**horizon,'status':'passed' if passed else 'failed',
                    'role':'peaceful viability screen; separate historical evidence gates still required'})
        initial=selected.group_by('province').agg(pl.col('total_population').sum().alias('initial_population'))
        for year in (0,25,100,200):
            summaries.append(history.filter(pl.col('month')==year*12).group_by('province').agg(
                pl.col('total_population').sum(),pl.col('local_population_capacity').sum(),pl.col('food_balance').sum(),
                pl.col('unmet_food_months').sum()).join(initial,on='province').with_columns(
                    (pl.col('total_population')/pl.col('initial_population')).alias('population_retention'),
                    pl.lit(year).alias('year'),pl.lit(name).alias('candidate')))
        manifests.append({'name':name,'preparation':prep,'scenario':asdict(scenario),'trajectory_checks':result,
            'world_start_capacity_people':float(state['local_population_capacity'].sum()*1000),
            'world_full_clearing_D100_people':float(maximum.sum()*1000)})
        print('Finished paired crop contract',name,flush=True)
    pl.concat(summaries,how='diagonal_relaxed').write_csv(out/'province_comparison.csv')
    pl.DataFrame(criteria).write_csv(out/'viability_criteria.csv')
    pl.concat(densities).write_parquet(out/'crop_density_comparison.parquet')
    (out/'manifest.json').write_text(json.dumps({'model_accepted':False,'candidates':manifests,
        'fingerprint':fingerprint([Path(__file__),ROOT/'src/prosper_or_perish_constructor/simulation',
            ROOT/'research/population_capacity/historical_rice_yields.json',
            ROOT/'research/population_capacity/historical_assignments_round_26_taihu.json'],
            {'overrides':OVERRIDES,'candidates':manifests,'required_horizons':[100,200]}),
        'contract':'Matched static sample calorie/protein and suitable-area inputs for both water modes. The legacy rainfed path instead uses a joint annual LP scenario allocation. No source is treated as measured medieval yield; historical managed-yield calibration remains required.'},indent=2,default=str))


if __name__=='__main__':run()
