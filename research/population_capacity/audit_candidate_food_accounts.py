"""Reproduce a regional candidate and export complete provincial food accounts."""
import argparse
import json
from pathlib import Path

import numpy as np
import polars as pl

from run_historical_direct import ROOT, prepare
from prosper_or_perish_constructor.simulation.agricultural_employment import attach_slave_agriculture
from prosper_or_perish_constructor.simulation.cache import fingerprint
from prosper_or_perish_constructor.simulation.food_diagnosis import diagnose_provincial_food


def run(experiment, *, all_provinces=False):
    manifest_path=experiment/'manifest.json'
    manifest=json.loads(manifest_path.read_text())
    _,(state,context,preparation)=prepare(manifest['overrides'])
    state=attach_slave_agriculture(state,subsistence_output=context.subsistence_agriculture,hiring_fraction=.75)
    saved_path=experiment/'starting_ledger.parquet'
    if not state.sort('location_tag').equals(pl.read_parquet(saved_path).sort('location_tag')):
        raise ValueError('Starting state is stale; rerun the candidate')
    criteria=pl.read_csv(experiment/'viability_criteria.csv')
    provinces=sorted((state if all_provinces else criteria)['province'].drop_nulls().unique().to_list())
    locations,totals,budgets=diagnose_provincial_food(state.filter(pl.col('province').is_in(provinces)),context)
    previous=pl.read_csv(experiment/'all_provincial_food_budgets.csv').filter(pl.col('province').is_in(provinces))
    metrics=['food_production','food_consumption','food_balance','subsistence_surplus',
             'non_subsistence_balance_after_other_pops','pressure_recoverable_consumption']
    left,right=budgets.sort('province'),previous.sort('province')
    if left['province'].to_list()!=right['province'].to_list() or not np.allclose(
            left.select(metrics).to_numpy(),right.select(metrics).to_numpy(),rtol=0,atol=1e-8):
        raise ValueError('Reconstructed food accounts differ from saved candidate')
    out=experiment/('world_food_audit' if all_provinces else 'food_audit');out.mkdir(exist_ok=True)
    locations.write_parquet(out/'local_accounts.parquet')
    totals.write_csv(out/'provincial_actual_and_low_pressure.csv')
    budgets.write_csv(out/'provincial_diagnosis.csv')
    failed=sorted(criteria.filter(pl.col('viability')=='failed')['province'].unique().to_list())
    budgets.filter(pl.col('province').is_in(failed)).write_csv(out/'failed_provincial_diagnosis.csv')
    report=dict(model_accepted=False,starting_state_reproduced=True,provincial_budgets_reproduced=True,
        complete_provinces=provinces,failed_provinces=failed,
        scope='all provinces' if all_provinces else 'regional acceptance provinces',
        failed_provinces_scope='evaluated regional criteria only; other provinces are not implicitly passed',
        limitations=['Negligible pressure is a diagnostic, never a fitted capacity assignment',
                     'Existing building food is retained; hypothetical future cookeries are not starting supply',
                     'Starting budgets do not certify trajectory or historical acceptance'],
        fingerprint=fingerprint([Path(__file__),manifest_path,saved_path,
            experiment/'viability_criteria.csv',experiment/'all_provincial_food_budgets.csv',
            ROOT/'src/prosper_or_perish_constructor/simulation'],dict(preparation=preparation)))
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment',type=Path,required=True)
    parser.add_argument('--all-provinces',action='store_true',help='Reconcile every provincial food budget, including locations outside regional acceptance cases')
    args=parser.parse_args()
    print(json.dumps(run(args.experiment,all_provinces=args.all_provinces),indent=2))
