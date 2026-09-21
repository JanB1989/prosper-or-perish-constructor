from pathlib import Path
import json,re
import polars as pl
r=Path.cwd(); before=pl.read_csv(r/'tmp/china_start_before.csv'); after=pl.read_csv(r/'artifacts/data/worldbuilder/start_placement.csv')
names=['jiaxing','changshu','ningguo','linan','huating','nanhui','anji','dongyang']
print(after.filter(pl.col('location_tag').is_in(names)).select('location_tag','capacity_people','pops_people','over_capacity').to_dicts())
joined=before.select('location_tag',pl.col('capacity_people').alias('before')).join(after.select('location_tag',pl.col('capacity_people').alias('after')),on='location_tag')
print('comparison',joined.filter(pl.col('location_tag').is_in(names)).to_dicts())
for label,df in [('before',before),('after',after)]:
 owned=df.filter(pl.col('owner').fill_null('')!=''); print(label,'over',owned.filter(pl.col('pops_people')>pl.col('capacity_people')).height,'excess',(owned['pops_people']-owned['capacity_people']).clip(0).sum())
setup=(r/'mod/Prosper or Perish (Population Growth & Food Rework)/main_menu/setup/start/14_pp_worldbuilder_buildings.txt').read_text(encoding='utf-8-sig')
rows=[]
for m in re.finditer(r'(jiangnan_\w+) = \{ tag = (\w+) level = (\d+) location = (\w+) \}',setup): rows.append(dict(building=m[1],level=int(m[3]),location=m[4]))
print('distribution',rows)
print('unknown provinces')
from prosper_or_perish_constructor.worldbuilder.contract import load_config,load_contract
cfg=load_config(r,r/'constructor.toml'); c=load_contract(cfg.handover)
for k,s in cfg.niche.items():
 for g in s.get('gate',[]):
  for attr,vals in g.items():
   if attr in ['province','topography','climate']: print(k,attr,set(vals)-set(c.location_attributes[attr].unique()))
