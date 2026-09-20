"""World diagnostic for direct magnitudes; no model/export acceptance claim."""
from pathlib import Path
import json
import polars as pl
from run_historical_direct import prepare, ROOT, OUTPUT
from prosper_or_perish_constructor.simulation.run import Simulation
from prosper_or_perish_constructor.simulation.land_experiments import _totals
from prosper_or_perish_constructor.simulation.model_acceptance import evaluate_model_acceptance
from prosper_or_perish_constructor.simulation.cache import fingerprint

def run():
 p,(state,context,prep)=prepare(('capacity.development_relative=0.05',))
 output=OUTPUT/'world';output.mkdir(parents=True,exist_ok=True)
 inputs=fingerprint([Path(__file__),p.historical_assignments_path,ROOT/'src/prosper_or_perish_constructor/simulation'],{'preparation':prep})
 state.write_parquet(output/'starting_ledger.parquet')
 sim=Simulation(state,context);history=[];snapshots={}
 for year in range(501):
  if year: sim.run(12,progress=False,materialize=False)
  sim.evaluate_food_budget();d=sim.diagnostic_state()
  history.append(_totals(d,year))
  if year in (0,25,100,200,300,400,500):
   snapshots[year]=d
   print(year,float(d['total_population'].sum()),float(d['local_population_capacity'].sum()),flush=True)
 pl.concat(history,how='diagonal_relaxed').write_parquet(output/'annual_history.parquet')
 pl.concat([d.with_columns(pl.lit(y).alias('year')) for y,d in snapshots.items()],how='diagonal_relaxed').write_parquet(output/'checkpoints.parquet')
 acceptance=evaluate_model_acceptance({**snapshots,0:state})
 manifest={'preparation':prep,'acceptance':acceptance,'fingerprint':inputs,
  'scope':'actual world composition; 12 months starting food; frozen infrastructure; coupled development; no trade/migration/investment',
  'coefficient':.05,'model_accepted':acceptance['model_accepted'],'game_export_ready':False}
 (output/'manifest.json').write_text(json.dumps(manifest,indent=2,default=str))
if __name__=='__main__':run()
