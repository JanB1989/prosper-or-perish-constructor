"""Observed Angkor ricefield-area sensitivity, not an accepted 1337 assignment."""
from pathlib import Path
import json
import polars as pl
from prosper_or_perish_constructor.simulation.profile import load_population_simulation_profile, prepare_population_simulation_state
from prosper_or_perish_constructor.simulation.historical_cultivation import apply_cultivated_area_evidence
from prosper_or_perish_constructor.simulation.run import Simulation
from prosper_or_perish_constructor.simulation.cache import fingerprint
ROOT=Path(__file__).resolve().parents[2]
OVERRIDES=('capacity.gaez_zero_development_fraction=1.5','capacity.location_area_exponent=0.5','capacity.baseline_open_land_access_fraction=0.005','mechanics.subsistence_output=1.25','mechanics.development_monthly_per_point=-0.000025','simulation.initial_food_months=12')
YEARS=(0,25,100,200,300,400,500)


def run():
 p=load_population_simulation_profile(ROOT/'population_capacity_simulation.toml',repo=ROOT,overrides=OVERRIDES)
 world,context,prep=prepare_population_simulation_state(ROOT,ROOT/'constructor.toml',p)
 province=world.filter(pl.col('location_tag')=='angkor')['province'].item()
 state=world.filter(pl.col('province')==province).sort('location_tag')
 output=ROOT/'artifacts/data/population_simulation/repair_round_21_angkor';output.mkdir(parents=True,exist_ok=True)
 histories=[];events=[]
 for area in (None,500.,1000.):
  name='baseline' if area is None else f'cultivated_{area:g}_km2'
  initial=state
  if area is not None:
   evidence=pl.DataFrame({'location_tag':['angkor'],'cultivated_area_km2':[area],
      'evidence_id':['klassen_2021_ricefields; approximate Angkor crosswalk; maintained-area sensitivity']})
   initial,event=apply_cultivated_area_evidence(state,evidence,formula=p.capacity_formula)
   events.append(event.with_columns(pl.lit(name).alias('scenario')))
  sim=Simulation(initial,context)
  for month in range(6001):
   if month:sim.run(1,progress=False,materialize=False)
   sim.evaluate_food_budget();histories.append(sim.diagnostic_state().with_columns(pl.lit(name).alias('scenario'),pl.lit(month).alias('month')))
  print('Completed '+name,flush=True)
 h=pl.concat(histories,how='diagonal_relaxed');h.write_parquet(output/'monthly_locations.parquet')
 pl.concat(events,how='diagonal_relaxed').write_csv(output/'land_events.csv')
 t=h.filter(pl.col('month').is_in([y*12 for y in YEARS])).group_by('scenario','month').agg(pl.col('total_population','local_population_capacity','starvation_months').sum(),pl.col('development').mean().alias('mean_development')).sort('scenario','month')
 t.write_csv(output/'totals.csv')
 manifest={'accepted':False,'source':'https://doi.org/10.1007/s10816-021-09535-5','source_observation':'>1000 km2 historical ricefields in Angkor Metropolitan Area',
  'source_period':[889,1300],'target_year':1337,'cultivated_area_scenarios_km2':[500,1000],
  'crosswalk':'existing dedicated Angkor-location catchment approximation; equal area is not independently verified polygon overlap',
  'limitations':['500 km2 is a half-maintenance sensitivity, not a measured historical area','1000 km2 is a conservative field-trace quantity, not proof all fields were maintained in 1337',
   'no additional yield, crop-frequency, development or water-reliability bonus','no legal building-level assignment or acceptance; whole food-sharing province retained'],
  'preparation':prep,'overrides':OVERRIDES,'fingerprint':fingerprint([Path(__file__),ROOT/'src/prosper_or_perish_constructor/simulation'],{'preparation':prep,'overrides':OVERRIDES})}
 (output/'manifest.json').write_text(json.dumps(manifest,indent=2,default=str))
 print(t.filter(pl.col('month').is_in([0,6000])).write_csv())
if __name__=='__main__':run()
