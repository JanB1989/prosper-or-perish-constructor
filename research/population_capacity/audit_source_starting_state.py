"""Audit a paired crop-source change after canonical starting-state preparation.

Presence labels can alter the conditional land-feasibility screen. Report that
effect instead of assuming unchanged cultivated hectares from unchanged labels.
"""
import argparse
import json
from pathlib import Path

import polars as pl

from prosper_or_perish_constructor.simulation.cache import fingerprint


def audit(before_path, after_path, changes_path, output):
    before = pl.read_parquet(before_path).sort('location_tag')
    after = pl.read_parquet(after_path).sort('location_tag')
    if not before['location_tag'].equals(after['location_tag']):
        raise ValueError('Location geometry membership changed')
    fixed = ['province', 'area_km2', 'development', 'total_population', 'building_food_output']
    fixed += [c for c in before.columns if c.startswith('population_')]
    if not before.select(fixed).equals(after.select(fixed)):
        raise ValueError('Source-only comparison changed independent starting assignments')
    metrics = ['crop_fallow_block_km2', 'water_managed_fields_km2',
               'local_population_capacity', 'natural_population_capacity',
               'infrastructure_population_capacity']
    metrics = [c for c in metrics if c in before.columns and c in after.columns]
    allowed = pl.read_csv(changes_path)['location_tag'].unique().to_list()
    pairs = before.select('location_tag', *metrics).join(
        after.select('location_tag', 'province', *metrics), on='location_tag',
        suffix='_after', validate='1:1')
    pairs = pairs.with_columns(*[(pl.col(c+'_after')-pl.col(c)).alias(c+'_change') for c in metrics])
    changed = pairs.filter(pl.any_horizontal(*[(pl.col(c+'_change').abs()>1e-10) for c in metrics]))
    if changed.filter(~pl.col('location_tag').is_in(allowed)).height:
        raise ValueError('Canonical geographical effects escaped corrected crop scope')
    output.mkdir(parents=True, exist_ok=True)
    changed.write_csv(output/'changed_starting_locations.csv')
    changed.group_by('province').agg(*[pl.col(c, c+'_after', c+'_change').sum() for c in metrics]).sort('province').write_csv(output/'changed_province_totals.csv')
    result = dict(model_accepted=False, independent_starting_assignments_unchanged=True,
        outside_crop_scope_changed_locations=0, changed_locations=changed.height,
        metrics={c: dict(changed_locations=int((pairs[c+'_change'].abs()>1e-10).sum()),
                        maximum_absolute_change=pairs[c+'_change'].abs().max(),
                        total_change=pairs[c+'_change'].sum()) for c in metrics},
        limitations=['This verifies paired-source attribution, not historical validity or behavioural acceptance',
                     'Capacity is in simulator thousands of people; physical fields are square kilometres'],
        fingerprint=fingerprint([Path(__file__),before_path,after_path,changes_path],{}))
    (output/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('before','after','changes','output'):
        parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(audit(args.before,args.after,args.changes,args.output),indent=2))
