"""Factorial heartland food budgets, using the canonical direct model and engine.

No capacity is selected from population. Pressure-zero is a diagnostic bound only.
"""
from pathlib import Path
from dataclasses import replace
import json
import numpy as np
import polars as pl
from run_historical_direct import prepare, ROOT, OUTPUT
from prosper_or_perish_constructor.simulation.historical_model import attach_historical_model, load_assignments
from prosper_or_perish_constructor.simulation.physical_support import PhysicalSupportTransform
from prosper_or_perish_constructor.simulation.run import Simulation

COEFFICIENTS=(.00125,.01,.025,.05)
METRICS=['total_population','local_population_capacity','food_production','last_food_consumption','food_balance',
 'subsistence_food_production','peasant_food_consumption','realized_building_food','rgo_food_output','employed_peasants','unemployed_peasants']

def run():
 p,(direct,context,metadata)=prepare()
 baseline=pl.read_parquet(ROOT/'artifacts/data/population_simulation/repair_round_20/starting_ledger.parquet')
 provinces=baseline.filter(pl.col('location_tag').is_in(['wuxian','jiaxing','huating','angkor','cairo','alexandria']))['province'].unique().to_list()
 baseline=baseline.filter(pl.col('province').is_in(provinces))
 assignments=load_assignments(p.historical_assignments_path)
 candidates=pl.read_parquet(p.candidates_path)
 transform=PhysicalSupportTransform(scale=p.gaez_zero_development_fraction,area_exponent=p.location_area_exponent,
  reference_area_km2=p.location_area_reference_km2,people_per_game_unit=p.people_per_game_unit)
 rows=[]
 for coefficient in COEFFICIENTS:
  formula=replace(p.capacity_formula,development_relative=coefficient)
  model,_=attach_historical_model(baseline,candidates,assignments=assignments,transform=transform,formula=formula)
  unadjusted_assignments={**assignments, 'systems': []}
  reference,_=attach_historical_model(baseline,candidates,assignments=unadjusted_assignments,transform=transform,formula=formula)
  for name in ['unchanged_baseline','unadjusted_assignments','development_only','infrastructure_only','both']:
   use_dev=name in ('development_only','both')
   use_infra=name in ('infrastructure_only','both')
   initial=model if use_infra else reference
   if name=='unchanged_baseline': initial=baseline
   initial=initial.with_columns(pl.Series('development',model['development'] if use_dev else baseline['development']))
   # Factorial cells share source normalization and coefficient. The archived
   # unchanged baseline is an additional historical comparison, not a factorial cell.
   active_formula=context.capacity_model if name=='unchanged_baseline' else formula
   sim=Simulation(initial,replace(context,capacity_model=active_formula)); sim.evaluate_food_budget()
   result=sim.state.with_columns(pl.lit(name).alias('scenario'),pl.lit(coefficient).alias('development_coefficient'))
   rows.append(result.select('location_tag','province','scenario','development_coefficient','development',*METRICS))
  # Absolute consumption bound: do not use it as a geographical capacity assignment.
  initial=model.with_columns((pl.col('total_population')/1e-6).alias('local_population_capacity'))
  sim=Simulation(initial,replace(context,capacity_model=None));sim.evaluate_food_budget()
  rows.append(sim.state.with_columns(pl.lit('pressure_zero_bound').alias('scenario'),pl.lit(coefficient).alias('development_coefficient')).select('location_tag','province','scenario','development_coefficient','development',*METRICS))
 frame=pl.concat(rows)
 totals=frame.group_by('province','scenario','development_coefficient').agg(pl.col(METRICS).sum(),pl.col('development').mean()).sort('development_coefficient','province','scenario')
 out=OUTPUT;out.mkdir(parents=True,exist_ok=True)
 frame.write_parquet(out/'factorial_locations.parquet');totals.write_csv(out/'factorial_provinces.csv')
 print(totals.filter(pl.col('scenario')=='both').select('province','development_coefficient','local_population_capacity','food_balance'))
if __name__=='__main__':run()
