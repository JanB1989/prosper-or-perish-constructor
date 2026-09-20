"""Trace grouped allocation conflicts to dated fields and the crop-area proxy."""
import argparse
import hashlib
import json
from pathlib import Path
import polars as pl


def run(ledger, groups, output):
    contract=json.loads(groups.read_text())
    columns=['location_tag','area_km2','crop_fallow_block_km2',
        'open_conversion_land_km2_p50','clearable_wild_land_km2_p50',
        'feasible_cultivated_fraction','hyde_cropland_area_km2_2025','hyde_cropland_area_km2_1300']
    state=pl.read_parquet(ledger,columns=columns)
    parts=[]
    for group in contract['groups']:
        parts.append(state.filter(pl.col('location_tag').is_in(group['location_tags'])).with_columns(
            pl.lit(group['source_province']).alias('analogue_province')))
    frame=pl.concat(parts).with_columns(
        (pl.col('area_km2')*pl.col('feasible_cultivated_fraction')).alias('mixture_suitability_area_km2'),
        (pl.col('crop_fallow_block_km2')+pl.col('open_conversion_land_km2_p50')+
         pl.col('clearable_wild_land_km2_p50')).alias('allocation_ceiling_km2'))
    scope=frame.group_by('analogue_province').agg(pl.col('area_km2','crop_fallow_block_km2',
        'mixture_suitability_area_km2','allocation_ceiling_km2',
        'hyde_cropland_area_km2_2025','hyde_cropland_area_km2_1300').sum()).sort('analogue_province')
    output.mkdir(parents=True,exist_ok=True)
    frame.write_csv(output/'land_ceiling_diagnosis.csv')
    scope.write_csv(output/'land_ceiling_scope_diagnosis.csv')
    residual=(scope['allocation_ceiling_km2']-scope['mixture_suitability_area_km2']).abs().max()
    report=dict(model_accepted=False,assignments_changed=False,
        maximum_ceiling_vs_mixture_area_residual_km2=residual,
        diagnosis='The allocation ceiling equals the crop-mixture suitability area in these scopes. It is not an independently surveyed floodplain boundary.',
        limitations=['HYDE2025 is a later related-source diagnostic, not1337 cultivated extent or permission to add future land.',
            'Whole game-location groups approximate historical provinces; group mismatch and agronomic-mask mismatch are separate uncertainties.',
            'Do not replace the ceiling with total location area, a population target, or modern cultivated hectares without physical-resource reconciliation.'],
        input_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ledger,groups,Path(__file__)]})
    (output/'land_ceiling_diagnosis.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('ledger','groups','output'):p.add_argument('--'+key,required=True,type=Path)
    a=p.parse_args();print(json.dumps(run(a.ledger,a.groups,a.output),indent=2))
