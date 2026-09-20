"""Paired population/stock perturbations at native fixed-system equilibria."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import numpy as np
import polars as pl
from run_historical_direct import ROOT, prepare
from prosper_or_perish_constructor.simulation.scenarios import FoodScenario, scenario_frame
from prosper_or_perish_constructor.simulation.equilibrium_controls import measure_subsistence_equilibria
from prosper_or_perish_constructor.simulation.historical_scenarios import HistoricalScenario, configure_historical_scenario
from prosper_or_perish_constructor.simulation.numpy_engine import numpy_state_from_polars
from prosper_or_perish_constructor.simulation.behavior_acceptance import compare_recovery
from prosper_or_perish_constructor.simulation.cache import fingerprint


def run(recipe_path,output):
    recipe=json.loads(recipe_path.read_text())
    _,(_,context,prep)=prepare(recipe['overrides'])
    reference=json.loads((ROOT/recipe['reference_manifest']).read_text())
    if prep['model_input_fingerprint']!=reference['preparation']['model_input_fingerprint']:
        raise ValueError('Recovery recipe differs from its acceptance candidate')
    native=HistoricalScenario(**recipe['scenario'])
    for key in ('common_rank_growth','pressure_decay_compensation'):
        if getattr(native,key)!=reference['scenarios'][0][key]:
            raise ValueError('Recovery native configuration differs from acceptance candidate')
    roots=[];specs=[];metadata=[]
    perturbations=[('control',1.,1.),('population_minus_10',.9,1.),('population_plus_10',1.1,1.),
                   ('stocks_half',1.,.5),('stocks_double',1.,2.)]
    for dev in (0.,25.,50.,75.,100.):
        result=measure_subsistence_equilibria(context,development=dev,native_scenario=native)
        roots.append(result)
        if result['status']!='passed' or len(result['population_stock_equilibria'])!=1:
            raise ValueError('A unique measured equilibrium is required before recovery tests')
        eq=result['population_stock_equilibria'][0]
        for name,pop_factor,food_factor in perturbations:
            label=f'D{dev:g}_{name}'
            specs.append(FoodScenario(label,development=dev,fill=eq['fill']*pop_factor,food_months=eq['stock_months']))
            metadata.append(dict(name=label,development=dev,perturbation=name,population_factor=pop_factor,food_factor=food_factor))
    state=scenario_frame(specs,context)
    # Hold absolute initial stocks fixed for population shocks; only stock
    # experiments change that resource. Each D has an identical unshocked pair.
    food=[]
    for i,row in enumerate(metadata):
        control_index=(i//len(perturbations))*len(perturbations)
        food.append(float(state['food'][control_index])*row['food_factor'])
    state=state.with_columns(pl.Series('food',food))
    configured,context=configure_historical_scenario(state,context,native)
    state=configured.with_columns(state['food'])
    engine=numpy_state_from_polars(state,context)
    fixed_dev=engine.development.copy();fixed_prosperity=engine.prosperity.copy()
    rows=[]
    for month in range(2401):
        if month:
            engine.tick_one_month()
            engine.development[:]=fixed_dev
            engine.prosperity[:]=fixed_prosperity
            engine._recompute_population_capacity()
        if not np.isfinite([engine.total_population,engine.food]).all() or (engine.total_population<=0).any() or (engine.food<0).any():
            raise ValueError('Invalid recovery trajectory')
        if not np.allclose(sum(engine.population.values()),engine.total_population,rtol=1e-10,atol=1e-8):
            raise ValueError('Population components do not reconcile')
        rows.append(pl.DataFrame({'location_tag':[x.name for x in specs],'month':month,
            'total_population':engine.total_population.copy(),'food':engine.food.copy(),
            'development':engine.development.copy(),'capacity':engine.population_capacity.copy()}))
    history=pl.concat(rows)
    results=[]
    for row in metadata:
        actual=history.filter(pl.col('location_tag')==row['name'])
        control=history.filter(pl.col('location_tag')==f"D{row['development']:g}_control")
        ordinary=compare_recovery(actual,control,end_month=0)
        logged=compare_recovery(actual.with_columns(pl.col('total_population').log()),
            control.with_columns(pl.col('total_population').log()),end_month=0)['total_population']
        drift=float(np.max(np.abs(control['total_population'].to_numpy()/control['total_population'][0]-1.)))
        results.append(dict(**row,recovery=ordinary,log_population_deviation_recovery=logged,
            control_maximum_relative_population_drift=drift,
            stationary_control=drift<1e-5,
            historical_range_status='not evaluated; source comparability is not a universal acceptance range'))
    output.mkdir(parents=True,exist_ok=True)
    history.write_parquet(output/'monthly.parquet')
    report=dict(model_accepted=False,input_fingerprint=reference['input_fingerprint'],
        recipe_path=str(recipe_path),candidate_preparation_matches=True,required_horizons=[100,200],roots=roots,cases=results,
        contract='Pure-peasant fixed development and prosperity; native population/food ticks; shocks only at month zero. Log population deviations compare to an identical unshocked control. No empirical growth coefficient is substituted.',
        fingerprint=fingerprint([Path(__file__),recipe_path,ROOT/recipe['reference_manifest'],
            ROOT/'src/prosper_or_perish_constructor/simulation',ROOT/'research/population_capacity/population_convergence_extraction.json'],
            dict(model_input_fingerprint=prep['model_input_fingerprint'],scenario=asdict(native),perturbations=perturbations)))
    (output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'output':str(output),'stationary_control_comparisons':sum(x['stationary_control'] for x in results),'cases':len(results)},indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recipe',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args();run(a.recipe.resolve(),a.output.resolve())
