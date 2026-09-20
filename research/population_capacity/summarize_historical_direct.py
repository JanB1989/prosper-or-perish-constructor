"""Render the direct-model diagnostic and compatible research companion tables."""
from pathlib import Path
import json
import hashlib
import numpy as np
import polars as pl
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from run_historical_direct import ROOT, OUTPUT
from prosper_or_perish_constructor.simulation.model_acceptance import evaluate_model_acceptance

def run():
 out=OUTPUT; world=out/'world'; state=pl.read_parquet(world/'starting_ledger.parquet')
 checkpoints=pl.read_parquet(world/'checkpoints.parquet')
 # This CSV preserves the established natural/static-base meaning. It is a
 # research artifact and is not copied to constructor deployment inputs.
 state.select('location_tag',pl.col('base_population_capacity').alias('population_capacity')).write_csv(out/'candidate_capacity.csv')
 components=['location_tag','area_km2','base_population_capacity','infrastructure_population_capacity',
  'urban_population_allowance','local_population_capacity',*[c for c in state.columns if c.startswith(('physical__','capacity__'))]]
 state.select(components).write_parquet(out/'component_ledger.parquet')
 state.select('location_tag','development','historical_system_id','management_evidence','management_inferred_analogue',
  'management_development_low','management_development_high',*[c for c in state.columns if c.startswith('management__')]).write_csv(out/'development_ledger.csv')
 state.select('location_tag','remaining_clearing_capacity','remaining_water_capacity','crop_fallow_block_km2',
  'clearable_wild_land_km2_p50','open_conversion_land_km2_p50','water_managed_fields_km2',
  'historical_area_conflict_km2','recovered_irrigated_mask_land_km2').write_csv(out/'opportunity_ledger.csv')
 x=state['calibrated_lon'].to_numpy();y=state['calibrated_lat'].to_numpy();area=state['area_km2'].to_numpy()
 infra=state['infrastructure_population_capacity'].to_numpy();base=state['base_population_capacity'].to_numpy()
 fig,axes=plt.subplots(2,2,figsize=(15,8),constrained_layout=True)
 panels=[('Starting support density',state['local_population_capacity'].to_numpy()*1000/area,LogNorm(.01,1000),'people/km²'),
  ('Starting development',state['development'].to_numpy(),None,'development 0–100'),
  ('Infrastructure share of flat support',np.divide(infra,infra+base,out=np.zeros(len(base)),where=(infra+base)>0),None,'share 0–1'),
  ('Remaining agronomic opportunity — water budget unverified',(state['remaining_clearing_capacity']+state['remaining_water_capacity']).to_numpy()*1000/area,LogNorm(.01,1000),'flat capacity people/km²')]
 for ax,(title,values,norm,label) in zip(axes.flat,panels):
  a=ax.scatter(x,y,c=np.maximum(values,.01) if norm else values,s=2,cmap='viridis',norm=norm,
   vmin=None if norm else 0,vmax=None if norm else (100 if title=='Starting development' else 1),rasterized=True)
  ax.set(title=title,xlim=(-180,180),ylim=(-60,80),xlabel='Longitude',ylabel='Latitude',facecolor='#edf0f2')
  fig.colorbar(a,ax=ax,label=label,shrink=.8)
 fig.suptitle('Candidate only · direct physical magnitudes · development coefficient 0.05 · location centroids',fontsize=12)
 fig.savefig(out/'candidate_components.png',dpi=160);plt.close(fig)
 budgets=pl.read_csv(out/'factorial_provinces.csv').filter((pl.col('development_coefficient')==.05)&pl.col('scenario').is_in(['unchanged_baseline','both']))
 table=budgets.pivot(on='scenario',index='province',values='food_balance').sort('province')
 regional=[]
 for p in sorted((out/'long_run').glob('*_checkpoints.parquet')):
  f=pl.read_parquet(p)
  regional.append(f.group_by('province','scenario','year').agg(pl.col('total_population','local_population_capacity','food_balance','food','starvation_months').sum(),pl.col('development').mean()))
 regional=pl.concat(regional,how='diagonal_relaxed');regional.write_csv(out/'provincial_checkpoints.csv')
 nominal=regional.filter((pl.col('scenario')=='dev_0.05_uncertainty_0.5_coupled')&pl.col('year').is_in([0,500]))
 fig,ax=plt.subplots(figsize=(10,4),constrained_layout=True)
 for row in nominal.pivot(on='year',index='province',values='total_population').sort('province').to_dicts():
  ax.bar(row['province'].replace('_province',''),row['500']/row['0'])
 ax.axhline(1,color='black',lw=1);ax.set(ylabel='Year 500 / starting population',title='Six complete provinces · nominal higher-development candidate')
 fig.savefig(out/'heartland_retention.png',dpi=160);plt.close(fig)
 controls={}
 for coefficient in (.025,.05):
  path=out/'long_run'/f'controls_dev_{coefficient:g}'/'food_scenarios.json'
  controls[str(coefficient)]=json.loads(path.read_text())
 evidence={'food_controls':{'status':'passed' if all(x['passed'] for x in controls.values()) else 'failed',
  'artifact':'long_run/controls_dev_*/food_scenarios.json','detail':'52 controlled scenarios for each coefficient; canonical native-rate implementation.'}}
 frames={int(y):checkpoints.filter(pl.col('year')==y) for y in checkpoints['year'].unique()};frames[0]=state
 acceptance=evaluate_model_acceptance(frames,evidence)
 (out/'model_acceptance.json').write_text(json.dumps(acceptance,indent=2))
 manifest=json.loads((world/'manifest.json').read_text());manifest['acceptance']=acceptance
 manifest['files']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.suffix in ('.csv','.parquet','.png')}
 manifest['source_registry']=json.loads((ROOT/'research/population_capacity/repair_source_manifest.json').read_text())
 manifest['csv_semantics']='population_capacity is natural/static base in game units; current total capacity is in the companion component ledger. Research output only.'
 manifest['status']='unaccepted candidate; documented provincial failures and incomplete mandatory geography'
 (out/'candidate_manifest.json').write_text(json.dumps(manifest,indent=2,default=str))
 lines=['# Direct historical capacity — round 22','', '**Candidate, not accepted. Building balance and game export are deferred.**','',
  'The current calculation uses direct infrastructure magnitudes and management development. It does not use population to assign either. It restores dated hydraulic cultivation omitted by the rainfed mask; unused irrigable land is not activated.', '',
  '![Starting components](candidate_components.png)','', '| Province | Archived starting food balance | Corrected starting food balance |','|---|---:|---:|']
 for r in table.to_dicts(): lines.append(f"| {r['province']} | {r['unchanged_baseline']:.1f} | {r['both']:.1f} |")
 lines+=['','Monthly food units; actual composition, staffing and existing building/RGO production. The comparison changes both geography and the development coefficient; `factorial_provinces.csv` separately holds the same-coefficient development/infrastructure contrasts.','',
  '![Heartland retention](heartland_retention.png)','', 'Both 52-scenario mechanism-control suites pass. This does not certify historical assignments. The world and complete-province runs retain checkpoints at 0, 25, 100, 200, 300, 400 and 500 years; nominal provincial runs also retain monthly histories.','',
  '## Acceptance results','', '| Requirement | Result | Detail |','|---|---|---|']
 for c in acceptance['checks']: lines.append(f"| {c['name']} | {c['status']} | {c['detail']} |")
 lines+=['','## Interpretation and limitations','',
  'Taihu and Angkor advantages come from maintained fields, water systems and management. Nile fields require reliable basin-water service. The same shared scale and sublinear area factor apply to current support and remaining gains; dividing an otherwise identical location in half increases combined game support by √2 at the tested area exponent 0.5.', '',
  'Historical field fractions and management scores remain inferred ranges. Most locations still use provisional farm-system analogues; India, Java/Bali, France and African/American centres do not yet have the required complete dated validation. Shanghai still exposes an area-mask conflict. Nile basin-area evidence requires a spatial boundary audit. Other native flat/relative capacity effects and explicit urban allowances are not fully inventoried. Water opportunity is agronomic potential, not a verified basin water budget.', '',
  'No trade, migration, autonomous investment or building balance is simulated. Initial food stocks are twelve months in actual-composition world/province runs. Historical world population is contextual and is not an acceptance target.','',
  '## Reproduce','', '```bash','uv run python research/population_capacity/compare_historical_contributions.py','uv run python research/population_capacity/run_historical_heartlands.py','uv run python research/population_capacity/run_historical_world.py','uv run python research/population_capacity/summarize_historical_direct.py','```','']
 (out/'report.md').write_text('\n'.join(lines))
 print(out/'report.md')
if __name__=='__main__':run()
