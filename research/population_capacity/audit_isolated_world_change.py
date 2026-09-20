"""Verify global collateral from a geographically isolated candidate change."""
import argparse
import hashlib
import json
from pathlib import Path

import polars as pl
import numpy as np


def run(before, after, tags, *, allow_field_change=False):
    inputs = [p / n for p in (before, after) for n in (
        'manifest.json', 'starting_ledger.parquet', 'common_slower_quarter_checkpoints.parquet')]
    a, b = [pl.read_parquet(p / 'starting_ledger.parquet').sort('location_tag') for p in (before, after)]
    if a['location_tag'].to_list() != b['location_tag'].to_list() or set(tags)-set(b['location_tag']):
        raise ValueError('Location coverage mismatch')
    outside = ~pl.col('location_tag').is_in(tags)
    metrics = ['development', 'local_population_capacity', 'crop_fallow_block_km2',
               'water_managed_fields_km2', 'building_food_output', 'total_population']
    if not a.filter(outside).select(metrics).equals(b.filter(outside).select(metrics)):
        raise ValueError('Starting geographical change escaped the named system')
    fixed = ['area_km2', 'building_food_output', 'employed_peasants']
    if not allow_field_change:
        fixed.append('crop_fallow_block_km2')
    fixed += [c for c in a.columns if c.startswith('population_')]
    if not a.select(fixed).equals(b.select(fixed)):
        raise ValueError('Isolated management changed land, food, jobs or population inputs')
    land=['crop_fallow_block_km2','retained_wild_land_km2','extensive_grazing_land_km2']
    if not np.allclose(a.select(pl.sum_horizontal(land)).to_numpy(),
                       b.select(pl.sum_horizontal(land)).to_numpy(),rtol=0,atol=1e-7):
        raise ValueError('Physical land does not reconcile')
    provinces = b.filter(pl.col('location_tag').is_in(tags))['province'].unique().to_list()
    old, new = [pl.read_parquet(p / 'common_slower_quarter_checkpoints.parquet').sort(
        'location_tag', 'year') for p in (before, after)]
    if not old.select('location_tag', 'year').equals(new.select('location_tag', 'year')):
        raise ValueError('Checkpoint coverage mismatch')
    other = ~pl.col('province').is_in(provinces)
    common = sorted(set(old.columns) & set(new.columns))
    if not old.filter(other).select(common).equals(new.filter(other).select(common)):
        raise ValueError('A trajectory outside the affected food-sharing provinces changed')
    annual_paths=[p/'common_slower_quarter_annual_provinces.parquet' for p in (before,after)]
    annual_before,annual_after=[pl.read_parquet(p).filter(other).sort('province','year') for p in annual_paths]
    if not annual_before.equals(annual_after):
        raise ValueError('An annual provincial aggregate outside the affected scope changed')
    inputs += annual_paths
    paired = new.select('location_tag', 'province', 'year', 'total_population', 'unmet_food_months').join(
        old.select('location_tag', 'year', 'total_population', 'unmet_food_months'),
        on=['location_tag', 'year'], suffix='_before', validate='1:1')
    summary = paired.group_by('year').agg(pl.col('total_population').sum(),
        pl.col('total_population_before').sum(),
        (pl.col('unmet_food_months') > pl.col('unmet_food_months_before')).sum().alias('worse_unmet_locations'),
        (pl.col('unmet_food_months') > 0).sum().alias('locations_with_unmet_food')).sort('year')
    output = after / 'isolated_world_audit'
    output.mkdir(exist_ok=True)
    paired.write_parquet(output/'paired_checkpoints.parquet')
    summary.write_csv(output/'world_comparison.csv')
    report = dict(model_accepted=False, target_tags=tags, affected_provinces=provinces,
        outside_starting_assignments_unchanged=True, outside_provincial_trajectories_unchanged=True,
        outside_annual_provincial_aggregates_unchanged=True,physical_land_conserved=True,
        field_change_allowed_within_tags=allow_field_change,
        fixed_inputs=fixed, world=summary.to_dicts(),
        limitation='Collateral and accounting audit, not demographic or geographical acceptance',
        source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs + [Path(__file__)]})
    (output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--after', type=Path, required=True)
    parser.add_argument('--tag', action='append', required=True)
    parser.add_argument('--allow-field-change',action='store_true')
    args = parser.parse_args()
    print(json.dumps(run(args.before, args.after, args.tag,allow_field_change=args.allow_field_change),indent=2))
