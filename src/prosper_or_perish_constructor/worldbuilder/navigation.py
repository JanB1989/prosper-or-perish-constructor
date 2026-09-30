"""Consume World Builder navigation evidence and compile gameplay integration.

Channel tiles take a topography by their state (Navigable River, Shallows, Falls). One building, the River Navigation
Canal, opens the Shallows tiles next to its location: a Shallows tile is open while any bank next to it has the canal,
and its water roads switch between their own cost profile and ``improved``. The state is recomputed from the canals
that exist whenever one is built or destroyed, never toggled, so building and demolishing in any order stays
consistent (on_destroyed runs while the building still counts: the recompute skips the location being destroyed).
The canal holds no population capacity.
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


def historical_evidence(settings, attributes):
    return next((entry for entry in settings.get('starting_evidence', []) if inside(attributes, entry['bounds'])), None)


def canal_key(settings):
    return settings['canal']['key']


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
    key=canal_key(settings)
    shallows=sorted(t for t,tile in tiles.items() if tile['state']=='improvable')
    banks=defaultdict(list)   # Shallows tile -> the ownable land locations on its banks
    for shore in shores:
        if shore['water_location'] in tiles and tiles[shore['water_location']]['state']=='improvable' and shore['location_tag'] in attrs:
            banks[shore['water_location']].append(shore)
    # Documented starting navigations: the best bank of each Shallows tile in an evidence envelope starts with a canal.
    sites={};water_owner={}
    for water in shallows:
        options=[s for s in banks[water] if historical_evidence(settings,attrs[s['location_tag']])]
        if not options:continue
        best=max(options,key=lambda s:(int(s['shore_pixels']),float(attrs[s['location_tag']].get('development') or 0),s['location_tag']))
        host=best['location_tag'];water_owner[water]=host
        site=sites.setdefault(host,{'building':key,'start_levels':1,'evidence':historical_evidence(settings,attrs[host])['id'],
                                    'water_tiles':[],'supporting_buildings':[key],'region':attrs[host].get('region','')})
        site['water_tiles'].append(water)
    for edge in edges:
        edge['host']='' if edge['state']=='barrier' else (water_owner.get(edge['from']) or water_owner.get(edge['to']) or '')
    validate_routes(tiles,edges,sites)
    state={'settings':settings,'manifest':manifest,'tiles':tiles,'sites':sites,'edges':edges,'without_site':[],
           'shallows':shallows,'banks':{w:sorted(s['location_tag'] for s in banks[w]) for w in shallows},'canal':key,
           'river_changes':list(pl.read_csv(root/'river_effect_changes.csv',schema_overrides={'original_levels':pl.String,'remaining_levels':pl.String}).iter_rows(named=True))}
    raw=dict(cfg.raw);raw['_navigation']=state
    cfg=replace(cfg,raw=raw)
    if write_blueprints:
        ensure_blueprints(repo,settings)
    return cfg


def canal_body(settings):
    spec=settings['canal'];key=spec['key']
    upkeep='\n'.join(f'    {k} = {v}' for k,v in spec['upkeep'].items())
    shallows=settings['topographies']['improvable']['key']
    return f'''is_foreign = no
max_levels = 1
pop_type = laborers
employment_size = 0
price = pp_{key}_price
category = infrastructure_category
icon = {key}
rural_settlement = yes
town = yes
city = yes
megalopolis = yes
build_time = {spec['construction_days']}
construction_demand = town_building_construction
location_potential = {{
  is_coastal = yes
  OR = {{
    has_building = building_type:{key}
    any_neighbor_location = {{ topography = {shallows} NOT = {{ has_location_modifier = {CANAL_OPEN} }} }}
  }}
}}
unique_production_methods = {{
  pp_{key}_maintenance = {{
{upkeep}
    category = building_maintenance
  }}
}}
on_built = {{ custom_tooltip = pp_river_canal_built_tt hidden_effect = {{ location = {{ pp_river_canal_built = yes }} }} }}
on_destroyed = {{ custom_tooltip = pp_river_canal_destroyed_tt hidden_effect = {{ location = {{ pp_river_canal_destroyed = yes }} }} }}
forbidden_for_estates = yes
ai_forbid_shutdown = yes
raw_modifier = {{
  free_building_levels = 1
}}
'''


def ensure_blueprints(repo,settings):
    spec=settings['canal'];key=spec['key']
    asset=yaml_io.safe_load((repo/'blueprints/accepted/buildings/jiangnan_canal_network.yml').read_text())['icon']
    icon=dict(asset);icon['source_png']='../assets/icons/'+key+'.png';icon['output_dds']=key+'.dds';icon.pop('prompt',None);icon.pop('drawing',None)
    if (repo/'assets/icon_drawings'/key/'draw.py').exists():  # procedural icon (eu5-building icon install)
        icon['drawing']='../../../assets/icon_drawings/'+key+'/draw.py'
    pm='pp_'+key+'_maintenance';price='pp_'+key+'_price'
    data={'version':2,'tag':key,'footprint':'infrastructure',
          'building':{'key':key,'mode':'CREATE','source':'pp_new_buildings.txt',
                      'production_method_slots':[{'name':'slot_0','methods':[pm]}],
                      'possible_production_methods':[],'body':canal_body(settings)},
          'localization':{'entries':{key:spec['name'],key+'_desc':spec['description'],
                                    key+'_slot_0':'Maintenance',pm:'Lock and Towpath Keepers',price:spec['name']+' Cost'}},
          'prices':[{'key':price,'body':'{ gold = '+str(spec['gold'])+' }'}], 'icon':icon,
          'evaluation':{'allow_rules':{'profit_percent':'Infrastructure upkeep without output: the canal pays for itself through the opened water roads, not through production.'}}}
    buildings._save_blueprint(repo/'blueprints/accepted/buildings'/f'{key}.yml',data)
    # the works of the earlier site system are gone; linked buildings no longer touch the water roads
    for old in settings.get('retired_buildings',[]):
        path=repo/'blueprints/accepted/buildings'/f'{old}.yml'
        if path.exists():path.unlink()
    for linked in settings.get('unlinked_buildings',[]):
        path=repo/'blueprints/accepted/buildings'/f'{linked}.yml'
        data=yaml_io.safe_load(path.read_text());body=data['building']['body']
        body='\n'.join(line for line in body.splitlines() if 'pp_navigation_refresh_site' not in line and 'pp_navigation_restore_site' not in line)+'\n'
        data['building']['body']=body
        buildings._save_blueprint(path,data)
    path=repo/'blueprints/buildings.manifest.yml';manifest=yaml_io.safe_load(path.read_text())
    for old in settings.get('retired_buildings',[]):manifest['enabled'].pop('buildings/'+old+'.yml',None)
    manifest['enabled']['buildings/'+key+'.yml']=True
    path.write_text(yaml.safe_dump(manifest,sort_keys=False),encoding='utf-8')


CANAL_OPEN='pp_river_canal_open'


def refreshable_tiles(state):
    """Tiles that have a map-state refresh effect (navigation_map_modes: passable tiles with a passable connection)."""
    out=set()
    for e in state['edges']:
        if e['state']=='barrier':continue
        for tag in (e['from'],e['to']):
            if tag in state['tiles'] and state['tiles'][tag]['state']!='barrier':out.add(tag)
    return out


def canal_effects(state,edge_line,road_names):
    """The canal's scripted effects and the game-start lines.

    ``pp_river_canal_tile_<tile>`` (tile scope) recomputes one Shallows tile: open while any bank next to it has the
    canal, except ``scope:pp_canal_closing`` (the location whose canal is being destroyed); then every water road of
    the tile is 'improved' when all Shallows tiles at its ends are open, else its own cost profile."""
    key=state['canal'];shallows=set(state['shallows']);topo=state['settings']['topographies']['improvable']['key']
    refresh=refreshable_tiles(state)
    by_tile=defaultdict(list)
    for e in state['edges']:
        if e['state']=='barrier':continue
        for tag in {e['from'],e['to']}&shallows:by_tile[tag].append(e)
    lines=[]
    dispatch=['pp_river_canal_refresh_tile = {']
    for n,tile in enumerate(sorted(shallows)):
        lines+=[f'pp_river_canal_tile_{tile} = {{',
                f' if = {{ limit = {{ any_neighbor_location = {{ has_building = building_type:{key} NOT = {{ this = scope:pp_canal_closing }} }} }} add_location_modifier = {{ modifier = {CANAL_OPEN} months = -1 mode = replace }} }}',
                f' else = {{ remove_location_modifier = {CANAL_OPEN} }}']
        touched=set()
        for e in by_tile[tile]:
            ends=[t for t in (e['from'],e['to']) if t in shallows]
            cond=' '.join(f'location:{t} = {{ has_location_modifier = {CANAL_OPEN} }}' for t in ends)
            lines.append(f' if = {{ limit = {{ {cond} }}{edge_line(e,True)} }} else = {{{edge_line(e)} }}')
            touched.update(t for t in (e['from'],e['to']) if t in refresh)
        lines+=[f' location:{t} = {{ pp_navigation_map_refresh_{t} = yes }}' for t in sorted(touched)]
        lines.append('}')
        dispatch.append(f' {"if" if n==0 else "else_if"} = {{ limit = {{ this = location:{tile} }} pp_river_canal_tile_{tile} = yes }}')
    dispatch.append('}')
    lines+=dispatch
    # built: the recompute runs for every Shallows tile next to the new canal (the closing scope is the tile itself, so
    # no bank is skipped); destroyed: the location being destroyed is skipped, its canal still counts at on_destroyed
    lines+=['pp_river_canal_built = {',f' every_neighbor_location = {{ limit = {{ topography = {topo} }} save_scope_as = pp_canal_closing pp_river_canal_refresh_tile = yes }}','}',
            'pp_river_canal_destroyed = {',' save_scope_as = pp_canal_closing',f' every_neighbor_location = {{ limit = {{ topography = {topo} }} pp_river_canal_refresh_tile = yes }}','}']
    start=[f' location:{tag} = {{ if = {{ limit = {{ has_building = building_type:{key} }} pp_river_canal_built = yes }} }}' for tag in sorted(state['sites'])]
    return lines,start


def write_topographies(mod_root,vanilla_root,contract,settings,repo=None):
    """Channel tiles take the topography of their state; the three water topographies with their own icons (drawn by
    assets/icons/topography/draw.py), their own Topography map mode colours, proximity modifier types (the engine
    requires <topography>_proximity_impact) and names."""
    import re
    from pathlib import Path

    from PIL import Image
    topos=settings['topographies']
    repo=Path(repo) if repo else Path(__file__).resolve().parents[3]
    tiles={r['location']:r['state'] for r in pl.read_csv(contract.root/'navigation/tiles.csv').iter_rows(named=True)}
    path=mod_root/'in_game/map_data/location_templates.txt'
    text=path.read_text(encoding='utf-8-sig');count=Counter()
    def sub(m):
        state=tiles.get(m.group(1))
        if state not in topos:return m.group(0)
        count[topos[state]['key']]+=1
        return re.sub(r'topography\s*=\s*\w+',f"topography = {topos[state]['key']}",m.group(0),count=1)
    text=re.sub(r'^(pp_nav_\d+)\s*=\s*\{[^\n]*\}',sub,text,flags=re.M)
    path.write_text('﻿'+text,encoding='utf-8',newline='\n')
    blocks=[];types=[];icons=[];loc=['﻿l_english:']
    for state,spec in topos.items():
        k=spec['key'];color='rgb {{ {} {} {} }}'.format(*spec['map_color'])
        if state=='barrier':
            body=(f"\tcolor = {color}\n\tmovement_cost = {spec['movement_cost']}\n"
                  "\tlocation_modifier = { blocks_vision_from_sea = yes blocks_vision_from_land = yes }\n")
        else:
            body=(f"\tcolor = {color}\n\tcan_freeze_over = yes\n\tcan_have_ice = yes\n\tmovement_cost = {spec['movement_cost']}\n"
                  "\tweather_front_strength_change_percent = 0\n\tweather_cyclone_strength_change_percent = 0\n\tweather_tornado_strength_change_percent = 0\n"
                  "\tlocation_modifier = { blocks_vision_from_sea = yes }\n")
        blocks.append(f"{k} = {{\n{body}\taudio_tags = {{ masDataTopologyElevation = 0 masDataTopologyOcean = 1 }}\n}}")
        types.append(f"{k}_proximity_impact = {{\n\tpercent = yes\n\tcolor = bad\n\tgame_data = {{ category = country }}\n}}")
        # vanilla has a proximity icon for narrows, not for ocean_wasteland
        icons.append(f"{k}_proximity_impact = {{\n\tpositive = \"gfx/interface/icons/modifier_types/narrows_proximity_impact.dds\"\n}}")
        loc+=[f' {k}: "{spec["name"]}"',f' {k}_desc: "{spec["description"]}"',
              f' MODIFIER_TYPE_NAME_{k}_proximity_impact: "{spec["name"]} Proximity"',
              f' MODIFIER_TYPE_DESC_{k}_proximity_impact: "How much a nearby {spec["name"].lower()} slows the spread of control."']
        # the location view reads topography icons from main_menu (vanilla has no in_game copy)
        dest=mod_root/'main_menu/gfx/interface/topography'/f'{k}.dds';dest.parent.mkdir(parents=True,exist_ok=True)
        with Image.open(repo/spec['icon']) as icon:
            if icon.size!=(64,64):raise ValueError(f"{spec['icon']}: topography icons are 64x64, got {icon.size}")
            icon.convert('RGBA').save(dest,format='DDS')
        (mod_root/'in_game/gfx/interface/topography'/f'{k}.dds').unlink(missing_ok=True)
    header='# Generated by ppc worldbuilder (navigation.py); do not edit by hand.\n'
    out={'in_game/common/topography/pp_river_topography.txt':'\n\n'.join(blocks),
         'main_menu/common/modifier_type_definitions/pp_river_topography_types.txt':'\n'.join(types),
         'main_menu/common/modifier_icons/pp_river_topography_icons.txt':'\n'.join(icons)}
    for rel,body in out.items():
        p=mod_root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('﻿'+header+body+'\n',encoding='utf-8',newline='\n')
    p=mod_root/'main_menu/localization/english/pp_river_topography_l_english.yml'
    p.write_text('\n'.join(loc)+'\n',encoding='utf-8',newline='\n')
    recolor_land_topographies(mod_root,settings.get('land_topography_colors',{}))
    return dict(count)


def recolor_land_topographies(mod_root,colors):
    """Land topographies whose World Builder colour is a water blue (Floodplains, Deltas) get a land colour, so the
    thin river channels are the only water-coloured strips in the Topography map mode."""
    import re
    if not colors:return
    path=mod_root/'main_menu/common/named_colors/ha1300_topography.txt'
    text=path.read_text(encoding='utf-8-sig')
    for name,rgb in colors.items():
        text,n=re.subn(rf'^(\s*{re.escape(name)}\s*=\s*)rgb\s*\{{[^}}]*\}}',lambda m:m.group(1)+'rgb {{ {} {} {} }}'.format(*rgb),text,flags=re.M)
        if n!=1:raise ValueError(f'{path.name}: expected 1 named colour {name}, found {n}')
    path.write_text('﻿'+text,encoding='utf-8',newline='\n')


def exchange_levels(levels,site):
    """A documented starting navigation: one canal level at its bank (the canal holds no capacity)."""
    if not site or not site.get('start_levels'):return 0
    levels[site['building']]=(1,1)
    return 1
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


def discovery_effect(tiles,shores):
    """Game start: every country discovers the river channels along the land it knows.

    The channels are sea zones in their own region (pp_navigation_region), which no vanilla discovery template lists,
    so without this every river showed as terra incognita for every country. A channel is discovered with its main
    bank (most shore pixels); channels grouped by that bank need one check per bank and country. A channel without a
    land bank follows any discovered neighbour."""
    best={}
    for s in shores:
        w=s['water_location']
        if w in tiles and (w not in best or int(s['shore_pixels'])>best[w][0]):best[w]=(int(s['shore_pixels']),s['location_tag'])
    by_bank=defaultdict(list)
    for w in sorted(tiles):
        if w in best:by_bank[best[w][1]].append(w)
    lines=['pp_navigation_discovery = {',' every_country = {','  save_scope_as = pp_nav_discoverer']
    for bank,waters in sorted(by_bank.items()):
        inner=' '.join(f'location:{w} = {{ discover_location = scope:pp_nav_discoverer }}' for w in waters)
        lines.append(f'  location:{bank} = {{ if = {{ limit = {{ is_discovered_by = scope:pp_nav_discoverer }} {inner} }} }}')
    for w in sorted(tiles):
        if w not in best:   # after the banks: its neighbouring channels are discovered by now
            lines.append(f'  location:{w} = {{ if = {{ limit = {{ any_neighbor_location = {{ is_discovered_by = scope:pp_nav_discoverer }} }} '
                         'discover_location = scope:pp_nav_discoverer } }')
    lines+=[' }','}']
    return '# Generated by ppc worldbuilder (navigation.py); do not edit by hand.\n'+'\n'.join(lines)+'\n'


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
    effects,start=canal_effects(state,edge_line,road_names)
    write('in_game/common/scripted_effects/pp_navigation_routes.txt','\n'.join(seed+effects)+'\n')
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
    shores=list(pl.read_csv(contract.root/'navigation/shores.csv').iter_rows(named=True))
    write('in_game/common/scripted_effects/pp_navigation_discovery.txt',discovery_effect(state['tiles'],shores))
    # Starting building levels that need the river are added after the rivers are restored (start_simulation).
    write('in_game/common/on_action/pp_navigation.txt','\n'.join([
        'on_game_start = { on_actions = { pp_navigation_start } }','pp_navigation_start = { effect = {',
        ' pp_navigation_discovery = yes',
        ' pp_navigation_preserve_rivers = yes',' pp_start_river_topup = yes',' pp_navigation_map_seed = yes',' pp_navigation_seed = yes',*start,' pp_navigation_map_refresh = yes','} }'])+'\n')
    canal=state['settings']['canal']
    write('in_game/common/advances/pp_navigation.txt',f"TRY_INJECT:{canal['advance']} = {{ unlock_building = {canal['key']} }}\n")
    loc=['l_english:', ' pp_navigation_navigable: "Navigable River"',' pp_navigation_improvable: "Shallows"',
         ' pp_navigation_barrier: "Falls"',' pp_navigation_improved: "Canal Passage"',
         ' pp_navigation_difficult: "Difficult Waterway"',
         ' pp_navigation_navigable_desc: "A river reach that boats can use. Movement and trade along it are easier."',
         ' pp_navigation_difficult_desc: "A large tropical or strongly seasonal river. Boats can use it, but slowly and at a cost."',
         ' pp_navigation_improvable_desc: "Shoals and mill weirs: boats pass slowly and at a cost until a River Navigation Canal is built on a bank."',
         ' pp_navigation_barrier_desc: "Falls or great rapids that boats cannot pass."',
         ' pp_navigation_improved_desc: "Shallows kept open by a River Navigation Canal on a bank."',
         ' pp_river_canal_built_tt: "Opens the shallows next to this location for boats: movement and trade along them become easier."',
         ' pp_river_canal_destroyed_tt: "The shallows next to this location close again unless another bank keeps a River Navigation Canal."',
         f' STATIC_MODIFIER_NAME_{CANAL_OPEN}: "Canal Passage"',
         f' STATIC_MODIFIER_DESC_{CANAL_OPEN}: "A River Navigation Canal on a bank keeps these shallows open for boats."']
    write('main_menu/localization/english/pp_navigation_roads_l_english.yml','\n'.join(loc)+'\n')
    triggers=[]
    for n in range(1,6):
        triggers.append(f'pp_navigation_river_level_{n} = {{ has_location_modifier = river_flowing_through_{n} }}')
    # has_river reads the engine's own river (its river_flowing_through_N static modifier is invisible to
    # has_location_modifier): without it every river location got its river modifier a second time at game start
    # (seen 2026-09-30: Anji listed "Stream Flowing Through" twice).
    triggers.append('pp_navigation_has_river = { OR = { has_river = yes '+' '.join(f'pp_navigation_river_level_{n} = yes' for n in range(1,6))+' } }')
    write('in_game/common/scripted_triggers/pp_navigation_rivers.txt','\n'.join(triggers)+'\n')
    from .navigation_map_modes import write_map_modes
    write_map_modes(mod_root,state)
    from eu5gameparser.clausewitz.parser import parse_file
    initial=defaultdict(dict)
    # the start placement moves the World Builder rows into the cities file: read every start setup file
    for path in sorted((mod_root/buildings.SETUP_PATH).parent.glob('*.txt')):
        if 'building_manager' not in path.read_text(encoding='utf-8-sig',errors='replace'):continue
        for manager in parse_file(path).entries:
            if manager.key != 'building_manager':continue
            for entry in manager.value.entries:
                values={field.key:field.value for field in entry.value.entries}
                if int(values.get('level',0))>0 and 'location' in values:
                    initial[values['location']][entry.key]=int(values['level'])
    active_sites={tag:sorted(set(initial[tag])&set(site['supporting_buildings'])) for tag,site in state['sites'].items() if set(initial[tag])&set(site['supporting_buildings'])}
    report={'enabled':True,'tiles':len(state['tiles']),'edges':len(state['edges']),'shallows':len(state['shallows']),
            'shallows_banks':sum(len(v) for v in state['banks'].values()),'starting_canals':len(state['sites']),
            'initially_open_sites':active_sites,
            'river_effects_restored':len(lost), 'native_bank_pixels_preserved':state['manifest'].get('preserved_river_pixels',0), 'ocean_connected_passable_tiles':state['manifest']['ocean_connected_passable_tiles'], 'river_ports_changed':state['manifest']['ports_changed'], 'spline_network':spline_report,
            'engine_facts':['add_road_to replaces an existing road type both ways (verified in game 2026-09-27).',
                            'on_built fires on the next daily tick; on_destroyed fires while the building still counts (verified 2026-09-27).',
                            'Roads are undirected; fleet class cannot be restricted on sea tiles.']}
    output=repo/'artifacts/data/worldbuilder/navigation';output.mkdir(parents=True,exist_ok=True)
    with (output/'building_inventory.csv').open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fieldnames=['location','region','building_key','evidence','starting_levels','open_at_start','shallows_tiles'])
        writer.writeheader()
        for tag,site in sorted(state['sites'].items()):
            writer.writerow({'location':tag,'region':site.get('region',''),'building_key':site['building'],'evidence':site['evidence'],
                             'starting_levels':initial[tag].get(site['building'],0),'open_at_start':bool(active_sites.get(tag)),
                             'shallows_tiles':';'.join(site['water_tiles'])})
    (output/'sites.json').write_text(json.dumps(state['sites'],indent=2)+'\n')
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def site_markers(state):
    """No per-location markers: the canal's gate reads the map (a Shallows neighbour) directly."""
    return {}


def write_bonus_compensation(state,mod_root,vanilla_root):
    """Native bank pixels own river effects; never add scripted duplicates. Also defines the canal's tile modifier."""
    if state['manifest'].get('river_preservation')!='native_bank_pixel':
        raise ValueError('Rebuild World Builder navigation: native river preservation contract required')
    blocks=['# River effects are preserved by the native river bitmap.',
            '# On a Shallows tile while a River Navigation Canal on a bank keeps it open (navigation.canal_effects).',
            f'{CANAL_OPEN} = {{\n\tgame_data = {{ category = location }}\n}}']
    (mod_root/'main_menu/common/static_modifiers/pp_navigation_preservation.txt').write_text('\n\n'.join(blocks)+'\n')
    stale=mod_root/'main_menu/localization/english/pp_navigation_preservation_l_english.yml'
    if stale.exists():stale.unlink()
    return {}
