from pathlib import Path
import polars as pl
from prosper_or_perish_constructor.worldbuilder.contract import load_config,load_contract
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root
from prosper_or_perish_constructor.worldbuilder.start_placement import load_pops
from eu5gameparser.clausewitz.parser import parse_file
r=Path.cwd(); c=load_contract(load_config(r,r/'constructor.toml').handover)
print('attributes',c.location_attributes.columns)
print(c.location_attributes.filter(pl.col('location_tag').is_in(['jiaxing','changshu','ningguo','linan','lin_an','huating','nanhui','anji','dongyang'])).to_dicts())
v=vanilla_root(r,r/'constructor.toml'); pops=load_pops(v)
print('cultures', {k: [(p.culture,p.size_k) for p in pops.get(k,[])] for k in ['jiaxing','changshu','ningguo','linan','lin_an','huating','nanhui','anji','dongyang']})
for p in (v/'game/in_game/common/culture_groups').glob('*.txt'):
 d=parse_file(p)
 for e in d.entries:
  if 'chinese' in str(e.key): print(p.name,e)
print('gates',c.building_types.select('building','gate_json').to_dicts())
print('baseline',pl.read_parquet(r/'data/vanilla/locations_with_raw_material.parquet').columns)
