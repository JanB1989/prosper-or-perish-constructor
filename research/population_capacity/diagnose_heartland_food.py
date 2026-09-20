"""Fixed-state provincial food attribution; pressure probes never fit capacity."""
from dataclasses import replace
from pathlib import Path
import polars as pl
from prosper_or_perish_constructor.simulation.profile import load_population_simulation_profile, prepare_population_simulation_state
from prosper_or_perish_constructor.simulation.run import Simulation
ROOT=Path(__file__).resolve().parents[2]
OVERRIDES=('capacity.gaez_zero_development_fraction=1.5','capacity.location_area_exponent=0.5','capacity.baseline_open_land_access_fraction=0.005','mechanics.subsistence_output=1.25','mechanics.development_monthly_per_point=-0.000025')
p=load_population_simulation_profile(ROOT/'population_capacity_simulation.toml',repo=ROOT,overrides=OVERRIDES)
state,context,prep=prepare_population_simulation_state(ROOT,ROOT/'constructor.toml',p)
tags=['wuxian','wujiang','kunshan','changshu','jiaxing','huating','angkor','cairo','alexandria']
provinces=state.filter(pl.col('location_tag').is_in(tags))['province'].unique().to_list()
state=state.filter(pl.col('province').is_in(provinces));rows=[]
for name,fill in [('actual',None),('pressure_near_zero',1e-6),('pressure_10pct',.1),('pressure_50pct',.5),('pressure_100pct',1.),('pressure_200pct',2.)]:
 initial=state if fill is None else state.with_columns((pl.col('total_population')/fill).alias('local_population_capacity'))
 sim=Simulation(initial,context if fill is None else replace(context,capacity_model=None));sim.evaluate_food_budget()
 rows.append(sim.state.with_columns(pl.lit(name).alias('scenario')))
frame=pl.concat(rows,how='diagonal_relaxed')
output=ROOT/'artifacts/data/population_simulation/repair_round_20/heartlands';output.mkdir(parents=True,exist_ok=True)
frame.write_parquet(output/'fixed_state_locations.parquet')
metrics=['total_population','local_population_capacity','food_production','last_food_consumption','food_balance','subsistence_food_production','peasant_food_consumption','realized_building_food','rgo_food_output','employed_peasants','unemployed_peasants']
totals=frame.group_by('province','scenario').agg(pl.col(metrics).sum(),pl.col('development').mean().alias('mean_development')).sort('province','scenario')
totals.write_csv(output/'province_budgets.csv')
actual=totals.filter(pl.col('scenario')=='actual').select('province',pl.col('food_balance').alias('actual_food_balance'),pl.col('last_food_consumption').alias('actual_consumption'))
minimum=totals.filter(pl.col('scenario')=='pressure_near_zero').select('province',pl.col('food_balance').alias('near_free_land_food_balance'),pl.col('last_food_consumption').alias('near_free_land_consumption'))
actual.join(minimum,on='province',validate='1:1').with_columns(
 (pl.col('actual_consumption')-pl.col('near_free_land_consumption')).alias('consumption_recoverable_through_pressure'),
 (-pl.col('near_free_land_food_balance')).clip(lower_bound=0.).alias('deficit_remaining_even_near_free_land'),
 pl.lit('diagnostic lower-pressure limit; no physical capacity assignment or population fitting').alias('interpretation'),
).write_csv(output/'capacity_only_food_limits.csv')
print(totals)
