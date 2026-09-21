from pathlib import Path
from collections import defaultdict
import csv,json,re
import polars as pl
from prosper_or_perish_constructor.worldbuilder.contract import load_config,load_contract
from prosper_or_perish_constructor.worldbuilder.buildings import cap_levels,gate_matches
from prosper_or_perish_constructor.worldbuilder.start_placement import load_pops,dominant_cultures
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root
r=Path.cwd(); cfg=load_config(r,r/'constructor.toml'); c=load_contract(cfg.handover)
mod=r/'mod/Prosper or Perish (Population Growth & Food Rework)'
attrs={x['location_tag']:x for x in c.location_attributes.join(c.location_targets.select('location_tag','development'),on='location_tag').to_dicts()}
cultures=dominant_cultures(load_pops(vanilla_root(r,r/'constructor.toml')))
ledger=defaultdict(dict)
for m in re.finditer(r'(\w+) = \{ tag = (\w+) level = (\d+) location = (\w+) \}',(mod/'main_menu/setup/start/14_pp_worldbuilder_buildings.txt').read_text(encoding='utf-8-sig')): ledger[m[4]][m[1]]=int(m[3])
rows=[]
for tag,levels in ledger.items():
 for key in ['jiangnan_canal_network','jiangnan_hill_terraces']:
  if key not in levels: continue
  spec=cfg.niche[key]; family=spec['family']; kind=next(k for k,v in cfg.building_map.items() if v==family); t=c.building_types.filter(pl.col('building')==kind).to_dicts()[0]; a={**attrs[tag],'culture':cultures[tag]}
  scale=cfg.level_scale.get(family,1); maximum=cap_levels(json.loads(t['cap_equation_json']),a,scale,int(t['level_limit']*scale))
  assert gate_matches(spec['gate'],a) and gate_matches(json.loads(t['gate_json']),a)
  family_levels=sum(v for k,v in levels.items() if k==family or cfg.niche.get(k,{}).get('family')==family)
  assert 0<=family_levels<=maximum
  rows.append(dict(location=tag,building=key,starting_levels=levels[key],minimum=0,maximum_at_start=maximum,shared_family=family,other_family_levels=family_levels-levels[key],province=a['province'],culture=a['culture']))
out=r/'artifacts/data/worldbuilder/jiangnan_distribution.csv'
with out.open('w') as f:
 w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(sorted(rows,key=lambda x:(x['building'],x['location'])))
for key in ['jiangnan_canal_network','jiangnan_hill_terraces']:
 rr=[x for x in rows if x['building']==key]; print(key,'locations',len(rr),'levels',sum(x['starting_levels'] for x in rr),'start range',min(x['starting_levels'] for x in rr),max(x['starting_levels'] for x in rr),'cap range',min(x['maximum_at_start'] for x in rr),max(x['maximum_at_start'] for x in rr))
before=pl.read_csv(r/'tmp/china_start_before.csv');after=pl.read_csv(r/'artifacts/data/worldbuilder/start_placement.csv')
changes=before.select('location_tag',pl.col('capacity_people').alias('before')).join(after.select('location_tag',pl.col('capacity_people').alias('after')),on='location_tag').filter(pl.col('before')!=pl.col('after'))
assert set(changes['location_tag'])<=set(x['location'] for x in rows),changes.filter(~pl.col('location_tag').is_in([x['location'] for x in rows]))
print('Capacity changes confined to the 40 regional placements; Bijnot and Cairo unchanged.')
print('owned over:',after.filter((pl.col('owner').fill_null('')!='') & (pl.col('pops_people')>pl.col('capacity_people'))).height)
print('excess:',after.filter(pl.col('owner').fill_null('')!='').select((pl.col('pops_people')-pl.col('capacity_people')).clip(0).sum()).item())
print(out)
