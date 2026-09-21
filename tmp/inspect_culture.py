from pathlib import Path
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root
from eu5gameparser.clausewitz.parser import parse_file
r=Path.cwd(); v=vanilla_root(r,r/'constructor.toml')
for p in (v/'game/in_game/common/cultures').glob('*.txt'):
 for e in parse_file(p).entries:
  if e.key=='wu_culture': print(e)
