"""Reconcile the frozen Upper Nile allocation comparisons and their outcomes."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import polars as pl


def run(root, baseline, case_names=None):
    base=pl.read_parquet(baseline).sort('location_tag')
    baseline_manifest=baseline.parent/'manifest.json'
    baseline_metadata=json.loads(baseline_manifest.read_text())
    def coefficients(document):
        return {k:v for k,v in (x.split('=',1) for x in document['overrides']) if k!='paths.historical_assignments'}
    cases=[];criteria=[];sensitivity=[];paths=[baseline,baseline_manifest,Path(__file__)]
    names=case_names or [f'{boundary}_{weights}' for boundary in ['core','with_atfih_giza','with_cairo'] for weights in ['hyde','luh2']]
    for name in names:
            case=root/name
            allocation_path=case/'input/manifest.json';manifest_path=case/'simulation/manifest.json'
            allocation=json.loads(allocation_path.read_text());manifest=json.loads(manifest_path.read_text())
            if coefficients(manifest)!=coefficients(baseline_metadata):raise ValueError('Shared parameters changed')
            tags=allocation['target_tags'];state_path=case/'simulation/starting_ledger.parquet'
            state=pl.read_parquet(state_path).sort('location_tag')
            if not base['location_tag'].equals(state['location_tag']):raise ValueError('Location coverage changed')
            fixed=['development','building_food_output','total_population','employed_peasants']
            if not base.select(fixed).equals(state.select(fixed)):raise ValueError('Non-land starting inputs changed')
            outside=~pl.col('location_tag').is_in(tags)
            metrics=['local_population_capacity','crop_fallow_block_km2','water_managed_fields_km2']
            if not base.filter(outside).select(metrics).equals(state.filter(outside).select(metrics)):
                raise ValueError('Change outside named extent scope')
            if manifest['preparation']['historical_model']['area_conflict_locations']:
                raise ValueError('Historical land conflict')
            land_columns=['crop_fallow_block_km2','retained_wild_land_km2','extensive_grazing_land_km2']
            before_land=base.select(pl.sum_horizontal(land_columns)).to_numpy()
            after_land=state.select(pl.sum_horizontal(land_columns)).to_numpy()
            if not np.allclose(before_land,after_land,rtol=0,atol=1e-7):raise ValueError('Physical land account changed')
            selected=state.filter(pl.col('location_tag').is_in(tags))
            if not np.isclose(selected['crop_fallow_block_km2'].sum(),allocation['allocated_total_km2'],rtol=0,atol=1e-7):
                raise ValueError('Applied fields do not match sourced experimental total')
            allocation_csv=case/'input/allocation.csv'
            intended=pl.read_csv(allocation_csv).sort('location_tag')
            if intended['location_tag'].to_list()!=selected['location_tag'].to_list() or not np.allclose(
                intended['allocated_fields_km2'],selected['crop_fallow_block_km2'],rtol=0,atol=1e-7):
                raise ValueError('Individual assigned fields differ from the canonical result')
            if 'inferred_basin_component_km2' in intended.columns and not np.isclose(
                intended['inferred_basin_component_km2'].sum(),allocation['source_total_km2'],rtol=0,atol=1e-7):
                raise ValueError('Seasonal basin component does not reconcile separately')
            opportunity=['clearable_wild_land_km2_p50','open_conversion_land_km2_p50']
            if np.any(state.select(pl.sum_horizontal(opportunity)).to_numpy()>
                      base.select(pl.sum_horizontal(opportunity)).to_numpy()+1e-7):
                raise ValueError('Evidenced fields promoted unused known land into future opportunity')
            cp=case/'simulation/viability_criteria.csv';result=pl.read_csv(cp)
            criteria.append(result.with_columns(pl.lit(name).alias('allocation_case')))
            sensitivity.append(state.select('location_tag','province',*metrics).with_columns(pl.lit(name).alias('allocation_case')))
            cases.append(dict(case=name,geographical_checks=result.group_by('viability').len().to_dicts(),
                assigned_fields_km2=selected['crop_fallow_block_km2'].sum(),
                served_fields_km2=selected['water_managed_fields_km2'].sum(),
                imposed_source_component_km2=allocation['source_total_km2'],
                existing_fields_beyond_source_component_km2=allocation['allocated_total_km2']-allocation['source_total_km2'],
                physically_saturated_locations=allocation['physically_saturated_locations'],
                physical_land_conserved=True,neighbours_unchanged=True,development_and_food_coefficients_unchanged=True))
            paths += [allocation_path,allocation_csv,manifest_path,state_path,cp]
    pl.concat(criteria).write_csv(root/'evaluated_horizon_comparisons.csv')
    pl.concat(sensitivity).write_parquet(root/'geographical_sensitivity.parquet')
    report=dict(model_accepted=False,cases=cases,
        limitations=['8400km2 is imposed from the rough source estimate, not independently validated by this allocation',
            'The physical conversion ledger does not establish floodplain or independently available water',
            'HYDE/LUH2 weights share source lineage; this is spatial sensitivity, not an independent-source holdout',
            'Passing survival screens does not freeze demographic plausibility ranges'],
        source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    (root/'allocation_comparison.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--case',action='append',dest='cases')
    a=p.parse_args();print(json.dumps(run(a.root,a.baseline,a.cases),indent=2))
