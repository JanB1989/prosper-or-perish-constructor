"""Canonical world comparison after confirmed available-land fallback correction."""
from pathlib import Path
from dataclasses import replace
import json
import numpy as np
import polars as pl
from prosper_or_perish_constructor.simulation.profile import load_population_simulation_profile, prepare_population_simulation_state
from prosper_or_perish_constructor.simulation.run import Simulation
from prosper_or_perish_constructor.simulation.development import decay_offset, FLAT
from prosper_or_perish_constructor.simulation.capacity_pressure import ABUNDANT_FREE_LAND, AVAILABLE_FREE_LAND, CapacityPressureBand
from prosper_or_perish_constructor.simulation.land_experiments import _totals
from prosper_or_perish_constructor.simulation.cache import fingerprint
ROOT = Path(__file__).resolve().parents[2]
YEARS = (0,25,100,200,300,400,500)
OVERRIDES = ('capacity.gaez_zero_development_fraction=1.5','capacity.location_area_exponent=0.5',
 'capacity.baseline_open_land_access_fraction=0.005','mechanics.subsistence_output=1.25',
 'mechanics.development_monthly_per_point=-0.000025','simulation.initial_food_months=12')


def run():
 p=load_population_simulation_profile(ROOT/'population_capacity_simulation.toml',repo=ROOT,overrides=OVERRIDES)
 state,context,prep=prepare_population_simulation_state(ROOT,ROOT/'constructor.toml',p)
 output=ROOT/'artifacts/data/population_simulation/repair_round_20';output.mkdir(parents=True,exist_ok=True)
 state.write_parquet(output/'starting_ledger.parquet')
 histories=[]; snapshots=[]
 for fraction in (0.,.25,.5):
  bonus=decay_offset(context.prosperity.development_monthly_per_point,fraction)
  bands=dict(context.capacity_pressure)
  for key in (ABUNDANT_FREE_LAND,AVAILABLE_FREE_LAND):
   bands[key]=CapacityPressureBand(key,{**bands[key].effects,FLAT:bands[key].get(FLAT)-bonus})
  initial=state.with_columns(((pl.col(FLAT) if FLAT in state.columns else pl.lit(0.))+bonus).alias(FLAT),pl.lit(True).alias('capacity_experiment_only'))
  sim=Simulation(initial,replace(context,capacity_pressure=bands))
  name=f'decay_compensation_{fraction:g}'
  for year in range(501):
   if year:sim.run(12,progress=False,materialize=False)
   sim.evaluate_food_budget();d=sim.diagnostic_state()
   histories.append(_totals(d,year).with_columns(pl.lit(name).alias('scenario')))
   if year in YEARS:snapshots.append(d.with_columns(pl.lit(year).alias('year'),pl.lit(name).alias('scenario')))
  print('Completed '+name,flush=True)
 h=pl.concat(histories,how='diagonal_relaxed');h.write_parquet(output/'annual_history.parquet')
 pl.concat(snapshots,how='diagonal_relaxed').write_parquet(output/'checkpoints.parquet')
 h.filter(pl.col('year').is_in(YEARS)).write_csv(output/'comparison.csv')
 manifest={'accepted':False,'overrides':OVERRIDES,'compensation_fractions':[0,.25,.5],
  'boundary_evidence':'User confirmed 2026-09-07: available free land applies below capacity whenever abundant conditions fail.',
  'preparation':prep,'limitations':['direct building staffing and activation of advances/other country modifiers incomplete',
  'unchanged geography; no construction, trade, migration or promotion; no historical acceptance claimed'],
  'fingerprint':fingerprint([Path(__file__),ROOT/'src/prosper_or_perish_constructor/simulation'],{'preparation':prep,'overrides':OVERRIDES})}
 (output/'manifest.json').write_text(json.dumps(manifest,indent=2,default=str))
 print(h.filter((pl.col('year')==500)&pl.col('scope_key').is_in(['world','east_asia','south_east_asia'])))
if __name__=='__main__':run()
