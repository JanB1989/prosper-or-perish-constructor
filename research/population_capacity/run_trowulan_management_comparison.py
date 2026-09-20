"""Isolate the dated Trowulan assessment with existing land and food buildings."""
import json
import numpy as np
import polars as pl
from run_historical_direct import ROOT,prepare
from run_acceptance_round_25 import OVERRIDES
from prosper_or_perish_constructor.simulation.agricultural_employment import attach_slave_agriculture
from prosper_or_perish_constructor.simulation.historical_scenarios import HistoricalScenario,run_historical_scenario
from prosper_or_perish_constructor.simulation.behavior_acceptance import evaluate_trajectory
from prosper_or_perish_constructor.simulation.food_diagnosis import diagnose_provincial_food
from prosper_or_perish_constructor.simulation.cache import fingerprint


def run():
    out=ROOT/'artifacts/data/population_simulation/repair_round_28/trowulan_management'
    out.mkdir(parents=True,exist_ok=True)
    states=[];reports=[];budgets=[]
    for name,extra in [('baseline',()),('dated_management',('paths.historical_assignments="research/population_capacity/historical_assignments_round_28.json"',))]:
        _,(state,context,prep)=prepare((*OVERRIDES,*extra))
        state=attach_slave_agriculture(state,subsistence_output=context.subsistence_agriculture,hiring_fraction=.75)
        states.append(state.sort('location_tag'))
        selected=state.filter(pl.col('province')=='trowulan_province')
        selected.write_parquet(out/f'{name}_starting_ledger.parquet')
        _,_,budget=diagnose_provincial_food(selected,context)
        budgets.append(budget.with_columns(pl.lit(name).alias('candidate')))
        history,_=run_historical_scenario(selected,context,HistoricalScenario(name))
        history.write_parquet(out/f'{name}_monthly.parquet')
        reports.append({'candidate':name,'preparation':prep,'viability':evaluate_trajectory(history,provisioned=True)})
    comparisons=('development','local_population_capacity','infrastructure_population_capacity','crop_fallow_block_km2')
    unchanged=all(np.allclose(states[0].filter(pl.col('location_tag')!='trowulan')[c].to_numpy(),
        states[1].filter(pl.col('location_tag')!='trowulan')[c].to_numpy()) for c in comparisons)
    land_unchanged=np.allclose(states[0]['crop_fallow_block_km2'].to_numpy(),states[1]['crop_fallow_block_km2'].to_numpy())
    if not unchanged or not land_unchanged:raise ValueError('management experiment changed neighbouring assignments or cultivated extent')
    pl.concat(budgets,how='diagonal_relaxed').write_csv(out/'provincial_food_budgets.csv')
    files=[ROOT/'src/prosper_or_perish_constructor/simulation',__file__,
        ROOT/'research/population_capacity/historical_assignments_round_28.json',ROOT/'research/population_capacity/trowulan_water_management_evidence.json']
    (out/'manifest.json').write_text(json.dumps({'accepted':False,'fingerprint':fingerprint(files,{'reports':reports}),
        'neighbouring_assignments_unchanged':bool(unchanged),'cultivated_extent_unchanged':bool(land_unchanged),'candidates':reports},indent=2,default=str))
    print(json.dumps([{'candidate':r['candidate'],'status':r['viability']['status'],'horizons':r['viability']['horizons']} for r in reports],indent=2))


if __name__=='__main__':run()
