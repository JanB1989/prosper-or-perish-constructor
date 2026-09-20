"""Long-run direct-capacity heartland trials; no automatic investment or trade."""
from pathlib import Path
from dataclasses import replace
import json
import numpy as np
import polars as pl
from run_historical_direct import prepare, ROOT, OUTPUT
from prosper_or_perish_constructor.simulation.historical_model import attach_historical_model, load_assignments
from prosper_or_perish_constructor.simulation.physical_support import PhysicalSupportTransform
from prosper_or_perish_constructor.simulation.run import Simulation
from prosper_or_perish_constructor.simulation.cache import fingerprint
from prosper_or_perish_constructor.simulation.land_experiments import _totals
from prosper_or_perish_constructor.simulation.scenarios import run_food_scenarios
YEARS=(0,25,100,200,300,400,500)

def run():
 p,(direct,context,prep)=prepare()
 baseline=pl.read_parquet(ROOT/'artifacts/data/population_simulation/repair_round_20/starting_ledger.parquet')
 provinces=baseline.filter(pl.col('location_tag').is_in(['wuxian','jiaxing','huating','angkor','cairo','alexandria']))['province'].unique().to_list()
 baseline=baseline.filter(pl.col('province').is_in(provinces))
 candidates=pl.read_parquet(p.candidates_path); assignments=load_assignments(p.historical_assignments_path)
 transform=PhysicalSupportTransform(scale=p.gaez_zero_development_fraction,area_exponent=p.location_area_exponent,
  reference_area_km2=p.location_area_reference_km2,people_per_game_unit=p.people_per_game_unit)
 out=OUTPUT/'long_run';out.mkdir(parents=True,exist_ok=True)
 summary=[];histories=[];gates=[]
 for coefficient in (.025,.05):
  formula=replace(context.capacity_model,development_relative=coefficient)
  for uncertainty in (0.,.5,1.):
   state,ledger=attach_historical_model(baseline,candidates,assignments=assignments,transform=transform,formula=formula,uncertainty=uncertainty)
   ctx=replace(context,capacity_model=formula)
   for frozen in (False,True):
    name=f'dev_{coefficient:g}_uncertainty_{uncertainty:g}_'+('frozen' if frozen else 'coupled')
    sim=Simulation(state,ctx);sim.evaluate_food_budget()
    # All comparisons begin with twelve months of their actual consumption.
    sim.state=sim.state.with_columns((pl.col('last_food_consumption')*12.).alias('food'))
    starting_dev=sim._engine.development.copy()
    monthly=[];checks=[]
    for month in range(6001):
     if month:
      sim.run(1,progress=False,materialize=False)
      if frozen: sim._engine.development=starting_dev.copy()
     if month%12==0 or uncertainty==.5:
      sim.evaluate_food_budget(); d=sim.diagnostic_state().with_columns(pl.lit(month).alias('month'),pl.lit(name).alias('scenario'))
      if uncertainty==.5: monthly.append(d)
      if month%12==0: histories.append(_totals(d,month//12).with_columns(pl.lit(name).alias('scenario')))
      if month//12 in YEARS and month%12==0: checks.append(d.with_columns(pl.lit(month//12).alias('year')))
    checkpoints=pl.concat(checks,how='diagonal_relaxed');checkpoints.write_parquet(out/(name+'_checkpoints.parquet'))
    if monthly: pl.concat(monthly,how='diagonal_relaxed').write_parquet(out/(name+'_monthly.parquet'))
    final=checkpoints.filter(pl.col('year')==500)
    summary.append({'scenario':name,'population_start':float(state['total_population'].sum()),
     'population_end':float(final['total_population'].sum()),'capacity_end':float(final['local_population_capacity'].sum()),
     'mean_development_end':float(final['development'].mean()),'starved_location_months':float(final['starvation_months'].sum()),
     'area_conflict_locations':ledger['area_conflict_locations']})
    print(summary[-1],flush=True)
  controls=run_food_scenarios(replace(context,capacity_model=formula),output=out/f'controls_dev_{coefficient:g}',monthly_history=True)
  gates.append({'coefficient':coefficient,'controls':controls})
 pl.DataFrame(summary).write_csv(out/'summary.csv')
 pl.concat(histories,how='diagonal_relaxed').write_parquet(out/'annual_history.parquet')
 (out/'manifest.json').write_text(json.dumps({'model_accepted':False,'game_export_ready':False,
  'scope':'six complete provinces; actual population composition; twelve months of food; fixed employment and infrastructure',
  'candidate_coefficients':[.025,.05],'uncertainty_positions':[0,.5,1],
  'preparation':prep,'controls':gates,
  'fingerprint':fingerprint([Path(__file__),p.historical_assignments_path,ROOT/'src/prosper_or_perish_constructor/simulation']),
  'limitations':['historical area conflicts remain','other mandatory geographic groups and holdouts not evaluated',
   'no autonomous investment, trade or migration; tribal native offsets are user-authorized assumptions']},indent=2,default=str))
if __name__=='__main__':run()
