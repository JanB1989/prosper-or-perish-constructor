"""Paired geographical control: identical land and people, pure rural subsistence."""
import json
import polars as pl
from run_historical_direct import ROOT,prepare
from prosper_or_perish_constructor.simulation.run import Simulation
from prosper_or_perish_constructor.simulation.land_experiments import _totals
from prosper_or_perish_constructor.simulation.numpy_engine import numpy_state_from_polars

def run():
 out=ROOT/'artifacts/data/population_simulation/repair_round_24/subsistence_geography';out.mkdir(parents=True,exist_ok=True)
 _,(state,context,prep)=prepare(('capacity.development_relative=0.05',
     'paths.active_modifier_ledger="artifacts/data/population_simulation/repair_round_23/active_modifiers/active_modifier_ledger.parquet"'))
 types=('peasants','tribesmen','slaves','nobles','clergy','burghers','laborers','soldiers','unknown')
 zero=[c for c in state.columns if c.startswith(('staffed_food__','observed_employment__','staffed_building_','unconditionally_active_building_')) or c in ('building_food_output','unstaffed_building_food_output','rgo_food_output','net_food_imports','production_food_inputs','employed_peasants','peasant_employment')]
 state=state.with_columns(*[pl.lit(0.).alias(c) for c in zero],
    *[(pl.col('total_population') if kind=='peasants' else pl.lit(0.)).alias('population_'+kind) for kind in types],
    pl.col('total_population').alias('unemployed_peasants'),pl.lit('rural_settlement').alias('location_rank'))
 engine=numpy_state_from_polars(state,context);_,cons,*_=engine.calculate_food_budget()
 state=state.with_columns(pl.Series('food',cons*12))
 state.write_parquet(out/'starting_ledger.parquet')
 sim=Simulation(state,context);rows=[];checkpoints=[]
 for year in range(201):
    if year:sim.run(12,progress=False,materialize=False)
    sim.evaluate_food_budget();d=sim.diagnostic_state();rows.append(_totals(d,year))
    if year in (0,25,100,200):checkpoints.append(d.with_columns(pl.lit(year).alias('year')))
 pl.concat(rows,how='diagonal_relaxed').write_parquet(out/'annual_history.parquet')
 pl.concat(checkpoints,how='diagonal_relaxed').write_parquet(out/'checkpoints.parquet')
 (out/'manifest.json').write_text(json.dumps({'accepted':False,'preparation':prep,
    'comparison':'Same initial total population, geography, capacity and development; all people are unemployed rural peasants. Building/RGO food and building development removed; starting stock 12 months of this scenario consumption.',
    'role':'Agricultural mechanism diagnostic; not a historical population reassignment.'},indent=2,default=str))
 print(pl.concat(rows,how='diagonal_relaxed').filter(pl.col('scope_key').is_in(['world','east_asia','south_east_asia','south_asia'])&pl.col('year').is_in([0,100,200])))
if __name__=='__main__':run()
