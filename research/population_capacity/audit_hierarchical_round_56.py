"""Top-down attribution and physical checks for the frozen round56 candidate."""
from pathlib import Path
import json
import hashlib

import numpy as np
import polars as pl

from run_historical_direct import ROOT, prepare
from prosper_or_perish_constructor.simulation.agricultural_employment import attach_slave_agriculture
from prosper_or_perish_constructor.simulation.food_diagnosis import diagnose_provincial_food

BASE = ROOT/'artifacts/data/population_simulation/repair_round_55/grouped_world'
OUT = ROOT/'artifacts/data/population_simulation/repair_round_56/preflight'


def land(frame):
    return frame.select(pl.sum_horizontal('crop_fallow_block_km2', 'extensive_grazing_land_km2',
        'retained_wild_land_km2')+pl.col('area_km2')*pl.col('urban_fraction_1300')).to_numpy().ravel()


def statistics(d):
    return d.group_by('macro_region').agg(pl.len().alias('locations'),
        pl.col('total_population').sum().alias('population'),
        pl.col('local_population_capacity').sum().alias('capacity'),
        pl.col('local_population_capacity').min().alias('capacity_min'),
        pl.col('local_population_capacity').median().alias('capacity_median'),
        pl.col('local_population_capacity').mean().alias('capacity_mean'),
        pl.col('local_population_capacity').max().alias('capacity_max'),
        pl.col('development').mean().alias('development_mean'),
        pl.col('development').median().alias('development_median'),
        pl.col('crop_fallow_block_km2').sum().alias('fields_km2'),
        pl.col('water_managed_fields_km2').sum().alias('water_km2'),
        pl.col('remaining_clearing_capacity').sum().alias('remaining_clearing_flat'),
        pl.col('remaining_water_capacity').sum().alias('remaining_water_flat')).sort('macro_region')


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((BASE/'manifest.json').read_text())
    overrides=manifest['overrides']
    _,(replay,_,_)=prepare(overrides)
    replay=attach_slave_agriculture(replay,subsistence_output=1.3,hiring_fraction=.75).sort('location_tag')
    before=pl.read_parquet(BASE/'starting_ledger.parquet').sort('location_tag')
    if not replay.select(before.columns).equals(before):
        differences=[c for c in before.columns if not replay[c].equals(before[c])]
        raise ValueError('Legacy starting state changed: '+str(differences))
    overrides=[*overrides,'paths.historical_assignments="research/population_capacity/historical_assignments_round_56.json"']
    _,(after,context,metadata)=prepare(overrides)
    after=attach_slave_agriculture(after,subsistence_output=context.subsistence_agriculture,hiring_fraction=.75).sort('location_tag')
    assert before['location_tag'].to_list()==after['location_tag'].to_list()
    assert np.allclose(land(before),land(after),rtol=0,atol=1e-7)
    assert np.allclose(land(after),after['area_km2'],rtol=0,atol=1e-7)
    assert after['historical_area_conflict_km2'].max()<1e-7
    assert (after['water_managed_fields_km2']<=after['crop_fallow_block_km2']+1e-8).all()
    assert np.allclose(after['capacity__water_control'],after['capacity__water_managed_baseline']+after['capacity__water_increment'])
    assert (after['remaining_clearing_capacity']<=before['remaining_clearing_capacity']+1e-7).all()
    for c in [x for x in before.columns if x.startswith('population_')]+['total_population','building_food_output','rgo_food_output','employed_peasants']:
        assert before[c].equals(after[c]),c
    after.write_parquet(OUT/'starting_ledger.parquet')
    # Exact sequential attribution: assignments at unchanged old physical support,
    # then corrected current land/water, with unchanged scale and D coefficient.
    old_flat=before['base_population_capacity']+before['infrastructure_population_capacity']
    old_factor=1+before['development']*.05
    new_factor=1+after['development']*.05
    assert np.allclose(old_flat*old_factor,before['local_population_capacity'])
    dev_only=old_flat*new_factor
    columns=['location_tag','macro_region','region','province','development','management_rule_id',
        'management_evidence_tier','local_population_capacity','crop_fallow_block_km2','water_managed_fields_km2',
        'historical_area_conflict_km2','historical_rainfed_density_unresolved']
    effects=after.select(columns).with_columns(
        before['development'].alias('before_development'),before['local_population_capacity'].alias('before_capacity'),
        (after['crop_fallow_block_km2']-before['crop_fallow_block_km2']).alias('added_fields_km2'),
        (after['water_managed_fields_km2']-before['water_managed_fields_km2']).alias('added_water_km2'),
        (dev_only-before['local_population_capacity']).alias('development_effect'),
        (after['local_population_capacity']-dev_only).alias('land_water_effect'),
        (after['local_population_capacity']-before['local_population_capacity']).alias('capacity_change'))
    assert np.allclose(effects['development_effect']+effects['land_water_effect'],effects['capacity_change'])
    effects.write_csv(OUT/'location_attribution.csv')
    for scope in ['macro_region','region','province']:
        effects.group_by(scope).agg(pl.len().alias('locations'),pl.col('before_capacity','local_population_capacity',
            'capacity_change','development_effect','land_water_effect','added_fields_km2','added_water_km2').sum()).sort(
            'capacity_change',descending=True).write_csv(OUT/f'{scope}_attribution.csv')
    pl.concat([statistics(before).with_columns(pl.lit('round55').alias('candidate')),
               statistics(after).with_columns(pl.lit('round56').alias('candidate'))]).write_csv(OUT/'macro_statistics.csv')
    _,_,budgets=diagnose_provincial_food(after,context);budgets.write_csv(OUT/'provincial_food_budgets.csv')
    # Explicit common-scale counterfactual; no extra simulation or selected fit.
    lower=(after['base_population_capacity']+after['infrastructure_population_capacity']-after['candidate_urban_accommodation'])*(3/4.5)
    lower=(lower+after['candidate_urban_accommodation'])*new_factor
    after.select('location_tag','macro_region').with_columns(lower.alias('scale3_capacity'),
        after['local_population_capacity'].alias('scale4_5_capacity')).group_by('macro_region').agg(
            pl.col('scale3_capacity','scale4_5_capacity').sum()).write_csv(OUT/'analytical_scale_comparison.csv')
    summary=dict(legacy_replay=True,legacy_columns=before.width,locations=after.height,
        area_conflicts=0,land_conserved=True,source_units='capacity in thousands of people; physical area km2',
        starting_capacity_before=float(before['local_population_capacity'].sum()),
        starting_capacity_after=float(after['local_population_capacity'].sum()),
        changed_development=int((before['development']!=after['development']).sum()),
        added_fields_km2=float(effects['added_fields_km2'].sum()),added_water_km2=float(effects['added_water_km2'].sum()),
        preparation=metadata,overrides=overrides,
        inputs={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [
            ROOT/'research/population_capacity/historical_assignments_round_56.json',BASE/'starting_ledger.parquet',
            ROOT/'src/prosper_or_perish_constructor/simulation/historical_model.py',
            ROOT/'src/prosper_or_perish_constructor/simulation/management_hierarchy.py']})
    (OUT/'manifest.json').write_text(json.dumps(summary,indent=2,default=str)+'\n')
    print({k:v for k,v in summary.items() if k not in ['preparation','overrides','inputs']},flush=True)


if __name__=='__main__':
    main()
