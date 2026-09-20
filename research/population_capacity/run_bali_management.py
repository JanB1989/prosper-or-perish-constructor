"""Frozen historical-management experiment with neighbouring island controls."""
import json
import polars as pl
from run_historical_direct import ROOT,prepare
from prosper_or_perish_constructor.simulation.run import Simulation

def run():
 out=ROOT/'artifacts/data/population_simulation/repair_round_24/bali';out.mkdir(parents=True,exist_ok=True)
 histories=[];starts=[];manifests=[]
 for name,extra in [('unchanged',()),*[(f'evidence_{q}',('paths.historical_assignments="research/population_capacity/historical_assignments_round_24.json"',f'capacity.historical_uncertainty={q}')) for q in (0.,.5,1.)]]:
    _,(state,context,prep)=prepare(('capacity.development_relative=0.05',*extra))
    state=state.filter(pl.col('province')=='bali_province')
    starts.append(state.with_columns(pl.lit(name).alias('scenario')))
    manifests.append({'scenario':name,'preparation':prep})
    sim=Simulation(state,context)
    for month in range(2401):
        if month:sim.run(1,progress=False,materialize=False)
        sim.evaluate_food_budget();histories.append(sim.diagnostic_state().with_columns(pl.lit(name).alias('scenario'),pl.lit(month).alias('month')))
    print('finished Bali',name,flush=True)
 pl.concat(starts,how='diagonal_relaxed').write_parquet(out/'starting_ledger.parquet')
 pl.concat(histories,how='diagonal_relaxed').write_parquet(out/'monthly_history.parquet')
 (out/'manifest.json').write_text(json.dumps({'accepted':False,'scenarios':manifests,
    'preregistered_comparison':'Bali management and water-served share, fixed cultivated extent. Lombok/Sasak unassigned; provincial sharing can change their food outcomes. Global uncertainty endpoints also vary inferred management in controls, explicitly recorded.',
    'criteria':'Zero physical conflicts; unchanged hectares and neighbouring capacities at nominal uncertainty; evaluate 100/200-year trajectories without fitting against population.'},indent=2,default=str))
if __name__=='__main__':run()
