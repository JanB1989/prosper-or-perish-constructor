"""Round 29: historical management first, then shared physical/game scaling."""
import json
from dataclasses import asdict
import polars as pl
from run_historical_direct import ROOT,prepare
from run_acceptance_round_25 import OVERRIDES,TAGS
from prosper_or_perish_constructor.simulation.agricultural_employment import attach_slave_agriculture
from prosper_or_perish_constructor.simulation.historical_scenarios import HistoricalScenario,run_historical_scenario
from prosper_or_perish_constructor.simulation.behavior_acceptance import evaluate_trajectory
from prosper_or_perish_constructor.simulation.food_diagnosis import diagnose_provincial_food
from prosper_or_perish_constructor.simulation.cache import fingerprint


def run():
    out=ROOT/'artifacts/data/population_simulation/repair_round_29/geography'
    out.mkdir(parents=True,exist_ok=True)
    specifications=[('baseline',28,1.5,.5,0.,1.),('regional_management',29,1.5,.5,0.,1.),
                    ('area_exponent',29,1.5,.75,0.,1.),('shared_scale',29,3.,.75,0.,1.),
                    ('joint_urban',29,3.,.75,3.,1.),('joint_rank',29,3.,.75,3.,0.)]
    reports=[];criteria=[];budgets=[]
    for name,assignment,scale,alpha,urban,rank in specifications:
        overrides=(*OVERRIDES,f'paths.historical_assignments="research/population_capacity/historical_assignments_round_{assignment}.json"',
                   f'capacity.gaez_zero_development_fraction={scale}',f'capacity.location_area_exponent={alpha}',
                   f'capacity.urban_allowance_per_observed_worker={urban}')
        _,(state,context,prep)=prepare(overrides)
        state=attach_slave_agriculture(state,subsistence_output=context.subsistence_agriculture,hiring_fraction=.75)
        state.write_parquet(out/f'{name}_starting_ledger.parquet')
        _,_,budget=diagnose_provincial_food(state,context)
        budgets.append(budget.with_columns(pl.lit(name).alias('candidate')))
        provinces=state.filter(pl.col('location_tag').is_in(TAGS))['province'].unique().to_list()
        selected=state.filter(pl.col('province').is_in(provinces))
        scenario=HistoricalScenario(name,remaining_urban_rank_penalty=rank)
        history,result=run_historical_scenario(selected,context,scenario)
        history.write_parquet(out/f'{name}_monthly.parquet')
        for province in provinces:
            evaluated=evaluate_trajectory(history.filter(pl.col('province')==province),provisioned=True)
            for row in evaluated['horizons']:
                passed=all(c['passed'] for c in evaluated['checks'] if c.get('horizon',row['year'])==row['year'])
                criteria.append({'candidate':name,'province':province,**row,'viability':'passed' if passed else 'failed'})
        reports.append({'candidate':name,'overrides':overrides,'scenario':asdict(scenario),'preparation':prep,'numerical_checks':result})
        print('Finished geographical candidate',name,flush=True)
    pl.DataFrame(criteria).write_csv(out/'viability_criteria.csv')
    pl.concat(budgets,how='diagonal_relaxed').write_csv(out/'world_starting_food_budgets.csv')
    identity=fingerprint([__file__,ROOT/'src/prosper_or_perish_constructor/simulation',ROOT/'research/population_capacity/eastern_java_rice_management_evidence.json'],
                         {'specifications':specifications,'reports':reports,'horizons':[100,200]})
    (out/'manifest.json').write_text(json.dumps({'accepted':False,'fingerprint':identity,'candidates':reports,
        'contract':'Dated regional management on existing fields; explicit analogues outside direct Malang/Brantas coverage. Shared conversion parameters vary globally. No per-location population fit, extra cultivated hectares or double rice harvest.',
        'scope':'World starting budgets; monthly histories for 22 complete provinces. Full world trajectories deferred until focused cases pass.'},indent=2,default=str))


if __name__=='__main__':run()
