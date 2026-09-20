"""Prepare a bounded historical-area experiment without population allocation."""
import argparse
import hashlib
import json
from pathlib import Path

import polars as pl

from prosper_or_perish_constructor.simulation.regional_extent import allocate_regional_fields
from prosper_or_perish_constructor.simulation.historical_model import known_land_for_evidenced_fields


def run(ledger, base_assignments, output, boundary, weights, group_contract=None):
    root=Path(__file__).resolve().parents[2]
    contract_path=Path(__file__).with_name('upper_nile_allocation_experiment.json')
    contract=json.loads(contract_path.read_text())
    source=root/contract['source_path']
    if hashlib.sha256(source.read_bytes()).hexdigest()!=contract['source_sha256']:
        raise ValueError('Historical area source hash mismatch')
    if boundary not in contract['boundaries'] or weights not in contract['weight_methods']:
        raise ValueError('Unfrozen boundary or allocation method')
    # Population is deliberately absent from this read and from the allocator.
    columns=['location_tag','province','region','has_river','area_km2','crop_fallow_block_km2',
             'clearable_wild_land_km2_p50','open_conversion_land_km2_p50',
             'hyde_cropland_area_km2','cropland_fraction_1300']
    state=pl.read_parquet(ledger,columns=columns)
    selected=(pl.col('province').is_in(contract['core_provinces']) &
              ~pl.col('location_tag').is_in(contract['excluded_locations'])) | pl.col('location_tag').is_in(contract['boundaries'][boundary])
    land=state.filter(selected).sort('location_tag')
    weight=pl.col('hyde_cropland_area_km2') if weights=='hyde' else pl.col('cropland_fraction_1300')*pl.col('area_km2')
    inputs=land.select('location_tag',
        pl.col('crop_fallow_block_km2').alias('current_fields_km2'),
        (pl.col('clearable_wild_land_km2_p50')+pl.col('open_conversion_land_km2_p50')).alias('remaining_convertible_km2'),
        weight.alias('allocation_weight'))
    extra_sources=[]; group_audit=[]
    if group_contract:
        if (output/'assignments.json').exists():
            raise FileExistsError('Use a fresh grouped experiment output; do not leave stale assignments beside a rejected attempt')
        grouped=json.loads(group_contract.read_text())
        budget_contract=grouped.get('land_budget','existing_conversion_opportunity')
        target_contract=grouped.get('area_interpretation','total_fields')
        if budget_contract not in ('existing_conversion_opportunity','evidenced_known_land') or target_contract not in ('total_fields','basin_component_minimum'):
            raise ValueError('Unknown grouped land or area contract')
        if budget_contract=='evidenced_known_land':
            recovery=pl.read_parquet(ledger,columns=['location_tag','retained_wild_land_km2',
                'extensive_grazing_land_km2','unclassified_land_km2'])
            recovery=recovery.with_columns(pl.Series('_evidenced_land_budget',known_land_for_evidenced_fields(recovery)))
            inputs=inputs.join(recovery.select('location_tag','_evidenced_land_budget'),on='location_tag',validate='1:1').with_columns(
                pl.col('_evidenced_land_budget').alias('remaining_convertible_km2')).drop('_evidenced_land_budget')
        table_path=root/grouped['source_table']
        if hashlib.sha256(table_path.read_bytes()).hexdigest()!=grouped['source_table_sha256']:
            raise ValueError('Grouped basin source transcription changed')
        if grouped['regional_total_km2']!=contract['source_fields_km2']:
            raise ValueError('Grouped and regional historical totals disagree')
        table=pl.read_csv(table_path)
        group_tags=[tag for group in grouped['groups'] for tag in group['location_tags']]
        if len(set(group_tags))!=len(group_tags) or set(group_tags)!=set(inputs['location_tag']):
            raise ValueError('Grouped allocation must partition the selected locations exactly')
        provinces=[group['source_province'] for group in grouped['groups']]
        if len(set(provinces))!=len(provinces):
            raise ValueError('Source province counted more than once')
        quantities={row['province']:row[grouped['source_weight_column']] for row in table.iter_rows(named=True)}
        if set(provinces)-set(quantities):
            raise ValueError('Unknown source province')
        denominator=sum(quantities[p] for p in provinces)
        if denominator<=0:
            raise ValueError('Grouped basin source has no positive area')
        allocations=[]
        for group in grouped['groups']:
            subset=inputs.filter(pl.col('location_tag').is_in(group['location_tags']))
            source_target=contract['source_fields_km2']*quantities[group['source_province']]/denominator
            low=subset['current_fields_km2'].sum()
            high=low+subset['remaining_convertible_km2'].sum()
            target=max(source_target,low) if target_contract=='basin_component_minimum' else source_target
            feasible=low-1e-8<=target<=high+1e-8
            group_audit.append(dict(source_province=group['source_province'],target_fields_km2=target,
                source_component_km2=source_target,unclassified_existing_excess_km2=max(low-source_target,0.),
                current_fields_km2=low,maximum_fields_km2=high,physically_feasible=feasible))
            if feasible:
                allocations.append(allocate_regional_fields(subset,target).with_columns(
                    pl.lit(group['source_province']).alias('source_province'),
                    (pl.col('allocated_fields_km2')*(source_target/target)).alias('inferred_basin_component_km2')))
        output.mkdir(parents=True,exist_ok=True)
        pl.DataFrame(group_audit).write_csv(output/'group_physical_feasibility.csv')
        if not all(row['physically_feasible'] for row in group_audit):
            (output/'physical_rejection.json').write_text(json.dumps(dict(model_accepted=False,
                assignments_written=False,groups=group_audit,group_contract_sha256=hashlib.sha256(group_contract.read_bytes()).hexdigest()),indent=2)+'\n')
            raise ValueError('Historical group targets conflict with physical fields; see group_physical_feasibility.csv')
        allocation=pl.concat(allocations).sort('location_tag')
        extra_sources=[group_contract,table_path,root/grouped['source_evidence']]
    else:
        allocation=allocate_regional_fields(inputs,contract['source_fields_km2'])
    assignments=json.loads(base_assignments.read_text())
    system=next(s for s in assignments['systems'] if s['id']=='nile_basin_fields')
    tags=allocation['location_tag'].to_list()
    others=state.filter((pl.col('region')=='egypt_region') & pl.col('has_river') & ~pl.col('location_tag').is_in(tags))['location_tag'].to_list()
    system['selector']={'location_tag':sorted(others)}
    for row in allocation.iter_rows(named=True):
        added=json.loads(json.dumps(system))
        added.update(id='upper_nile_extent_'+row['location_tag'],selector={'location_tag':[row['location_tag']]},
            cultivated_area_km2_range=[row['allocated_fields_km2']]*2,
            source_ids=[contract_path.name,*([group_contract.name] if group_contract else [])],
            interpretation='Exploratory bounded allocation of dated regional basin extent; grouped dated spatial analogy when specified. See frozen contracts. No population fitting.')
        assignments['systems'].append(added)
    assignments['status']='exploratory Upper Nile extent; unaccepted'
    assignments['source_hashes']={str((base_assignments.parent/k).resolve()):v for k,v in assignments.get('source_hashes',{}).items()}
    for p in [contract_path,source,ledger,*extra_sources]:
        assignments['source_hashes'][str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest()
    output.mkdir(parents=True,exist_ok=True)
    allocation.write_csv(output/'allocation.csv')
    path=output/'assignments.json';path.write_text(json.dumps(assignments,indent=2)+'\n')
    report=dict(model_accepted=False,boundary=boundary,weights=weights,source_total_km2=contract['source_fields_km2'],
        allocated_total_km2=allocation['allocated_fields_km2'].sum(),
        added_fields_km2=allocation['added_fields_km2'].sum(),
        physically_saturated_locations=int(allocation['allocation_hit_bound'].sum()),target_tags=tags,
        group_physical_feasibility=group_audit,
        source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [base_assignments,ledger,contract_path,source,Path(__file__),*extra_sources]},
        limitations=contract['limitations']+(grouped['uncertainty'] if group_contract else []))
    (output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    return path, report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ['ledger','base-assignments','output']:parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--boundary',required=True)
    parser.add_argument('--weights',required=True)
    parser.add_argument('--group-contract',type=Path)
    args=parser.parse_args()
    _,report=run(args.ledger,args.base_assignments,args.output,args.boundary,args.weights,args.group_contract)
    print(json.dumps(report,indent=2))
