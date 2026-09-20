"""Exact game-pixel / river crosswalk; corridor widths are diagnostics, not fields."""
import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
import polars as pl
from pyproj import Transformer
from rasterio.features import shapes
from rasterio.transform import Affine
from shapely import from_wkb
from shapely.geometry import shape, mapping
from shapely.ops import transform, unary_union

from prosper_or_perish_population_capacity.geometry_calibration import CylindricalTransform


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8*1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def run(ledger_path, locations_png, output):
    root = Path(__file__).resolve().parents[2]
    data = root/'artifacts/data/population_capacity'
    geometry_path = data/'geometry_land_contract_candidate_v1/location_geometry_candidate.parquet'
    transform_path = data/'geometry_land_contract_candidate_v1/coordinate_transform_candidate.json'
    rivers_path = data/'hydrology_alignment/river_reaches.parquet'
    contract_path = Path(__file__).with_name('upper_nile_allocation_experiment.json')
    contract = json.loads(contract_path.read_text())
    columns = ['location_tag','province','area_km2','crop_fallow_block_km2','water_managed_fields_km2']
    ledger = pl.read_parquet(ledger_path, columns=columns)
    selected = ledger.filter(pl.col('province').is_in(contract['core_provinces']+['cairo_province']))
    tags = selected['location_tag'].to_list()
    geometry = pl.read_parquet(geometry_path).filter(pl.col('location_tag').is_in(tags))
    coords = CylindricalTransform.from_dict(json.loads(transform_path.read_text()))
    png_hash = sha(locations_png)
    samples_path = data/'geometry_land_contract_candidate_v1/full/game_authoritative_physical_samples.parquet'
    stamps = pl.scan_parquet(samples_path).select('locations_png_sha256','coordinate_transform_sha256').unique().collect()
    transform_identity = hashlib.sha256(json.dumps(coords.to_dict(),sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if stamps.height != 1 or stamps['locations_png_sha256'][0] != png_hash or stamps['coordinate_transform_sha256'][0] != transform_identity:
        raise ValueError('Current game raster/transform differs from canonical samples')
    left, right = geometry['bbox_min_x'].min(), geometry['bbox_max_x'].max()+1
    top, bottom = geometry['bbox_min_y'].min(), geometry['bbox_max_y'].max()+1
    Image.MAX_IMAGE_PIXELS = None
    with Image.open(locations_png) as image:
        rgb = np.asarray(image.crop((left,top,right,bottom)).convert('RGB')).astype(np.uint32)
    colors = (rgb[:,:,0]<<16)+(rgb[:,:,1]<<8)+rgb[:,:,2]
    labels = np.zeros(colors.shape,dtype=np.int32)
    rows = geometry.sort('location_tag').to_dicts()
    for index,row in enumerate(rows,1):
        mask = colors == int(row['named_location_hex'],16)
        if int(mask.sum()) != row['pixel_count']:
            raise ValueError(f"Incomplete pixels for {row['location_tag']}")
        labels[mask] = index
    parts = {}
    for geo, label in shapes(labels, mask=labels>0, transform=Affine.translation(left,top)):
        parts.setdefault(int(label),[]).append(shape(geo))
    polygons = {rows[i-1]['location_tag']: transform(coords.predict,unary_union(p)) for i,p in parts.items()}
    rivers = pl.scan_parquet(rivers_path).filter(
        pl.col('centroid_lon').is_between(29.,34.) & pl.col('centroid_lat').is_between(23.5,30.7)
        & (pl.col('main_basin_id')=='main_river:10047863')
        & (pl.col('q_mean_m3_s')>500)).collect()
    if not rivers.height:
        raise ValueError('No major Nile reaches found')
    river = unary_union(from_wkb(rivers['geometry_wkb'].to_numpy()))
    # Local equal-area projection keeps corridor area comparisons physical.
    projection = Transformer.from_crs('EPSG:4326','+proj=laea +lat_0=27 +lon_0=32 +datum=WGS84 +units=m',always_xy=True)
    projected_river = transform(projection.transform,river)
    corridors = {width:projected_river.buffer(width*1000) for width in (.5,1.,2.,5.)}
    reach_shapes = [(row, transform(projection.transform,from_wkb(row['geometry_wkb'])))
                    for row in rivers.iter_rows(named=True)]
    reach_intersections=[]
    metrics=[];features=[]
    for row in selected.sort('location_tag').iter_rows(named=True):
        tag=row['location_tag']; poly=polygons[tag]; physical=transform(projection.transform,poly)
        for reach, line in reach_shapes:
            length=physical.intersection(line).length/1000
            if length>1e-8:
                reach_intersections.append(dict(location_tag=tag,reach_id=reach['reach_id'],
                    downstream_reach_id=reach['downstream_reach_id'],intersection_length_km=length,
                    source_distance_downstream_km=reach['distance_downstream_km']))
        metrics.append(dict(**row, polygon_area_km2=physical.area/1e6,
            river_length_km=physical.intersection(projected_river).length/1000,
            **{f'corridor_{str(width).replace(".","_")}_km_each_bank_area_km2':physical.intersection(corridor).area/1e6
               for width,corridor in corridors.items()}))
        features.append(dict(type='Feature',properties={'location_tag':tag,'province':row['province']},geometry=mapping(poly)))
    output.mkdir(parents=True,exist_ok=True)
    pl.DataFrame(metrics).write_csv(output/'location_river_crosswalk.csv')
    (output/'game_location_polygons.geojson').write_text(json.dumps(dict(type='FeatureCollection',features=features)))
    rivers.drop('geometry_wkb').write_csv(output/'selected_river_reaches.csv')
    intersections=pl.DataFrame(reach_intersections)
    intersections.write_csv(output/'river_reach_location_intersections.csv')
    # This must reconcile to the union only if no reach is duplicated spatially.
    length_by_tag=intersections.group_by('location_tag').agg(pl.col('intersection_length_km').sum())
    lengths=dict(length_by_tag.iter_rows())
    maximum_length_residual=max(abs(lengths.get(m['location_tag'],0.)-m['river_length_km']) for m in metrics)
    if maximum_length_residual>1e-6:
        raise ValueError('River reach intersections double-count channel length')
    fig,ax=plt.subplots(figsize=(9,12))
    for tag,poly in polygons.items():
        for part in getattr(poly,'geoms',[poly]):
            x,y=part.exterior.xy;ax.fill(x,y,alpha=.12,color='sienna');ax.plot(x,y,color='#66513c',lw=.7)
        point=poly.representative_point();ax.text(point.x,point.y,tag,fontsize=6)
    for part in getattr(river,'geoms',[river]):
        x,y=part.xy;ax.plot(x,y,color='#137fac',lw=1.2)
    ax.set(xlim=(29.5,34),ylim=(23.5,max(p.bounds[3] for p in polygons.values())+.12),xlabel='Longitude',ylabel='Latitude',
           title='Upper Nile: canonical game boundaries and modern river geometry\nSpatial audit — no historical hectares assigned')
    ax.set_aspect(1/np.cos(np.deg2rad(27)));fig.tight_layout();fig.savefig(output/'nile_geometry.png',dpi=180);plt.close(fig)
    report=dict(model_accepted=False,locations=len(metrics),river_reaches=rivers.height,
        exact_game_pixel_counts_verified=True,canonical_raster_and_transform_verified=True,
        maximum_reach_union_length_residual_km=maximum_length_residual,
        river_selection={'basin':'main_river:10047863','minimum_modern_mean_flow_m3_s':500,
                         'role':'major trunk spatial filter only; not a medieval water budget'},
        historical_basin_polygon_crosswalk_complete=False,hectares_allocated=False,
        maximum_relative_polygon_vs_canonical_area_difference=max(abs(m['polygon_area_km2']/m['area_km2']-1) for m in metrics),
        limitations=['Modern river geometry is a spatial reference, not a medieval discharge or channel survey.',
            'Uniform corridor widths are sensitivity diagnostics, not floodplain/cultivated-area estimates.',
            'Banban and the Edfu/Esna chain still require bank/section overlap; location names alone do not allocate basin hectares.',
            'No location-specific registration shift is applied; the canonical coordinate transform is preserved.'],
        input_hashes={str(p):sha(p) for p in [ledger_path,geometry_path,transform_path,locations_png,rivers_path,contract_path,Path(__file__)]})
    (output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ledger',type=Path,required=True)
    parser.add_argument('--locations-png',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(run(args.ledger,args.locations_png,args.output),indent=2))
