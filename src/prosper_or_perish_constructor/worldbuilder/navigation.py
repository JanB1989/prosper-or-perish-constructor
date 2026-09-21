"""Consume World Builder navigation evidence and compile gameplay integration.

Buildings share an existing capacity family. Starting works exchange levels,
never add people to the geographic capacity budget.
"""
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path
import hashlib
import json
import re

import polars as pl
import yaml

from . import buildings


def inside(attrs, bounds):
    x, y = attrs.get('calibrated_lon'), attrs.get('calibrated_lat')
    return x is not None and y is not None and bounds[0] <= float(x) <= bounds[2] and bounds[1] <= float(y) <= bounds[3]


def prepare(repo, cfg, contract, *, write_blueprints=True):
    path=cfg.raw.get('navigation_config')
    if not path:return cfg
    settings=json.loads((repo/path).read_text())
    if not settings.get('enabled'):return cfg
    root=contract.root/'navigation'
    for rel,expected in contract.meta['files'].items():
        if rel.startswith('navigation/') and hashlib.sha256((contract.root/rel).read_bytes()).hexdigest()!=expected:
            raise ValueError('Navigation handover checksum mismatch: '+rel)
    manifest=json.loads((root/'manifest.json').read_text())
    if not all(manifest['checks'].values()):raise ValueError('Navigation geography checks failed')
    tiles={r['location']:r for r in pl.read_csv(root/'tiles.csv').iter_rows(named=True)}
    shores=list(pl.read_csv(root/'shores.csv').iter_rows(named=True))
    edges=list(pl.read_csv(root/'edges.csv').iter_rows(named=True))
    attrs={r['location_tag']:r for r in contract.location_attributes.join(contract.location_targets.select('location_tag','development'),on='location_tag',how='left').iter_rows(named=True)}
    eligibility={}
    for key,spec in settings['building_types'].items():
        family=spec.get('family',settings['family']);kind=next(k for k,v in cfg.building_map.items() if v==family)
        row=next(r for r in contract.building_types.iter_rows(named=True) if r['building']==kind)
        gate=json.loads(row['gate_json']);equation=json.loads(row['cap_equation_json'])
        scale=cfg.level_scale.get(family,1.0);limit=int(round(cfg.level_limit*scale))
        eligibility[key]={tag for tag,a in attrs.items() if buildings.gate_matches(gate,a) and buildings.cap_levels(equation,a,scale,limit)>0}
    def site_kind(tag,state):
        for regional in settings['regional_priority']:
            if tag in eligibility[regional] and inside(attrs[tag],settings['building_types'][regional]['bounds']):return regional
        return 'canal_lock_works' if state=='improvable' else 'river_navigation_works'
    by_water=defaultdict(list)
    for shore in shores:
        tag=shore['location_tag']
        if tag not in attrs:continue
        kind=site_kind(tag,shore['state'])
        if tag in eligibility[kind]:by_water[shore['water_location']].append(shore)
    sites={};water_owner={};no_site=[]
    for water,tile in sorted(tiles.items()):
        if tile['state']=='barrier':continue
        options=by_water[water]
        if not options:no_site.append(water);continue
        # Prefer a documented starting corridor, then substantial bank frontage.
        def rank(s):
            a=attrs[s['location_tag']]
            historic=any(inside(a,e['bounds']) for e in settings['starting_evidence'])
            return (historic,int(s['shore_pixels']),float(a.get('development') or 0),s['location_tag'])
        host=max(options,key=rank)['location_tag'];water_owner[water]=host
        if host not in sites:
            a=attrs[host];key=site_kind(host,tile['state']);family=settings['building_types'][key].get('family',settings['family'])
            evidence=next((e for e in settings['starting_evidence'] if e['building']==key and inside(a,e['bounds'])),None)
            sites[host]={'building':key,'family':family,'start_levels':settings['starting_levels_per_site'] if evidence else 0,
                         'evidence':evidence['id'] if evidence else 'future_investment','water_tiles':[]}
        sites[host]['water_tiles'].append(water)
    for site in sites.values():
        if site['building']=='river_navigation_works' and any(tiles[w]['state']=='improvable' for w in site['water_tiles']):
            site['building']='canal_lock_works'
    for edge in edges:
        edge['host']='' if edge['state']=='barrier' else (water_owner.get(edge['from']) or water_owner.get(edge['to']) or '')
    # Every regional kind is defined even if current map safety guards omit all
    # its candidate sites. An empty gate disables it instead of making it global.
    niche=dict(cfg.niche)
    for key in settings['building_types']:
        locations=sorted(tag for tag,s in sites.items() if s['building']==key)
        niche[key]={'family':settings['building_types'][key].get('family',settings['family']),'strength':1.0,'lock':[], 'gate':[{'location_tag':locations}],
                    'place_at_start':False,'maximum_levels':int(settings['maximum_levels_per_site'])}
    for site in sites.values():
        site['supporting_buildings']=[site['building']]+[key for key,spec in settings.get('existing_building_links',{}).items() if site['building'] in spec['site_buildings']]
    state={'settings':settings,'manifest':manifest,'tiles':tiles,'sites':sites,'edges':edges,'without_site':no_site, 'river_changes':list(pl.read_csv(root/'river_effect_changes.csv',schema_overrides={'original_levels':pl.String,'remaining_levels':pl.String}).iter_rows(named=True))}
    raw=dict(cfg.raw);raw['_navigation']=state
    cfg=replace(cfg,niche=niche,raw=raw)
    if write_blueprints:
        ensure_blueprints(repo,settings)
    return cfg


def ensure_blueprints(repo,settings):
    asset=yaml.safe_load((repo/'blueprints/accepted/buildings/jiangnan_canal_network.yml').read_text())['icon']
    for key,spec in settings['building_types'].items():
        icon=dict(asset);icon['source_png']='../assets/icons/'+key+'.png';icon['output_dds']=key+'.dds';icon.pop('prompt',None)
        pm='pp_'+key+'_maintenance';price='pp_'+key+'_price'
        upkeep='\n'.join(f'    {k} = {v}' for k,v in settings['upkeep'].items())
        body=f'''is_foreign = no
max_levels = pp_wb_cap_{key}
increase_per_level_cost = 0.75
pop_type = laborers
employment_size = 0
price = {price}
category = infrastructure_category
custom_tags = {{ pp_food_security_priority pp_water_control_priority }}
icon = {key}
rural_settlement = yes
town = yes
city = yes
megalopolis = yes
build_time = {settings['construction_days']}
construction_demand = town_building_construction
location_potential = {{ always = no }}
unique_production_methods = {{
  {pm} = {{
{upkeep}
    category = building_maintenance
  }}
}}
raw_modifier = {{ local_population_capacity = 0 }}
on_built = {{ custom_tooltip = pp_navigation_upgrade_tt hidden_effect = {{ location = {{ pp_navigation_refresh_site = yes }} }} }}
on_destroyed = {{ hidden_effect = {{ location = {{ pp_navigation_restore_site = yes }} }} }}
forbidden_for_estates = yes
ai_forbid_shutdown = yes
'''
        target=repo/'blueprints/accepted/buildings'/f'{key}.yml'
        # Preserve generated cap and gate on subsequent builds; the normal
        # improvement stage refreshes them from the current contract below.
        data={'version':2,'tag':key,'footprint':'capacity_source',
              'building':{'key':key,'mode':'CREATE','source':'pp_new_buildings.txt',
                          'production_method_slots':[{'name':'slot_0','methods':[pm]}],
                          'possible_production_methods':[],'body':body},
              'localization':{'entries':{key:spec['name'],key+'_desc':spec['description']+' Shares the local allowance for '+spec.get('family',settings['family']).replace('_',' ')+'. At a full allowance, replace an existing level to make room.',
                                        key+'_slot_0':'Maintenance',pm:'Channel and Sluice Keepers',price:spec['name']+' Cost'}},
              'prices':[{'key':price,'body':'{ gold = '+str(spec['gold'])+' }'}], 'icon':icon}
        buildings._save_blueprint(target,data)
    for key,spec in settings.get('existing_building_links',{}).items():
        path=repo/'blueprints/accepted/buildings'/f'{key}.yml'
        data=yaml.safe_load(path.read_text());body=data['building']['body']
        if 'pp_navigation_refresh_site' not in body:
            body+='\non_built = { hidden_effect = { location = { pp_navigation_refresh_site = yes } } }\non_destroyed = { hidden_effect = { location = { pp_navigation_restore_site = yes } } }\n'
        data['building']['body']=body
        for price in data['prices']:price['body']='{ gold = '+str(spec['gold'])+' }'
        buildings._save_blueprint(path,data)
    path=repo/'blueprints/buildings.manifest.yml';manifest=yaml.safe_load(path.read_text())
    for key in settings['building_types']:manifest['enabled']['buildings/'+key+'.yml']=True
    path.write_text(yaml.safe_dump(manifest,sort_keys=False),encoding='utf-8')


def exchange_levels(levels,site):
    """Move an existing general-family level to works with equal unit capacity."""
    if not site or not site['start_levels']:return 0
    family=site['family'];key=site['building']
    if family not in levels:return 0
    current,cap=levels[family];count=min(current,int(site['start_levels']))
    if count:
        levels[family]=(current-count,cap)
        levels[key]=(count,min(cap,count))
    return count


def write_runtime(repo,cfg,contract,mod_root,vanilla_root):
    state=cfg.raw.get('_navigation')
    if not state:return {'enabled':False}
    def write(rel,text):
        p=mod_root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('\ufeff'+text,encoding='utf-8',newline='\n')
    costs=state['manifest']['config']['road_costs'];road_names={s:'pp_navigation_'+s for s in costs}
    roads=[]
    for i,(name,cost) in enumerate(costs.items(),20):
        roads.append(f'''{road_names[name]} = {{
 level = {i}
 enabled = {{ always = no }}
 movement_cost = {cost['movement_cost']}
 market_access = {cost['market_access']}
 pop_movement = 0
 proximity = 0
 build_time_per_unit_distance = 30
 price_per_unit_distance = build_gravel_road
 construction_demand = build_gravel_road_demand
 maintenance_demand = maintain_gravel_road_demand
 color = map_paved_road
 spline_style_id = 1
}}''')
    write('in_game/common/road_types/pp_navigation.txt','\n'.join(roads)+'\n')
    def edge_line(e,improved=False):
        kind='improved' if improved else e['state']
        return f" location:{e['from']} = {{ add_road_to = {{ target = location:{e['to']} type = {road_names[kind]} }} }}"
    seed=['pp_navigation_seed = {']+[edge_line(e) for e in state['edges']]+['}']
    refresh=['pp_navigation_refresh_site = {'];restore=['pp_navigation_restore_site = {'];start=[]
    by_host=defaultdict(list)
    for e in state['edges']:
        if e['host']:by_host[e['host']].append(e)
    for tag,site in sorted(state['sites'].items()):
        key=site['building'];edges=by_host[tag]
        present='OR = { '+' '.join('has_building = building_type:'+k for k in site['supporting_buildings'])+' }'
        if not edges:continue
        refreshed=[' if = {',f'  limit = {{ this = location:{tag} }}']+[edge_line(e,True) for e in edges]+[' }']
        refresh.extend(refreshed)
        restore.extend([' if = {',f'  limit = {{ this = location:{tag} NOT = {{ {present} }} }}']+[edge_line(e) for e in edges]+[' }'])
        start.append(f' location:{tag} = {{ if = {{ limit = {{ {present} }} '+ ' '.join(edge_line(e,True) for e in edges)+' } }')
    refresh.append('}');restore.append('}')
    write('in_game/common/scripted_effects/pp_navigation_routes.txt','\n'.join(seed+refresh+restore)+'\n')
    lost=list(pl.read_csv(contract.root/'navigation/lost_river_effects.csv').iter_rows(named=True))
    bonus=['pp_navigation_preserve_rivers = {']
    for row in lost:
        tag=row['location_tag'];level=int(row['river_level']);key=f'river_flowing_through_{level}'
        bonus.append(f' location:{tag} = {{ if = {{ limit = {{ NOT = {{ has_location_modifier = {key} }} }} add_location_modifier = {{ modifier = {key} days = -1 mode = replace }} }} }}')
        if row['original_coastal']:
            key=f'river_flowing_through_coast_{level}'
            bonus.append(f' location:{tag} = {{ if = {{ limit = {{ NOT = {{ has_location_modifier = {key} }} }} add_location_modifier = {{ modifier = {key} days = -1 mode = replace }} }} }}')
    bonus.append('}')
    write('in_game/common/scripted_effects/pp_navigation_river_bonuses.txt','\n'.join(bonus)+'\n')
    write('in_game/common/on_action/pp_navigation.txt','\n'.join([
        'on_game_start = { on_actions = { pp_navigation_start } }','pp_navigation_start = { effect = {',
        ' pp_navigation_preserve_rivers = yes',' pp_navigation_seed = yes',*start,'} }'])+'\n')
    unlocks=state['settings'].get('advance_unlocks',{})
    write('in_game/common/advances/pp_navigation.txt','\n'.join(f'TRY_INJECT:{advance} = {{ unlock_building = {key} }}' for key,advance in unlocks.items())+'\n')
    loc=['l_english:', ' pp_navigation_navigable: "Navigable Waterway"',' pp_navigation_improvable: "Unimproved Waterway"',
         ' pp_navigation_barrier: "River Barrier"',' pp_navigation_improved: "Maintained Navigation"',
         ' pp_navigation_upgrade_tt: "Improves movement and market access along the waterways maintained from this location."']
    write('main_menu/localization/english/pp_navigation_roads_l_english.yml','\n'.join(loc)+'\n')
    triggers=[]
    for n in range(1,6):
        triggers.append(f'pp_navigation_river_level_{n} = {{ OR = {{ has_location_modifier = pp_nav_original_level_{n} AND = {{ NOT = {{ has_location_modifier = pp_nav_geography_changed }} has_location_modifier = river_flowing_through_{n} }} }} }}')
    triggers.append('pp_navigation_has_river = { OR = { '+' '.join(f'pp_navigation_river_level_{n} = yes' for n in range(1,6))+' } }')
    write('in_game/common/scripted_triggers/pp_navigation_rivers.txt','\n'.join(triggers)+'\n')
    initial=defaultdict(set)
    for key,tag in re.findall(r'(\w+) = \{ tag = \w+ level = [1-9]\d* location = (\w+) \}',(mod_root/buildings.SETUP_PATH).read_text(encoding='utf-8-sig')):
        initial[tag].add(key)
    active_sites={tag:sorted(initial[tag]&set(site['supporting_buildings'])) for tag,site in state['sites'].items() if initial[tag]&set(site['supporting_buildings'])}
    report={'enabled':True,'tiles':len(state['tiles']),'edges':len(state['edges']),'building_sites':len(state['sites']),
            'site_types':dict(Counter(s['building'] for s in state['sites'].values())),
            'initially_improved_sites':active_sites,'historical_candidate_sites':sum(s['start_levels']>0 for s in state['sites'].values()),
            'water_tiles_without_capacity_site':state['without_site'],'river_effects_restored':len(lost),
            'engine_limits':['Roads are undirected; water-to-land script direction is not one-way movement.',
                             'Fleet class cannot be restricted on sea tiles.',
                             'Destruction downgrade needs in-game verification of add_road_to replacing a higher road level.']}
    output=repo/'artifacts/data/worldbuilder/navigation';output.mkdir(parents=True,exist_ok=True)
    (output/'sites.json').write_text(json.dumps(state['sites'],indent=2)+'\n')
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def river_bonus_plan(changes):
    """Keep the original river levels and mouth bonuses through raster edits."""
    result={}
    for row in changes:
        original={int(n) for n in str(row['original_levels'] or '').split(',') if n}
        remaining={int(n) for n in str(row['remaining_levels'] or '').split(',') if n}
        keys=['pp_nav_geography_changed']+[f'pp_nav_original_level_{n}' for n in sorted(original)]
        keys += [f'river_flowing_through_{n}' for n in sorted(original-remaining)]
        keys += [f'pp_nav_cancel_river_{n}' for n in sorted(remaining-original)]
        before=original if row['original_coastal'] else set()
        after=remaining if row['new_coastal'] else set()
        keys += [f'river_flowing_through_coast_{n}' for n in sorted(before-after)]
        keys += [f'pp_nav_cancel_mouth_{n}' for n in sorted(after-before)]
        result[row['location_tag']]=keys
    return result


def write_bonus_compensation(state,mod_root,vanilla_root):
    from . import modifiers
    # Read generated effective river blocks. Negate only top-level numeric
    # modifiers; metadata is not an effect and must not enter the cancellation.
    river_text=(mod_root/modifiers.RIVER_MODIFIERS_PATH).read_text(encoding='utf-8-sig')
    coast=modifiers.static_modifier_bodies(vanilla_root,r'river_flowing_through_coast_\d+')
    blocks=[]
    markers=['pp_nav_geography_changed']+[f'pp_nav_original_level_{n}' for n in range(1,6)]
    for key in markers:blocks.append(key+' = { game_data = { category = location } }')
    for n in range(1,6):
        match=re.search(r'TRY_REPLACE:river_flowing_through_'+str(n)+r'\s*=\s*\{',river_text)
        if not match:raise ValueError('Missing effective river modifier '+str(n))
        pos=match.end();depth=1;end=pos
        while depth:
            depth+=(river_text[end]=='{')-(river_text[end]=='}');end+=1
        for kind,body in [('river',river_text[pos:end-1]),('mouth','\n'.join(coast[f'river_flowing_through_coast_{n}']))]:
            numeric=[];depth=0
            for line in body.splitlines():
                value=re.fullmatch(r'\s*(\w+)\s*=\s*([-+]?\d+(?:\.\d+)?)\s*',line)
                if depth==0 and value:numeric.append(f' {value[1]} = {-float(value[2]):g}')
                depth+=line.count('{')-line.count('}')
            blocks.append(f'pp_nav_cancel_{kind}_{n} = {{\n game_data = {{ category = location }}\n'+'\n'.join(numeric)+'\n}')
    path=mod_root/'main_menu/common/static_modifiers/pp_navigation_preservation.txt'
    path.write_text('\ufeff'+'\n\n'.join(blocks)+'\n',encoding='utf-8')
    loc=['l_english:']
    for key in markers:
        loc.append(f' STATIC_MODIFIER_NAME_{key}: "River Geography"')
        loc.append(f' STATIC_MODIFIER_DESC_{key}: "The river continues to shape cultivation and settlement along its banks."')
    for kind in ['river','mouth']:
        for n in range(1,6):
            loc.append(f' STATIC_MODIFIER_NAME_pp_nav_cancel_{kind}_{n}: "Original Riverbank"')
            loc.append(f' STATIC_MODIFIER_DESC_pp_nav_cancel_{kind}_{n}: "Navigation works preserve the established riverbank benefits without adding river-mouth advantages inland."')
    (mod_root/'main_menu/localization/english/pp_navigation_preservation_l_english.yml').write_text('\ufeff'+'\n'.join(loc)+'\n',encoding='utf-8')
    return river_bonus_plan(state['river_changes'])
