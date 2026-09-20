"""Round 23: canonical world run with observed country effects and 100/200 gates."""
from pathlib import Path
import json
import polars as pl
from run_historical_direct import ROOT,prepare
from prosper_or_perish_constructor.simulation.run import Simulation
from prosper_or_perish_constructor.simulation.land_experiments import _totals
from prosper_or_perish_constructor.simulation.cache import fingerprint

def run(output_name="world"):
    if not output_name.replace("_", "").replace("-", "").isalnum():
        raise ValueError("output_name must be a simple directory name")
    extra=('capacity.development_relative=0.05',
      'paths.active_modifier_ledger="artifacts/data/population_simulation/repair_round_23/active_modifiers/active_modifier_ledger.parquet"')
    p,(state,context,prep)=prepare(extra)
    out=ROOT/'artifacts/data/population_simulation/repair_round_23'/output_name;out.mkdir(parents=True,exist_ok=True)
    state.write_parquet(out/'starting_ledger.parquet')
    source=fingerprint([Path(__file__),ROOT/'src/prosper_or_perish_constructor/simulation'],{'preparation':prep,'overrides':extra})
    sim=Simulation(state,context);histories=[];snapshots=[]
    for year in range(201):
        if year:sim.run(12,progress=False,materialize=False)
        sim.evaluate_food_budget();d=sim.diagnostic_state()
        histories.append(_totals(d,year))
        if year in (0,25,100,200):snapshots.append(d.with_columns(pl.lit(year).alias('year')))
    pl.concat(histories,how='diagonal_relaxed').write_parquet(out/'annual_history.parquet')
    pl.concat(snapshots,how='diagonal_relaxed').write_parquet(out/'checkpoints.parquet')
    (out/'manifest.json').write_text(json.dumps({'model_accepted':False,'required_horizons':[100,200],
      'preparation':prep,'fingerprint':source,'limitations':'Current historical assignments remain unresolved; broader modifier scopes are not automatically applied.'},indent=2,default=str))
    print(prep['active_country_modifiers'])
    print(pl.concat(histories,how='diagonal_relaxed').filter(pl.col('scope_key').is_in(['world','east_asia','south_east_asia'])&pl.col('year').is_in([0,100,200])))
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--output-name',default='world')
    run(parser.parse_args().output_name)
