"""Map dated regional practice evidence, then use the canonical management hierarchy.

No regional prevalence is converted to hectares, irrigation or population targets.
The 950 CE slice is a prior with explicit continuity uncertainty, not a 1337 survey.
"""
from pathlib import Path
import hashlib
import json
import os

import numpy as np
import pandas as pd
import pyogrio
import pyproj
import shapely

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / 'research/population_capacity'
CACHE = ROOT / 'artifacts/data/population_capacity/repair_round_56/sources/archaeoglobe'


def build():
    manifest = json.loads((CACHE / 'manifest.json').read_text())
    for source in manifest:
        assert hashlib.sha256((CACHE/source['file']).read_bytes()).hexdigest() == source['sha256']
    state_path = ROOT/'artifacts/data/population_simulation/repair_round_56/preflight/starting_ledger.parquet'
    state = pd.read_parquet(state_path)
    metadata, table = pyogrio.read_arrow(CACHE/'ArchaeGLOBE_Regions.shp')
    geometries = shapely.from_wkb(table['wkb_geometry'].to_numpy())
    x, y = pyproj.Transformer.from_crs('EPSG:4326', metadata['crs'], always_xy=True).transform(
        state.calibrated_lon, state.calibrated_lat)
    pairs = shapely.STRtree(geometries).query(shapely.points(x, y), predicate='intersects')
    if len(np.unique(pairs[0])) != len(pairs[0]):
        raise ValueError('Ambiguous historical region boundaries require explicit resolution')
    # Upstream .tab is actually comma-separated Latin-1. Preserve literal None.
    source = pd.read_csv(CACHE/'ARCHAEOGLOBE_CONSENSUS_ASSESSMENT.tab', encoding='latin1', keep_default_na=False)
    crosswalk = pd.DataFrame({'location_tag': state.location_tag.iloc[pairs[0]].to_numpy(),
        'archaeoglobe_region': table['Archaeo_ID'].to_numpy()[pairs[1]]}).merge(
        source[['Region','Label','INAG_1KBP','EXAG_1KBP','PAS_1KBP','INAG_1500CE']],
        left_on='archaeoglobe_region', right_on='Region', validate='many_to_one')
    crosswalk = state[['location_tag']].merge(crosswalk, how='left', validate='one_to_one')
    crosswalk['mapping_status'] = np.where(crosswalk.Region.notna(), 'centroid_inside_region', 'unmapped_no_nearest_imputation')
    crosswalk.to_csv(CACHE/'location_practice_crosswalk.csv', index=False)
    data = json.loads((RESEARCH/'historical_assignments_round_56.json').read_text())
    rules = []
    # Regional prevalence indicates applicability of an uncertain practice analogue,
    # never that every field used this system. No water-management score is granted.
    assessments = {'Widespread': ([2,0,2,2], [18.75,50]),
                   'Common': ([2,0,1,2], [18.75,43.75])}
    for level, (scores, bounds) in assessments.items():
        tags = crosswalk.loc[crosswalk.INAG_1KBP == level, 'location_tag'].tolist()
        rules.append(dict(id='archaeoglobe_950_intensive_'+level.lower(), tier=1,
            selector={'location_tag':tags}, valid_years=[1337,1337], scores=scores,
            development_range=bounds, source_ids=['archaeoglobe_2019_950CE_regional_prior']))
    # Dated regional/provincial texts and named systems outrank the coarse survey.
    rules += [r for r in data['management_hierarchy']['rules'] if r['tier'] > 1]
    data['management_hierarchy']['rules'] = rules
    data['status'] = 'round56 historical-practice variant; frozen before simulation; unaccepted'
    evidence = dict(schema_version=1, source='Stephens et al. 2019, doi:10.1126/science.aax1192',
        archive='https://doi.org/10.7910/DVN/6ZXAGT', source_commit=manifest[0]['commit'],
        data_license='CC0; attribution requested, per source README',
        source_time='1KBP (approximately 950 CE); no interpolation from 1500 CE',
        target_year=1337, mapping='Canonical calibrated centroids transformed into source Eckert IV CRS; no nearest-region imputation',
        matched_locations=int(crosswalk.Region.notna().sum()), unmapped_locations=int(crosswalk.Region.isna().sum()),
        assessment=assessments, population_inputs=False, potential_inputs=False,
        uncertainty=['Regional prevalence is not a local survey or a field intensity measurement.',
            'Continuity from 950 to 1337 is an explicit inference; later observations are diagnostic only.',
            'Common means 1-20% and widespread >20% regional prevalence; these are not hectare assignments.',
            'Game development scores are shared uncertain analogues, not measured historical values.',
            'Named local evidence overrides this layer. No water hectares or extra crop cycles granted.',
            'HYDE and ArchaeoGLOBE may share evidence; this layer is not independent validation.'],
        baseline='round56 first frozen candidate; food/growth/scale unchanged',
        input_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            [Path(__file__),state_path,CACHE/'location_practice_crosswalk.csv',RESEARCH/'historical_assignments_round_56.json']})
    ep = RESEARCH/'archaeoglobe_round_56_evidence.json'
    ep.write_text(json.dumps(evidence,indent=2)+'\n')
    for path in [ep,CACHE/'location_practice_crosswalk.csv',*[CACHE/s['file'] for s in manifest]]:
        data['source_hashes'][os.path.relpath(path,RESEARCH)] = hashlib.sha256(path.read_bytes()).hexdigest()
    target = RESEARCH/'historical_assignments_round_56_archaeoglobe.json'
    target.write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps({'assignments':str(target),**evidence},indent=2))


if __name__ == '__main__':
    build()
