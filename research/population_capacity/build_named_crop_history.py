"""Replay existing history and add source-pinned named-system attestations."""
import argparse
import hashlib
import json
from pathlib import Path
import tomllib
import numpy as np
import shapely
from pyogrio.raw import read as read_ogr
import polars as pl
from prosper_or_perish_population_capacity.crop_history import load_crop_history_registry, build_crop_history_location_frame
from prosper_or_perish_population_capacity.crop_labels import _location_frame

ROOT=Path(__file__).resolve().parents[2]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def build(evidence_path, baseline_registry, baseline_labels, output, config_output, annual_output):
    evidence=json.loads(evidence_path.read_text())
    source_path=ROOT/evidence['local_path']
    if sha(source_path)!=evidence['source']['object_sha256']:
        raise ValueError('Named-system source checksum mismatch')
    raw=tomllib.loads(baseline_registry.read_text())
    expected=[c['crop'] for c in raw['crop']]
    original_evidence=(baseline_registry.parent/raw['evidence']['path']).resolve()
    old=load_crop_history_registry(baseline_registry,original_evidence,expected_crops=expected)
    text=baseline_registry.read_text()
    for section,key in [('evidence','path'),('mapping','path'),('mapping','audit_path'),('domains','path')]:
        value=raw[section][key]
        resolved=(baseline_registry.parent/value).resolve().as_posix()
        text=text.replace(f'{key} = "{value}"', f'{key} = "{resolved}"')
    existing=[x for x in raw['source'] if x['source_id']==evidence['source']['source_id']]
    if existing:
        if len(existing)!=1 or existing[0]['object_sha256']!=evidence['source']['object_sha256']:
            raise ValueError('Existing source identity differs')
    else:
        text+='\n[[source]]\n'+'\n'.join(f'{k} = {json.dumps(v)}' for k,v in evidence['source'].items())+'\n'
    for record in evidence['records']:
        text+='\n[[system_evidence]]\n'+'\n'.join(f'{k} = {json.dumps(v)}' for k,v in record.items())+'\n'
    output.mkdir(parents=True,exist_ok=True)
    added_domains=[]
    if evidence.get('negative_domains'):
        boundary=ROOT/'artifacts/data/population_capacity/crop_history_sources/natural_earth_admin0/ne_50m_admin_0_countries.zip'
        if sha(boundary)!=raw['domains']['boundary_object_sha256']:
            raise ValueError('Domain boundary checksum mismatch')
        metadata,_,wkb,fields=read_ogr(boundary,columns=['ADM0_A3'])
        if metadata['crs']!='EPSG:4326':
            raise ValueError('Domain boundary CRS differs')
        country_codes=np.asarray(fields[0])
        geometries=shapely.from_wkb(wkb)
        domains=json.loads((baseline_registry.parent/raw['domains']['path']).read_text())
        for domain in evidence['negative_domains']:
            if set(domain['country_codes'])-set(country_codes):
                raise ValueError('Unknown domain country code')
            geometry=shapely.make_valid(shapely.union_all(geometries[np.isin(country_codes,domain['country_codes'])]))
            if geometry.is_empty or not geometry.is_valid:
                raise ValueError('Invalid crop-history domain')
            properties=dict(domain_id=domain['domain_id'],evidence_state='known_unavailable',
                start_year=-9999,end_year=1337,evidence_kind='cited_domain_time_exclusion',
                crops=domain['crops'],source_ids=[evidence['source']['source_id']],
                source_object_sha256s=[evidence['source']['object_sha256']],
                citation_urls=[evidence['source']['citation_url']],notes=domain['interpretation'])
            domains['features'].append(dict(type='Feature',properties=properties,geometry=json.loads(shapely.to_geojson(geometry))))
            added_domains.append((geometry,domain['crops']))
        domain_path=output/'crop_history_domains.geojson'
        domain_path.write_text(json.dumps(domains,sort_keys=True,separators=(',',':'))+'\n')
        old_path=(baseline_registry.parent/raw['domains']['path']).resolve().as_posix()
        text=text.replace(f'path = "{old_path}"',f'path = "{domain_path.as_posix()}"')
        text=text.replace(raw['domains']['sha256'],sha(domain_path))
    registry_path=output/'crop_history_registry.toml'
    registry_path.write_text(text)
    new=load_crop_history_registry(registry_path,original_evidence,expected_crops=expected)
    config_path=ROOT/'population_capacity.toml'
    config=tomllib.loads(config_path.read_text())
    locations=_location_frame(pl.read_parquet(ROOT/config['carrying_capacity']['geometry']))
    before=build_crop_history_location_frame(locations,old,resolve_uncertain=True)
    after=build_crop_history_location_frame(locations,new,resolve_uncertain=True)
    labels=pl.read_parquet(baseline_labels)
    replay=labels.select('location_tag','crop','historical_availability').unique().join(
        before.select('location_tag','crop',pl.col('historical_availability').alias('replayed')),
        on=['location_tag','crop'],how='left',validate='1:1')
    if replay.filter(pl.col('replayed').is_null()|(pl.col('historical_availability')!=pl.col('replayed'))).height:
        raise ValueError('Baseline labels do not replay against their registry')
    delta=before.select('location_tag','crop',pl.col('historical_availability').alias('before')).join(
        after.select('location_tag','crop',pl.col('historical_availability').alias('after')),
        on=['location_tag','crop'],validate='1:1').filter(pl.col('before')!=pl.col('after'))
    allowed={(tag,crop) for x in evidence['records'] for tag in x['location_tags'] for crop in x['crops']}
    for geometry,crops in added_domains:
        selected=locations.filter(pl.Series(shapely.covers(geometry,shapely.points(locations['longitude'].to_numpy(),locations['latitude'].to_numpy()))))
        allowed.update((tag,crop) for tag in selected['location_tag'] for crop in crops)
    if set(delta.select('location_tag','crop').iter_rows())-allowed:
        raise ValueError('Named-system labels expanded beyond their crosswalk')
    replaced=[c for c in after.columns if c in labels.columns and c not in ('location_tag','crop')]
    updated=labels.drop(replaced).join(after.select('location_tag','crop',*replaced),
        on=['location_tag','crop'],how='left',validate='m:1',maintain_order='left').select(labels.columns)
    if updated.height!=labels.height or not updated.drop(replaced).equals(labels.drop(replaced)):
        raise ValueError('Crop-history update changed physical label inputs')
    updated.write_parquet(output/'crop_mode_labels.parquet')
    delta.write_csv(output/'availability_changes.csv')
    sample_link=output/'crop_mode_samples'
    sample_target=(ROOT/'artifacts/data/population_capacity/crop_mode_samples').resolve()
    if sample_link.exists():
        if sample_link.resolve()!=sample_target:
            raise ValueError('Physical sample link differs')
    else:
        sample_link.symlink_to(sample_target,target_is_directory=True)
    configured=config_path.read_text()
    for key,value in [('crop_mode_labels',output/'crop_mode_labels.parquet'),
                      ('crop_risk_scenarios_root',annual_output),('crop_history_registry',registry_path),
                      ('crop_history_evidence',original_evidence)]:
        configured=configured.replace(f'{key} = "{config["carrying_capacity"][key]}"', f'{key} = "{value.resolve().as_posix()}"')
    config_output.write_text(configured)
    result=dict(accepted=False,baseline_registry_sha256=sha(baseline_registry),baseline_labels_sha256=sha(baseline_labels),
        evidence_sha256=sha(evidence_path),source_sha256=sha(source_path),builder_sha256=sha(Path(__file__)),
        registry_sha256=sha(registry_path),labels_sha256=sha(output/'crop_mode_labels.parquet'),
        changed_crop_locations=delta.height,changed_locations=delta['location_tag'].n_unique(),
        physical_labels_unchanged=True,baseline_replayed=True,negative_domains=len(added_domains),
        contract='Crop presence only; physical label inputs, harvest count and yield physics unchanged. Canonical preparation must separately audit cultivated hectares and water opportunities because the crop-mixture feasibility screen can change; no export')
    (output/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ['evidence','baseline-registry','baseline-labels','output','config-output','annual-output']:
        parser.add_argument('--'+key,type=Path,required=True)
    a=parser.parse_args()
    build(a.evidence.resolve(),a.baseline_registry.resolve(),a.baseline_labels.resolve(),a.output.resolve(),a.config_output.resolve(),a.annual_output.resolve())
