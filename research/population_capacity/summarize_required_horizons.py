"""Export compatible research ledgers and diagnostic maps, never game inputs."""
from pathlib import Path
import json,hashlib
import numpy as np
import polars as pl
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
ROOT=Path(__file__).resolve().parents[2]

def run():
    out=ROOT/'artifacts/data/population_simulation/repair_round_23'
    source=out/'historical_extent_correction'
    state=pl.read_parquet(source/'starting_ledger.parquet')
    history=pl.read_parquet(source/'checkpoints.parquet')
    state.select('location_tag',pl.col('base_population_capacity').alias('population_capacity')).write_csv(out/'candidate_capacity.csv')
    state.select('location_tag','area_km2','base_population_capacity','infrastructure_population_capacity',
        'urban_population_allowance','local_population_capacity',*[c for c in state.columns if c.startswith(('physical__','capacity__'))]).write_parquet(out/'component_ledger.parquet')
    state.select('location_tag','development','historical_system_id','management_evidence','management_inferred_analogue',
        'management_development_low','management_development_high').write_csv(out/'development_ledger.csv')
    state.select('location_tag','remaining_clearing_capacity','remaining_water_capacity','crop_fallow_block_km2',
        'clearable_wild_land_km2_p50','open_conversion_land_km2_p50','water_managed_fields_km2',
        'historical_area_conflict_km2','historical_requested_fields_km2','historical_extent_exceeds_crop_mixture_km2').write_csv(out/'opportunity_ledger.csv')
    final=history.filter(pl.col('year')==200).select('location_tag',pl.col('total_population').alias('final_population'))
    state=state.join(final,on='location_tag',validate='1:1',maintain_order='left')
    area=state['area_km2'].to_numpy();base=state['base_population_capacity'].to_numpy();infra=state['infrastructure_population_capacity'].to_numpy()
    p0=state['total_population'].to_numpy()
    retention=np.divide(state['final_population'].to_numpy(),p0,out=np.full(len(p0),np.nan),where=p0>0)
    panels=[('Starting capacity density',state['local_population_capacity'].to_numpy()*1000/area,LogNorm(.01,1000),'people/km²'),
      ('Starting development',state['development'].to_numpy(),None,'0–100'),
      ('Active infrastructure share',np.divide(infra,base+infra,out=np.zeros(len(base)),where=base+infra>0),None,'0–1'),
      ('Unvalidated remaining opportunity',(state['remaining_clearing_capacity']+state['remaining_water_capacity']).to_numpy()*1000/area,LogNorm(.01,1000),'flat support people/km²'),
      ('Year 200 population / initial',retention,LogNorm(.1,10),'ratio'),
      ('Inferred farm-system management',state['management_inferred_analogue'].cast(pl.Float64).to_numpy(),None,'1 = still inferred')]
    fig,axes=plt.subplots(3,2,figsize=(15,12),constrained_layout=True)
    for ax,(title,values,norm,label) in zip(axes.flat,panels):
        a=ax.scatter(state['calibrated_lon'],state['calibrated_lat'],c=np.maximum(values,.0001) if norm else values,
            norm=norm,s=2,cmap='viridis',vmin=None if norm else 0,vmax=None if norm else (100 if 'development' in title else 1),rasterized=True)
        ax.set(title=title,xlim=(-180,180),ylim=(-60,80),xlabel='Longitude',ylabel='Latitude',facecolor='#edf0f2')
        fig.colorbar(a,ax=ax,label=label,shrink=.8)
    fig.suptitle('Round 23 candidate — NOT ACCEPTED — location centroids',fontsize=15)
    fig.savefig(out/'candidate_maps.png',dpi=140);plt.close(fig)
    files=[source/'starting_ledger.parquet',source/'checkpoints.parquet',out/'candidate_capacity.csv',out/'component_ledger.parquet',out/'development_ledger.csv',out/'opportunity_ledger.csv',out/'active_modifiers/active_modifier_ledger.parquet']
    manifest={'model_accepted':False,'game_export_ready':False,'required_horizons':[100,200],
        'capacity_csv_semantics':'natural/static base in game units; not total developed capacity',
        'source_run':json.loads((source/'manifest.json').read_text()),
        'artifacts':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
        'report':'research/population_capacity/round_23_findings.md',
        'limitations':'Regional acceptance, broad historical evidence, source holdouts, water budgets and complete active-effect scope remain unresolved.'}
    (out/'candidate_manifest.json').write_text(json.dumps(manifest,indent=2,default=str))
    print(out/'candidate_maps.png')
if __name__=='__main__':run()
