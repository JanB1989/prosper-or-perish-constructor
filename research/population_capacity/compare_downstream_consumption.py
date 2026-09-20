"""Hold geography/subsistence fixed while testing downstream household demand."""
import json
import hashlib
from pathlib import Path
import polars as pl
from run_historical_direct import ROOT, OUTPUT, prepare
from prosper_or_perish_constructor.simulation.scenarios import apply_mechanics_overrides, URBAN_FOOD_TYPES
from prosper_or_perish_constructor.simulation.run import Simulation

def run():
 p,(state,context,prep)=prepare(('capacity.development_relative=0.05',))
 provinces=state.filter(pl.col('location_tag').is_in(['wuxian','jiaxing','huating','angkor','cairo','alexandria']))['province'].unique().to_list()
 state=state.filter(pl.col('province').is_in(provinces));initial=[];snapshots=[]
 for factor in (1.,.85,.7):
  ctx=apply_mechanics_overrides(context,{'urban_food_consumption_multiplier':factor})
  sim=Simulation(state,ctx);sim.evaluate_food_budget()
  sim.state=sim.state.with_columns((pl.col('last_food_consumption')*12).alias('food'))
  columns=[c for c in sim.state.columns if c.startswith('food_consumption__')]
  initial.append(sim.state.select('location_tag','province','total_population','local_population_capacity',
   'subsistence_surplus','subsistence_food_production','peasant_food_consumption',
   'food_production','last_food_consumption','food_balance',*columns).with_columns(pl.lit(factor).alias('urban_consumption_multiplier')))
  last=0
  for year in (0,25,100,200,300,400,500):
   sim.run((year-last)*12,progress=False,materialize=False);last=year
   sim.evaluate_food_budget()
   snapshots.append(sim.diagnostic_state().with_columns(pl.lit(year).alias('year'),pl.lit(factor).alias('urban_consumption_multiplier')))
  print('Completed downstream factor',factor,flush=True)
 out=OUTPUT/'downstream_consumption';out.mkdir(parents=True,exist_ok=True)
 first=pl.concat(initial,how='diagonal_relaxed');first.write_parquet(out/'starting_location_budgets.parquet')
 totals=first.group_by('province','urban_consumption_multiplier').agg(pl.exclude('location_tag','province','urban_consumption_multiplier').sum()).sort('province','urban_consumption_multiplier')
 totals.write_csv(out/'starting_province_budgets.csv')
 pl.concat(snapshots,how='diagonal_relaxed').write_parquet(out/'checkpoints.parquet')
 (out/'manifest.json').write_text(json.dumps({'status':'downstream sensitivity experiment; not accepted balance',
  'factors':[1,.85,.7],'affected_types':sorted(URBAN_FOOD_TYPES),'fixed':'all geography, infrastructure, development coefficient, peasant consumption, subsistence production',
  'preparation':prep,'input_file_hashes':{str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in [Path(__file__),p.historical_assignments_path,ROOT/'src/prosper_or_perish_constructor/simulation/scenarios.py',ROOT/'src/prosper_or_perish_constructor/simulation/numpy_engine.py']},'stock_months':12,'checkpoints':[0,25,100,200,300,400,500]},indent=2,default=str))
 print(totals.select('province','urban_consumption_multiplier','subsistence_surplus','food_balance'))
if __name__=='__main__':run()
