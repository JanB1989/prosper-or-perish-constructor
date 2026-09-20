"""Compare a dated basin-area estimate with explicit game-geography brackets."""
import argparse
import hashlib
import json
from pathlib import Path

import polars as pl


def run(ledger_path, output):
    root = Path(__file__).resolve().parents[2]
    contract_path = Path(__file__).with_name('upper_egypt_extent_audit_contract.json')
    observations_path = Path(__file__).with_name('historical_system_observations.json')
    contract = json.loads(contract_path.read_text())
    observations = json.loads(observations_path.read_text())['observations']
    observation = next(x for x in observations if x['id'] == contract['observation_id'])
    quantity = observation['quantity']
    if quantity['unit'] != 'km2' or quantity['original_estimate'] * 4200 / 1e6 != quantity['estimate']:
        raise ValueError('Basin source units no longer match the audited conversion')
    # Read only geographical/physical fields. Population is not an allocation input.
    columns = ['location_tag', 'province', 'region', 'area_km2', 'calibrated_lat',
               'calibrated_lon', 'has_river', 'crop_fallow_block_km2',
               'water_managed_fields_km2', 'hyde_cropland_area_km2',
               'hyde_irrigated_area_km2', 'historical_system_id']
    frame = pl.read_parquet(ledger_path, columns=columns)
    core = contract['core_provinces']
    broad = core + contract['northern_boundary_provinces']
    if set(broad) - set(frame['province'].unique()):
        raise ValueError('Missing game province in physical bracket')
    selected = frame.filter(pl.col('province').is_in(broad)).with_columns(
        pl.when(pl.col('province').is_in(core)).then(pl.lit('core')).otherwise(
            pl.lit('northern_boundary')).alias('boundary_role'))
    if selected.filter((pl.col('water_managed_fields_km2') > pl.col('crop_fallow_block_km2') + 1e-8)
                       | (pl.col('crop_fallow_block_km2') > pl.col('area_km2') + 1e-8)).height:
        raise ValueError('Invalid physical fields/water nesting')
    rows = []
    for name, provinces in [('core', core), ('core_plus_entire_cairo', broad)]:
        scope = selected.filter(pl.col('province').is_in(provinces))
        fields = scope['crop_fallow_block_km2'].sum()
        water = scope['water_managed_fields_km2'].sum()
        rows.append(dict(scope=name, locations=scope.height,
            total_game_land_km2=scope['area_km2'].sum(), current_fields_km2=fields,
            current_water_served_fields_km2=water, historical_basin_estimate_km2=quantity['estimate'],
            fields_fraction_of_estimate=fields/quantity['estimate'],
            water_fraction_of_estimate=water/quantity['estimate'],
            field_difference_km2=fields-quantity['estimate'],
            water_difference_km2=water-quantity['estimate']))
    output.mkdir(parents=True, exist_ok=True)
    selected.sort('calibrated_lat').write_csv(output/'location_crosswalk.csv')
    selected.filter(pl.col('location_tag').is_in(contract['distinct_hydraulic_locations'])).write_csv(
        output/'distinct_hydraulic_systems.csv')
    pl.DataFrame(rows).write_csv(output/'scope_comparison.csv')
    source_pdf = root / contract['source_pdf']
    inputs = [ledger_path, contract_path, observations_path, source_pdf, Path(__file__)]
    report = dict(model_accepted=False, source_conversion_verified=True,
        hectare_allocation_performed=False, historical_polygon_matching_complete=False,
        source_storage_at_one_metre_m3=quantity['estimate']*1e6,
        scenarios=rows, limitations=contract['limitations'],
        both_brackets_below_source_estimate=all(row['field_difference_km2'] < 0 for row in rows),
        conclusion='Compare the reported physical differences with source uncertainty and mixed geographic coverage; regional food survival cannot certify the Nile extent gate.',
        source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs})
    (output/'manifest.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ledger', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.ledger, args.output), indent=2))
