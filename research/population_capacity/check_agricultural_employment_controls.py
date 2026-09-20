"""Monthly Patna stock and crop-loss controls for the proposed employment target."""
import json
import polars as pl
from run_historical_direct import ROOT,prepare
from prosper_or_perish_constructor.simulation.agricultural_employment import attach_slave_agriculture
from prosper_or_perish_constructor.simulation.run import Simulation
from prosper_or_perish_constructor.simulation.numpy_engine import numpy_state_from_polars

def run(fraction=.5):
 out=ROOT/f'artifacts/data/population_simulation/repair_round_24/employment_controls_{fraction:g}';out.mkdir(parents=True,exist_ok=True)
 _,(state,context,prep)=prepare(('capacity.development_relative=0.05',
   'paths.active_modifier_ledger="artifacts/data/population_simulation/repair_round_23/active_modifiers/active_modifier_ledger.parquet"'))
 state=attach_slave_agriculture(state.filter(pl.col('province')=='patna_province'),subsistence_output=context.subsistence_agriculture,hiring_fraction=fraction)
 histories=[];results=[]
 for stock in (0,3,12,24):
  for shock in (False,True):
   engine=numpy_state_from_polars(state,context);_,cons,*_=engine.calculate_food_budget()
   initial=state.with_columns(pl.Series('food',cons*stock));sim=Simulation(initial,context)
   p0=float(initial['total_population'].sum());d0=float(initial['development'].mean());name=f'stock_{stock}_shock_{shock}'
   for month in range(2401):
    if month in (301,313) and shock:
     sim._engine.extras_float['candidate_agriculture_food_per_worker__slaves'][:]=context.subsistence_agriculture*(.5 if month==301 else 1.)
    if month:sim.run(1,progress=False,materialize=False)
    sim.evaluate_food_budget();d=sim.diagnostic_state();histories.append(d.with_columns(pl.lit(name).alias('scenario'),pl.lit(month).alias('month')))
    if month==12:startup=d['unmet_food_months'].sum()
    if month in (1200,2400):
     p=float(d['total_population'].sum());dev=float(d['development'].mean());unmet=float(d['unmet_food_months'].sum()-startup)
     results.append({'scenario':name,'year':month//12,'population_retention':p/p0,'development_retention':dev/d0,
       'unmet_location_months_after_startup':unmet,'peaceful_control':not shock,
       'peaceful_gate_passed':p/p0>=.9 and dev/d0>=.9 and unmet==0 if not shock else None})
 pl.concat(histories,how='diagonal_relaxed').write_parquet(out/'monthly_history.parquet')
 (out/'results.json').write_text(json.dumps({'model_accepted':False,'preparation':prep,'results':results,
   'shock':'Half the proposed agricultural food output for 12 months starting year 25; staffing and consumption unchanged.'},indent=2,default=str))
 print(results)
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--fraction',type=float,default=.5)
 run(parser.parse_args().fraction)
