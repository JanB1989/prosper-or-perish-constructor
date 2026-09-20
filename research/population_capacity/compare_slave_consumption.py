"""User-requested downstream slave-demand probes; no accepted balance change."""
from dataclasses import replace
import json
import polars as pl
from run_historical_direct import ROOT,prepare
from prosper_or_perish_constructor.simulation.run import Simulation
from prosper_or_perish_constructor.simulation.land_experiments import _totals
from prosper_or_perish_constructor.simulation.food_diagnosis import diagnose_provincial_food

def run():
    out=ROOT/'artifacts/data/population_simulation/repair_round_23/slave_consumption';out.mkdir(parents=True,exist_ok=True)
    _,(state,context,prep)=prepare(('capacity.development_relative=0.05',
      'paths.active_modifier_ledger="artifacts/data/population_simulation/repair_round_23/active_modifiers/active_modifier_ledger.parquet"'))
    starting=state.group_by('province').agg(pl.col('total_population').sum().alias('initial_population'),pl.col('population_slaves').sum().alias('initial_slaves'))
    parts=[];histories=[];budgets=[]
    for multiplier in (1.,.5,0.):
        rates=dict(context.pop_food_rates);rates['slaves']*=multiplier
        ctx=replace(context,pop_food_rates=rates)
        _,_,budget=diagnose_provincial_food(state,ctx)
        budgets.append(budget.with_columns(pl.lit(multiplier).alias('slave_consumption_multiplier')))
        sim=Simulation(state,ctx)
        for year in range(201):
            if year:sim.run(12,progress=False,materialize=False)
            sim.evaluate_food_budget();d=sim.diagnostic_state()
            histories.append(_totals(d,year).with_columns(pl.lit(multiplier).alias('slave_consumption_multiplier')))
            if year in (0,25,100,200):
                parts.append(d.with_columns(pl.lit(year).alias('year'),pl.lit(multiplier).alias('slave_consumption_multiplier')))
        print('finished slave demand',multiplier,flush=True)
    frames=pl.concat(parts,how='diagonal_relaxed');frames.write_parquet(out/'checkpoints.parquet')
    pl.concat(histories,how='diagonal_relaxed').write_parquet(out/'annual_history.parquet')
    pl.concat(budgets,how='diagonal_relaxed').write_csv(out/'starting_food_budgets.csv')
    provinces=frames.group_by('province','year','slave_consumption_multiplier').agg(pl.col('total_population').sum(),pl.col('population_slaves').sum(),pl.col('food_balance').sum())
    original=provinces.filter(pl.col('slave_consumption_multiplier')==1.).select('province','year',pl.col('total_population').alias('unchanged_population'))
    provinces.join(original,on=['province','year']).join(starting,on='province').with_columns(
        (pl.col('total_population')-pl.col('unchanged_population')).alias('population_change_vs_unchanged'),
        (pl.col('initial_slaves')>0).alias('direct_beneficiary')).write_csv(out/'all_province_comparison.csv')
    (out/'manifest.json').write_text(json.dumps({'accepted':False,'scope':'all locations; every province reported',
        'mechanism':'Only base slave consumption changes. Slaves still produce no subsistence. No other population coefficient changes.',
        'starting_conditions':'Identical population, development, infrastructure, employment and absolute food stocks in all cases.',
        'scenarios':[1.,.5,0.],'required_horizons':[100,200],'preparation':prep,
        'zero_demand_limitation':'Food-free survival is a mechanics bound, not evidence of historical self-provisioning or an accepted policy.'},indent=2,default=str))
if __name__=='__main__':run()
