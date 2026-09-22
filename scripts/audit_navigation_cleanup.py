"""Read-only regression audit against the pushed pre-cleanup checkpoint."""
from pathlib import Path
from collections import defaultdict
import json
import math
import subprocess
import yaml
from eu5gameparser.clausewitz.parser import parse_text,parse_file

ROOT=Path(__file__).resolve().parents[1]
MOD=ROOT/'mod/Prosper or Perish (Population Growth & Food Rework)'
REF='checkpoint/pre-river-navigation-cleanup-20260922'
SETUP='main_menu/setup/start/14_pp_worldbuilder_buildings.txt'

def old(rel):
    return subprocess.check_output(['git','show',REF+':'+str(rel)],cwd=ROOT).decode('utf-8-sig')

def bindings(text):
    manager=next(e.value for e in parse_text(text).entries if e.key=='building_manager')
    result=[]
    for e in manager.entries:
        values={v.key:v.value for v in e.value.entries}
        result.append((e.key,values['location'],values['level']))
    return result

def weights(keys,previous=False):
    values={}
    for key in sorted(keys):
        p=Path('blueprints/accepted/buildings')/(key+'.yml')
        blueprint=yaml.safe_load(old(p) if previous else (ROOT/p).read_text())
        body=parse_text(blueprint['building']['body'])
        raw=next(e.value for e in body.entries if e.key=='raw_modifier')
        values[key]=float(next(e.value for e in raw.entries if e.key=='local_population_capacity'))
    return values

def totals(rows,unit):
    out=defaultdict(float)
    for key,tag,n in rows:out[tag]+=n*unit[key]
    return out

def main():
    before=bindings(old(MOD.relative_to(ROOT)/SETUP))
    after=bindings((MOD/SETUP).read_text(encoding='utf-8-sig'))
    a=totals(before,weights({r[0] for r in before},True))
    b=totals(after,weights({r[0] for r in after}))
    mismatches={tag:(a[tag],b[tag]) for tag in a.keys()|b.keys() if not math.isclose(a[tag],b[tag],abs_tol=1e-8)}
    assert not mismatches,mismatches
    scripts=[*MOD.glob('in_game/common/road_types/pp_navigation*.txt'),
             *MOD.glob('in_game/common/scripted_effects/pp_navigation*.txt'),
             *MOD.glob('in_game/common/scripted_triggers/pp_navigation*.txt'),
             *MOD.glob('in_game/common/on_action/pp_navigation*.txt'),
             MOD/'in_game/gfx/map/map_modes/pp_river_navigation.txt']
    for path in scripts:parse_file(path)
    roads=parse_file(MOD/'in_game/common/road_types/pp_navigation.txt')
    levels={e.key:next(v.value for v in e.value.entries if v.key=='level') for e in roads.entries}
    assert levels['pp_navigation_improved']==max(levels.values())
    for rel in ['main_menu/setup/start/21_pp_wb_attribute_modifiers.txt','in_game/common/on_action/pp_wb_apply_attribute_modifiers.txt']:
        text=(MOD/rel).read_text(encoding='utf-8-sig')
        assert 'pp_nav_cancel' not in text and 'pp_nav_original_level' not in text
    report={'passed':True,'baseline':REF,'starting_capacity_locations_compared':len(a.keys()|b.keys()),
            'starting_capacity_mismatches':mismatches,'navigation_scripts_parsed':len(scripts),
            'improved_road_highest_level':True,'duplicate_river_compensation_removed':True,
            'engine_verification':'Fresh campaign required to verify minimal native bank segments and landing UI.'}
    target=ROOT/'artifacts/data/worldbuilder/navigation/cleanup_audit.json'
    target.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
