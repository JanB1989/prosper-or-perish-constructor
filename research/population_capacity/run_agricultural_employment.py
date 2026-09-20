"""Round 24: explicit agricultural job targets, no free slave consumption."""
import json
import polars as pl
from run_historical_direct import ROOT,prepare
from prosper_or_perish_constructor.simulation.agricultural_employment import attach_slave_agriculture
from prosper_or_perish_constructor.simulation.run import Simulation
from prosper_or_perish_constructor.simulation.food_diagnosis import diagnose_provincial_food
from prosper_or_perish_constructor.simulation.land_experiments import _totals

def run(fractions=(0.,.5,1.),output_name="employment_reserved"):
    if not output_name.replace("_","").isalnum():raise ValueError("invalid output name")
    out=ROOT/'artifacts/data/population_simulation/repair_round_24'/output_name;out.mkdir(parents=True,exist_ok=True)
    _,(initial,context,prep)=prepare(('capacity.development_relative=0.05',
       'paths.active_modifier_ledger="artifacts/data/population_simulation/repair_round_23/active_modifiers/active_modifier_ledger.parquet"'))
    histories=[];checkpoints=[];budgets=[]
    for fraction in fractions:
        state=attach_slave_agriculture(initial,subsistence_output=context.subsistence_agriculture,hiring_fraction=fraction)
        state.write_parquet(out/f'starting_jobs_{fraction:g}.parquet')
        _,_,budget=diagnose_provincial_food(state,context)
        budgets.append(budget.with_columns(pl.lit(fraction).alias('hiring_fraction')))
        sim=Simulation(state,context)
        for year in range(201):
            if year:sim.run(12,progress=False,materialize=False)
            sim.evaluate_food_budget();d=sim.diagnostic_state()
            histories.append(_totals(d,year).with_columns(pl.lit(fraction).alias('hiring_fraction')))
            if year in (0,25,100,200):checkpoints.append(d.with_columns(pl.lit(year).alias('year'),pl.lit(fraction).alias('hiring_fraction')))
        print('finished agricultural jobs',fraction,flush=True)
    pl.concat(histories,how='diagonal_relaxed').write_parquet(out/'annual_history.parquet')
    pl.concat(checkpoints,how='diagonal_relaxed').write_parquet(out/'checkpoints.parquet')
    pl.concat(budgets,how='diagonal_relaxed').write_csv(out/'starting_food_budgets.csv')
    (out/'manifest.json').write_text(json.dumps({'accepted':False,'preparation':prep,
       'scenario':'Proposed staffed agricultural employment for slaves; fixed infrastructure and jobs, native consumption unchanged.',
       'shared_parameters':{'food_per_worker':context.subsistence_agriculture,'jobs_per_agricultural_support_unit':1.,'hiring_fractions':list(fractions)},
       'limits':'Existing employed peasants/slaves also reserve land conservatively; initial subsistence peasants reserved; no future opportunity or added capacity. Job-land conversion is a balance assumption requiring sensitivity, not measured historical employment.',
       'game_integration':'Later building pass must implement equivalent staffed food production and employment. This scenario is not current observed production.'},indent=2,default=str))
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--fractions',nargs='+',type=float,default=[0.,.5,1.]);parser.add_argument('--output-name',default='employment_reserved')
    args=parser.parse_args();run(tuple(args.fractions),args.output_name)
