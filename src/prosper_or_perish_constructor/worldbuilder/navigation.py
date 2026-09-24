"""Consume World Builder navigation evidence and compile gameplay integration.

Buildings share an existing capacity family. Starting works exchange levels,
never add people to the geographic capacity budget.
"""
from collections import Counter, defaultdict
from dataclasses import replace
import csv
import hashlib
import json

import polars as pl
import yaml

from . import buildings, spline_network
from prosper_or_perish_constructor import yaml_io


def inside(attrs, bounds):
    x, y = attrs.get('calibrated_lon'), attrs.get('calibrated_lat')
    return x is not None and y is not None and bounds[0] <= float(x) <= bounds[2] and bounds[1] <= float(y) <= bounds[3]


def regional_match(attributes, spec):
    """A regional envelope must satisfy both its geometry and named regions."""
    return inside(attributes, spec['bounds']) and (
        not spec.get('regions') or attributes.get('region') in spec['regions']
    )


def historical_evidence(settings, attributes, building):
    return next((entry for entry in settings['starting_evidence']
                 if entry['building'] == building and inside(attributes, entry['bounds'])), None)


def validate_routes(tiles, edges, sites):
    """Reject ambiguous undirected connections and unsafe construction hosts."""
    seen = set()
    for edge in edges:
        source, target = edge['from'], edge['to']
        pair = tuple(sorted((source, target)))
        if source == target or pair in seen:
            raise ValueError(f'Duplicate or self-connected navigation route: {pair}')
        seen.add(pair)
        if source not in tiles:
            raise ValueError(f'Unknown navigation source: {source}')
        blocked = any(tiles.get(tag, {}).get('state') == 'barrier' for tag in pair)
        if blocked and (edge['state'] != 'barrier' or edge.get('host')):
            raise ValueError(f'Navigation works would open a barrier: {pair}')
        host = edge.get('host')
        if host and (host not in sites or not set(pair).intersection(sites[host]['water_tiles'])):
            raise ValueError(f'Navigation host has no assigned endpoint: {pair}, {host}')


def prepare(repo, cfg, contract, *, write_blueprints=True, locations=None):
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
    if locations is not None:
        regions = dict(locations.select('location_tag', 'region').iter_rows())
        for tag, attributes in attrs.items():
            attributes['region'] = regions.get(tag)
    elif any(spec.get('regions') for spec in settings['building_types'].values()):
        raise ValueError('Navigation regional rules require the location region table')
    eligibility={}
    for key,spec in settings['building_types'].items():
        family=spec.get('family',settings['family']);kind=next(k for k,v in cfg.building_map.items() if v==family)
        row=next(r for r in contract.building_types.iter_rows(named=True) if r['building']==kind)
        gate=json.loads(row['gate_json']);equation=json.loads(row['cap_equation_json'])
        scale=cfg.level_scale.get(family,1.0);limit=int(round(cfg.level_limit*scale))
        eligibility[key]={tag for tag,a in attrs.items() if buildings.gate_matches(gate,a) and buildings.cap_levels(equation,a,scale,limit)>0}
    def site_kind(tag,state):
        for regional in settings['regional_priority']:
            if tag in eligibility[regional] and regional_match(attrs[tag],settings['building_types'][regional]):return regional
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
            historic=historical_evidence(settings,a,site_kind(s['location_tag'],tile['state'])) is not None
            return (historic,int(s['shore_pixels']),float(a.get('development') or 0),s['location_tag'])
        host=max(options,key=rank)['location_tag'];water_owner[water]=host
        if host not in sites:
            a=attrs[host];key=site_kind(host,tile['state']);family=settings['building_types'][key].get('family',settings['family'])
            evidence=historical_evidence(settings,a,key)
            sites[host]={'building':key,'family':family,'start_levels':settings['starting_levels_per_site'] if evidence else 0,
                         'evidence':evidence['id'] if evidence else 'future_investment','water_tiles':[],
                         'region':a.get('region','')}
        sites[host]['water_tiles'].append(water)
    for site in sites.values():
        if site['building']=='river_navigation_works' and any(tiles[w]['state']=='improvable' for w in site['water_tiles']):
            site['building']='canal_lock_works'
    for edge in edges:
        edge['host']='' if edge['state']=='barrier' else (water_owner.get(edge['from']) or water_owner.get(edge['to']) or '')
    validate_routes(tiles,edges,sites)
    # Every regional kind is defined even if current map safety guards omit all
    # its candidate sites. An empty gate disables it instead of making it global.
    niche=dict(cfg.niche)
    for key in settings['building_types']:
        locations=sorted(tag for tag,s in sites.items() if s['building']==key)
        # The tag list stays the offline gate; the game tests the site marker placed on the same locations.
        niche[key]={'family':settings['building_types'][key].get('family',settings['family']),'strength':1.0,'lock':[], 'gate':[{'location_tag':locations}],'marker':site_marker(key),
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
    asset=yaml_io.safe_load((repo/'blueprints/accepted/buildings/jiangnan_canal_network.yml').read_text())['icon']
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
        data=yaml_io.safe_load(path.read_text());body=data['building']['body']
        if 'pp_navigation_refresh_site' not in body:
            body+='\non_built = { hidden_effect = { location = { pp_navigation_refresh_site = yes } } }\non_destroyed = { hidden_effect = { location = { pp_navigation_restore_site = yes } } }\n'
        data['building']['body']=body
        for price in data['prices']:price['body']='{ gold = '+str(spec['gold'])+' }'
        buildings._save_blueprint(path,data)
    path=repo/'blueprints/buildings.manifest.yml';manifest=yaml_io.safe_load(path.read_text())
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


# Navigation roads draw with their own spline style: no road texture on the water and, because the
# vanilla road vehicles only use the four vanilla styles, no trade wagons on the rivers.
SPLINE_STYLE_ID = 4
SPLINE_STYLE = f"""pp_navigation = {{
 id = {SPLINE_STYLE_ID}
 spline = {{
  uv_scale = 0.5
  width = 0.01
  uv_rounding = yes
  smooth_fade_distance = 10
  smooth_iterations = 0
  smooth_kernel_size = 1
  tesselation_max_angle = 5.0
  tesselation_min_distance = 0.05
  tesselation_max_distance = 0.25
  opacity_fade_distance = 0.625
 }}
 effect = {{
  effectname = "SingleTexturePass"
  shaderfile = "gfx/FX/road_gravel.shader"
  texture_set = {{
   name = ""
   texture = {{ file = "gfx/map/spline_network/road_dirt_diffuse.dds" }}
   texture = {{ file = "gfx/map/spline_network/road_dirt_normal.dds" srgb = no }}
   texture = {{ file = "gfx/map/spline_network/road_dirt_properties.dds" }}
   texture = {{ file = "gfx/map/spline_network/road_flatmap.dds" }}
  }}
 }}
 connections = none
 heightmap = none
}}
"""


def road_costs(state):
    """Handover road costs with the constructor's balance overrides (`road_costs` in the navigation config) on top.
    The World Builder owns which cost profile a route has; the constructor owns what each profile costs in game."""
    costs={k:dict(v) for k,v in state['manifest']['config']['road_costs'].items()}
    for name,override in state['settings'].get('road_costs',{}).items():
        if name not in costs:raise ValueError(f'Unknown navigation road cost profile: {name}')
        costs[name].update(override)
    return costs


def write_runtime(repo,cfg,contract,mod_root,vanilla_root):
    state=cfg.raw.get('_navigation')
    if not state:return {'enabled':False}
    def write(rel,text):
        p=mod_root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('\ufeff'+text,encoding='utf-8',newline='\n')
    costs=road_costs(state);road_names={s:'pp_navigation_'+s for s in costs}
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
 spline_style_id = {SPLINE_STYLE_ID}
}}''')
    write('in_game/common/road_types/pp_navigation.txt','\n'.join(roads)+'\n')
    write('in_game/gfx/map/spline_network/spline_styles/pp_navigation.txt',SPLINE_STYLE)
    spline_report=spline_network.write(mod_root,vanilla_root,[(e['from'],e['to']) for e in state['edges']])
    def edge_line(e,improved=False):
        kind='improved' if improved else e.get('cost_profile',e['state'])
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
        affected=sorted({w for e in edges for w in (e['from'],e['to']) if w in state['tiles'] and state['tiles'][w]['state']!='barrier'})
        updates=[f' location:{w} = {{ pp_navigation_map_refresh_{w} = yes }}' for w in affected]
        refreshed[-1:-1]=updates
        refresh.extend(refreshed)
        reset=updates
        restore.extend([' if = {',f'  limit = {{ this = location:{tag} NOT = {{ {present} }} }}']+[edge_line(e) for e in edges]+reset+[' }'])
        start.append(f' location:{tag} = {{ if = {{ limit = {{ {present} }} '+ ' '.join([*(edge_line(e,True) for e in edges),*updates])+' } }')
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
    # The engine traces its river sizes from rivers.png and drops some bank remnants the navigation export keeps
    # (Hanyang, Mechelen: no river size at all), while the World Builder still gives them a river level. Such a
    # location gets its level back; one the engine sized differently keeps the engine's (no double bonus).
    lost_tags={row['location_tag'] for row in lost}
    for row in contract.location_attributes.select('location_tag','river_level').iter_rows(named=True):
        level=int(row['river_level'] or 0)
        if level and row['location_tag'] not in lost_tags:
            bonus.append(f" location:{row['location_tag']} = {{ if = {{ limit = {{ NOT = {{ pp_navigation_has_river = yes }} }} add_location_modifier = {{ modifier = river_flowing_through_{level} days = -1 mode = replace }} }} }}")
    bonus.append('}')
    write('in_game/common/scripted_effects/pp_navigation_river_bonuses.txt','\n'.join(bonus)+'\n')
    # Starting building levels that need the river are added after the rivers are restored (start_simulation).
    write('in_game/common/on_action/pp_navigation.txt','\n'.join([
        'on_game_start = { on_actions = { pp_navigation_start } }','pp_navigation_start = { effect = {',
        ' pp_navigation_preserve_rivers = yes',' pp_start_river_topup = yes',' pp_navigation_map_seed = yes',' pp_navigation_seed = yes',*start,' pp_navigation_map_refresh = yes','} }'])+'\n')
    unlocks=state['settings'].get('advance_unlocks',{})
    write('in_game/common/advances/pp_navigation.txt','\n'.join(f'TRY_INJECT:{advance} = {{ unlock_building = {key} }}' for key,advance in unlocks.items())+'\n')
    loc=['l_english:', ' pp_navigation_navigable: "Navigable Waterway"',' pp_navigation_improvable: "Unimproved Waterway"',
         ' pp_navigation_barrier: "River Barrier"',' pp_navigation_improved: "Maintained Navigation"',
         ' pp_navigation_difficult: "Difficult Waterway"',
         ' pp_navigation_navigable_desc: "A river reach that boats can use. Movement and trade along it are easier."',
         ' pp_navigation_difficult_desc: "A river reach with shoals, rapids or strong seasonal floods. Boats can use it, but slowly and at a cost."',
         ' pp_navigation_improvable_desc: "A river reach that is passable but costly until navigation works on its banks are completed."',
         ' pp_navigation_barrier_desc: "Falls or rapids that boats cannot pass."',
         ' pp_navigation_improved_desc: "A river reach kept open by the navigation works on its banks."',
         ' pp_navigation_upgrade_tt: "Improves movement and market access along the waterways maintained from this location."']
    write('main_menu/localization/english/pp_navigation_roads_l_english.yml','\n'.join(loc)+'\n')
    triggers=[]
    for n in range(1,6):
        triggers.append(f'pp_navigation_river_level_{n} = {{ has_location_modifier = river_flowing_through_{n} }}')
    triggers.append('pp_navigation_has_river = { OR = { '+' '.join(f'pp_navigation_river_level_{n} = yes' for n in range(1,6))+' } }')
    write('in_game/common/scripted_triggers/pp_navigation_rivers.txt','\n'.join(triggers)+'\n')
    from .navigation_map_modes import write_map_modes
    write_map_modes(mod_root,state)
    from eu5gameparser.clausewitz.parser import parse_file
    initial=defaultdict(dict)
    setup=parse_file(mod_root/buildings.SETUP_PATH)
    for manager in setup.entries:
        if manager.key != 'building_manager':continue
        for entry in manager.value.entries:
            values={field.key:field.value for field in entry.value.entries}
            if int(values.get('level',0))>0:
                initial[values['location']][entry.key]=int(values['level'])
    active_sites={tag:sorted(set(initial[tag])&set(site['supporting_buildings'])) for tag,site in state['sites'].items() if set(initial[tag])&set(site['supporting_buildings'])}
    report={'enabled':True,'tiles':len(state['tiles']),'edges':len(state['edges']),'building_sites':len(state['sites']),
            'site_types':dict(Counter(s['building'] for s in state['sites'].values())),
            'initially_improved_sites':active_sites,'historical_candidate_sites':sum(s['start_levels']>0 for s in state['sites'].values()),
            'water_tiles_without_capacity_site':state['without_site'],'river_effects_restored':len(lost), 'native_bank_pixels_preserved':state['manifest'].get('preserved_river_pixels',0), 'ocean_connected_passable_tiles':state['manifest']['ocean_connected_passable_tiles'], 'river_ports_changed':state['manifest']['ports_changed'], 'spline_network':spline_report,
            'engine_limits':['Roads are undirected; water-to-land script direction is not one-way movement.',
                             'Fleet class cannot be restricted on sea tiles.',
                             'Destruction downgrade needs in-game verification of add_road_to replacing a higher road level.']}
    output=repo/'artifacts/data/worldbuilder/navigation';output.mkdir(parents=True,exist_ok=True)
    with (output/'building_inventory.csv').open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fieldnames=['location','region','building','building_key','starting_levels','existing_supporting_buildings','navigation_active_at_start','assigned_water_tiles','capacity_family'])
        writer.writeheader()
        for tag,site in sorted(state['sites'].items()):
            key=site['building']
            writer.writerow({'location':tag,'region':site.get('region',''),'building':state['settings']['building_types'][key]['name'],
                             'building_key':key,'starting_levels':initial[tag].get(key,0),
                             'existing_supporting_buildings':';'.join(k for k in site['supporting_buildings'] if k!=key and k in initial[tag]),
                             'navigation_active_at_start':bool(active_sites.get(tag)), 'assigned_water_tiles':len(site['water_tiles']), 'capacity_family':site['family']})
    (output/'sites.json').write_text(json.dumps(state['sites'],indent=2)+'\n')
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def site_marker(key):
    return f'pp_navigation_site_{key}'


def site_markers(state):
    """Location -> its site marker. The works' gates test the setup-placed marker in one lookup; a list of
    every site tag costs one comparison per tag on each location_potential check (the profiler's largest mod row)."""
    return {tag:[site_marker(site['building'])] for tag,site in (state or {}).get('sites',{}).items()}


def write_bonus_compensation(state,mod_root,vanilla_root):
    """Native bank pixels own river effects; never add scripted duplicates. Also defines the site markers."""
    if state['manifest'].get('river_preservation')!='native_bank_pixel':
        raise ValueError('Rebuild World Builder navigation: native river preservation contract required')
    types=state.get('settings',{}).get('building_types',{})
    blocks=['# River effects are preserved by the native river bitmap.','# Site markers: placed in the setup on each navigation site, tested by the works gates.']
    blocks+=[f'{site_marker(k)} = {{\n\tgame_data = {{ category = location }}\n}}' for k in sorted(types)]
    (mod_root/'main_menu/common/static_modifiers/pp_navigation_preservation.txt').write_text('\n\n'.join(blocks)+'\n')
    loc=['\ufeffl_english:']
    for k,spec in sorted(types.items()):
        loc.append(f'  STATIC_MODIFIER_NAME_{site_marker(k)}: "{spec["name"]} Site"')
        loc.append(f'  STATIC_MODIFIER_DESC_{site_marker(k)}: "The waterway here can be improved with {spec["name"]}."')
    (mod_root/'main_menu/localization/english/pp_navigation_preservation_l_english.yml').write_text('\n'.join(loc)+'\n',encoding='utf-8')
    return {}
