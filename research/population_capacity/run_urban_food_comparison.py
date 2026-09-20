"""Round 27: separate existing cookery staffing from urban accommodation."""
from pathlib import Path
import json
import polars as pl
from run_historical_direct import ROOT,prepare
from run_acceptance_round_25 import OVERRIDES,TAGS
from prosper_or_perish_constructor.simulation.agricultural_employment import attach_slave_agriculture
from prosper_or_perish_constructor.simulation.food_diagnosis import diagnose_provincial_food
from prosper_or_perish_constructor.simulation.historical_scenarios import HistoricalScenario,run_historical_scenario
from prosper_or_perish_constructor.simulation.behavior_acceptance import evaluate_trajectory
from prosper_or_perish_constructor.simulation.run import Simulation
from prosper_or_perish_constructor.simulation.land_experiments import _totals
from prosper_or_perish_constructor.simulation.cache import fingerprint


def run():
    out=ROOT/'artifacts/data/population_simulation/repair_round_27/urban_food'
    out.mkdir(parents=True,exist_ok=True)
    manifests=[]; cases=[]; budgets=[]
    for name,staff,accommodation in [('unchanged',False,0.),('cookery_staffing',True,0.),
                                   ('accommodation',False,1.),('both',True,1.),
                                   ('accommodation_three',False,3.)]:
        overrides=(*OVERRIDES,f'simulation.staff_existing_cookeries={str(staff).lower()}',
                   f'capacity.urban_allowance_per_observed_worker={accommodation}')
        _,(state,context,prep)=prepare(overrides)
        state=attach_slave_agriculture(state,subsistence_output=context.subsistence_agriculture,hiring_fraction=.75)
        state.write_parquet(out/f'{name}_starting_ledger.parquet')
        _,_,budget=diagnose_provincial_food(state,context)
        budgets.append(budget.with_columns(pl.lit(name).alias('candidate')))
        provinces=state.filter(pl.col('location_tag').is_in(TAGS))['province'].unique().to_list()
        selected=state.filter(pl.col('province').is_in(provinces))
        history,result=run_historical_scenario(selected,context,HistoricalScenario(name))
        history.write_parquet(out/f'{name}_monthly.parquet')
        for province in provinces:
            checked=evaluate_trajectory(history.filter(pl.col('province')==province),provisioned=True)
            for horizon in checked['horizons']:
                passed=all(c['passed'] for c in checked['checks'] if c.get('horizon',horizon['year'])==horizon['year'])
                cases.append({'candidate':name,'province':province,**horizon,'status':'passed' if passed else 'failed'})
        sim=Simulation(state,context);annual=[];checkpoints=[]
        for year in range(201):
            if year:sim.run(12,progress=False,materialize=False)
            sim.evaluate_food_budget();snapshot=sim.diagnostic_state()
            annual.append(_totals(snapshot,year))
            if year in (0,25,100,200):checkpoints.append(snapshot.with_columns(pl.lit(year).alias('year')))
        pl.concat(annual,how='diagonal_relaxed').write_parquet(out/f'{name}_annual_world.parquet')
        pl.concat(checkpoints,how='diagonal_relaxed').write_parquet(out/f'{name}_all_location_checkpoints.parquet')
        manifests.append({'name':name,'overrides':overrides,'preparation':prep,'monthly_accounting':result,
            'cookery_hires':float(state['candidate_cookery_hires'].sum()) if staff else 0.,
            'urban_flat_allowance':float(state['candidate_urban_accommodation'].sum()) if accommodation else 0.})
        print('Finished world and regional comparison',name,flush=True)
    pl.DataFrame(cases).write_csv(out/'viability_criteria.csv')
    pl.concat(budgets,how='diagonal_relaxed').write_csv(out/'all_provincial_food_budgets.csv')
    identity=fingerprint([Path(__file__),ROOT/'src/prosper_or_perish_constructor/simulation'],{'candidates':manifests,'horizons':[100,200]})
    (out/'manifest.json').write_text(json.dumps({'accepted':False,'fingerprint':identity,'candidates':manifests,
        'contract':'Existing cookeries hire available laborers with recipe inputs/wages assumed supplied. Existing victuals market output retained. No new imports, food buildings, agricultural land or population-specific consumption reductions. Accommodation is a separate one-flat-unit-per-observed-urban-worker diagnostic.',
        'coverage':'Every location is simulated annually and at checkpoints. Monthly histories cover 22 complete provinces. Viability is separate from unresolved historical and resource evidence gates.'},indent=2,default=str))


if __name__=='__main__':run()
