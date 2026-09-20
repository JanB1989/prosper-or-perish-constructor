"""Audit an isolated management change against saved canonical world runs."""
import argparse
import hashlib
import json
from pathlib import Path

import polars as pl


def run(before: Path, after: Path):
    manifests = [json.loads((p / 'manifest.json').read_text()) for p in (before, after)]
    overrides = [{k: v for k, v in (s.split('=', 1) for s in m['overrides'])
                  if k != 'paths.historical_assignments'} for m in manifests]
    if overrides[0] != overrides[1]:
        raise ValueError('Non-assignment parameters changed')
    scenarios = [[case['scenario'] for case in m['cases']] for m in manifests]
    if scenarios[0] != scenarios[1]:
        raise ValueError('Scenario definitions changed')
    paths = [p / name for p in (before, after) for name in (
        'manifest.json', 'starting_ledger.parquet',
        'common_slower_quarter_checkpoints.parquet', 'viability_criteria.csv')]
    a, b = [pl.read_parquet(p / 'starting_ledger.parquet').sort('location_tag') for p in (before, after)]
    if a['location_tag'].to_list() != b['location_tag'].to_list():
        raise ValueError('Location coverage changed')
    fixed = ['area_km2', 'crop_fallow_block_km2', 'water_managed_fields_km2',
             'natural_population_capacity', 'infrastructure_population_capacity',
             'building_food_output', 'employed_peasants']
    fixed += [c for c in a.columns if c.startswith('population_')]
    fixed += [c for c in a.columns if c.startswith(('opportunity__', 'capacity__'))]
    for column in fixed:
        if not a[column].equals(b[column]):
            raise ValueError(f'Management comparison changed fixed input: {column}')
    changed = b['development'] != a['development']
    if (changed & (b['historical_system_id'] != 'analogue')).any():
        raise ValueError('Named historical development changed')
    delta = b.select('location_tag', 'province', 'region', 'historical_system_id',
                     'management_evidence', 'development', 'management_non_crop_fallback').with_columns(
        a['development'].alias('previous_development'), changed.alias('changed'))
    old, new = [pl.read_parquet(p / 'common_slower_quarter_checkpoints.parquet') for p in (before, after)]
    keys = ['location_tag', 'year']
    metrics = ['total_population', 'local_population_capacity', 'development', 'unmet_food_months']
    paired = new.select(keys + ['province', 'region'] + metrics).join(
        old.select(keys + metrics), on=keys, suffix='_before', validate='1:1')
    if paired.height != old.height or paired.height != new.height:
        raise ValueError('Checkpoint coverage changed')
    summary = paired.group_by('year').agg(
        pl.col('total_population').sum(), pl.col('local_population_capacity').sum(),
        pl.col('development').mean(),
        (pl.col('unmet_food_months') > 0).sum().alias('locations_with_unmet_food'),
        (pl.col('unmet_food_months') > pl.col('unmet_food_months_before')).sum().alias('worse_unmet_locations'),
        ((pl.col('unmet_food_months') > 0) & (pl.col('unmet_food_months_before') == 0)).sum().alias('new_unmet_locations'),
    ).sort('year')
    out = after / 'management_comparison'
    out.mkdir(exist_ok=True)
    delta.write_csv(out / 'assignments.csv')
    paired.write_parquet(out / 'paired_checkpoints.parquet')
    summary.write_csv(out / 'world_summary.csv')
    paired.filter((pl.col('year') == 200) & (pl.col('unmet_food_months') > 0)
                  & (pl.col('unmet_food_months_before') == 0)).write_csv(out / 'new_unmet_locations.csv')
    criteria = pl.read_csv(after / 'viability_criteria.csv')
    report = dict(model_accepted=False, fixed_inputs_verified=fixed,
                  named_development_unchanged=True, changed_development_locations=int(changed.sum()),
                  fallback_locations=int(b['management_non_crop_fallback'].sum()),
                  criteria=criteria.group_by('viability').len().to_dicts(),
                  world=summary.to_dicts(),
                  limitations=['Zero reconstructed cropland does not establish absence of agriculture',
                               'Regional viability is not complete model acceptance'],
                  source_hashes={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths + [Path(__file__)]})
    (out / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--after', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.before, args.after), indent=2))
