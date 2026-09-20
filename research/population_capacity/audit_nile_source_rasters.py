"""Integrate cached HYDE cells independently of game-location sampling."""
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import polars as pl
import rasterio
from rasterio.windows import Window, bounds, from_bounds
import xarray as xr

from prosper_or_perish_constructor.simulation.profile import load_population_simulation_profile
from prosper_or_perish_constructor.simulation.source_provenance import hyde_raster_provenance


def run(output):
    root = Path(__file__).resolve().parents[2]
    profile = load_population_simulation_profile(root/'population_capacity_simulation.toml',repo=root)
    paths = {'cropland':profile.hyde_cropland_path, 'irrigated':profile.hyde_irrigated_path,
             'rainfed':profile.hyde_rainfed_path, 'pasture':profile.hyde_pasture_path}
    metadata = hyde_raster_provenance(paths)
    requested_bounds = (29., 23.5, 34., 30.1)
    rows = []
    netcdf_metadata = {}
    input_paths = [*paths.values(), Path(__file__)]
    for kind, path in paths.items():
        with rasterio.open(path) as source:
            if source.crs.to_epsg() != 4326 or source.tags().get('units') not in ('km²','km2','km**2'):
                raise ValueError('This audit requires geographic per-cell area totals in km2')
            raw = from_bounds(*requested_bounds, source.transform)
            x, y = math.floor(raw.col_off), math.floor(raw.row_off)
            window = Window(x,y,math.ceil(raw.col_off+raw.width)-x,math.ceil(raw.row_off+raw.height)-y)
            values = source.read(1,window=window,masked=True).astype(np.float64)
            if np.any(values.compressed() < 0):
                raise ValueError('Negative physical area in valid source cells')
            rows.append(dict(kind=kind,source_year=metadata[kind]['source_year'],
                requested_year=metadata[kind]['requested_year'],area_sum_km2=float(values.sum()),
                valid_cells=int(values.count()),masked_cells=int(np.ma.getmaskarray(values).sum()),
                actual_cell_bounds=list(bounds(window,source.transform))))
        nc = profile.hyde_root/'data/input_data/hyde'/metadata[kind]['source_dataset']
        input_paths.append(nc)
        with xr.open_dataset(nc,decode_times=False) as data:
            netcdf_metadata[kind] = {key:str(data.attrs.get(key)) for key in
                ('version','description','license','date_created','input_date')}
    # Equal crop/irrigation totals support water dependence within this source,
    # not independently attested 1337 irrigation or a transferable yield bonus.
    output.mkdir(parents=True,exist_ok=True)
    pl.DataFrame([{k:v for k,v in row.items() if k!='actual_cell_bounds'} for row in rows]).write_csv(output/'source_totals.csv')
    source_hashes = {}
    for path in input_paths:
        with path.open('rb') as stream:
            source_hashes[str(path)] = hashlib.file_digest(stream,'sha256').hexdigest()
    report = dict(model_accepted=False,requested_bounds=requested_bounds,
        scope='Coarse Aswan-to-Cairo geographic rectangle, including Fayyum; not a historical basin polygon',
        window_policy='Outward-rounded complete cells; no centroid sampling, population or game-area multiplier',
        totals=rows,raster_provenance=metadata,netcdf_declared_metadata=netcdf_metadata,
        limitations=['HYDE release directory naming and NetCDF declared version must both remain visible',
            'The rectangle is not identical to the game-province brackets',
            'No numerical historical confidence interval or hectare allocation is inferred',
            'Raster zeros remain reconstruction estimates, not evidence of no historical livelihood'],
        source_hashes=source_hashes)
    (output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    print(json.dumps(run(parser.parse_args().output),indent=2))
