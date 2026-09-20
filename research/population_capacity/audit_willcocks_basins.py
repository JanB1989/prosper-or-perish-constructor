"""Audit original source arithmetic before using dated Nile areas in calibration."""
import argparse
import hashlib
import json
from pathlib import Path

import polars as pl


def run(output: Path):
    root = Path(__file__).resolve().parents[2]
    contract_path = Path(__file__).with_name('willcocks_1889_basin_evidence.json')
    contract = json.loads(contract_path.read_text())
    for source in contract['sources']:
        path = root / source['path']
        if hashlib.sha256(path.read_bytes()).hexdigest() != source['sha256']:
            raise ValueError(f'Source fingerprint changed: {path}')
    table_path = root / contract['table_path']
    frame = pl.read_csv(table_path)
    unit = contract['unit']['calculation_square_metres'] / 1e6
    numeric = list(contract['printed_totals'])
    if frame.select(pl.any_horizontal([pl.col(c).is_null() | (pl.col(c) < 0)
                                      for c in numeric]).any()).item():
        raise ValueError('Incomplete or negative transcribed area')
    discrepancies = []
    for row in frame.iter_rows(named=True):
        if row['left_basin_feddans'] + row['right_basin_feddans'] != row['printed_basin_feddans']:
            raise ValueError(f"Basin-bank arithmetic does not reconcile: {row['province']}")
        delta = row['printed_total_feddans'] - sum(row[c] for c in
            ['printed_basin_feddans', 'high_berm_feddans', 'summer_tract_feddans'])
        if delta:
            discrepancies.append(dict(scope='row', recipient=row['province'],
                field='printed_total_feddans', printed_minus_components_feddans=delta))
    sums = {c: frame[c].sum() for c in numeric}
    for field, printed in contract['printed_totals'].items():
        if printed != sums[field]:
            discrepancies.append(dict(scope='column', recipient='total', field=field,
                printed_minus_components_feddans=printed-sums[field]))
    if discrepancies != contract['expected_source_discrepancies']:
        raise ValueError(f'Unexpected source/transcription discrepancy: {discrepancies}')
    southern = contract['southern_basin_observations']
    section_b = southern['section_B']
    if sum(section_b['areas_feddans']) != section_b['printed_total_feddans']:
        raise ValueError('Southern basin chain does not reconcile')
    for section in ('section_A', 'section_B'):
        item = southern[section]
        acres = item.get('area_feddans', item.get('printed_total_feddans'))
        area = item.get('area_km2', item.get('total_km2'))
        if abs(acres*unit-area) > 1e-8:
            raise ValueError(f'Incorrect southern area conversion: {section}')
    converted = frame.with_columns([
        (pl.col(c)*unit).alias(c.replace('_feddans', '_km2')) for c in numeric])
    output.mkdir(parents=True, exist_ok=True)
    converted.write_csv(output/'dated_province_areas.csv')
    basin = sums['printed_basin_feddans']*unit
    report = dict(schema_version=1, source_hashes_verified=True,
        bank_and_province_basin_totals_reconcile=True,
        southern_basin_observations_reconcile=True,
        all_printed_arithmetic_reconciles=not discrepancies,
        preserved_source_discrepancies=discrepancies,
        silently_corrected_source_values=False,
        dated_basin_km2=basin,
        dated_high_berm_km2=sums['high_berm_feddans']*unit,
        dated_summer_tract_km2_from_rows=sums['summer_tract_feddans']*unit,
        dated_summer_tract_km2_from_printed_total=contract['printed_totals']['summer_tract_feddans']*unit,
        precise_unit_relative_change=contract['unit']['appendix_precise_square_metres']/4200-1,
        using_english_acre_relative_error=4046.8564224/4200-1,
        source_to_game_year_gap=contract['publication_year']-contract['game_year'],
        historical_game_crosswalk_complete=False,
        hectare_assignment_performed=False, model_accepted=False,
        limitations=contract['limitations'],
        input_hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in [contract_path, table_path, Path(__file__)]})
    (output/'manifest.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.output), indent=2))
