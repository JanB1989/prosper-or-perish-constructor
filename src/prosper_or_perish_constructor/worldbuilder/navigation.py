"""Consume World Builder navigation evidence and compile gameplay integration.

Channel tiles take a topography by their state (Navigable River, Shallows, Falls). The channels are plain sea tiles:
no water roads and no building act on them (the River Navigation Canal and the hidden navigation road types were
removed 2026-10-13; neither the player nor the AI can build a road that touches a sea tile, EU5 1.4). Shallows with
documented starting navigation (``starting_evidence``, the Grand Canal) start as Navigable River.
"""
from collections import Counter, defaultdict
from dataclasses import replace
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


def validate_routes(tiles, edges):
    """Reject ambiguous undirected connections."""
    seen = set()
    for edge in edges:
        source, target = edge['from'], edge['to']
        pair = tuple(sorted((source, target)))
        if source == target or pair in seen:
            raise ValueError(f'Duplicate or self-connected navigation route: {pair}')
        seen.add(pair)
        if source not in tiles:
            raise ValueError(f'Unknown navigation source: {source}')


def opened_at_start(settings, location_attributes, tiles, shores):
    """Shallows tiles with documented starting navigation: any ownable bank inside a ``starting_evidence`` envelope."""
    attrs = {r['location_tag']: r for r in location_attributes.select('location_tag', 'calibrated_lon', 'calibrated_lat').iter_rows(named=True)}
    return {s['water_location'] for s in shores
            if tiles.get(s['water_location'], {}).get('state') == 'improvable' and s['location_tag'] in attrs
            and historical_evidence(settings, attrs[s['location_tag']])}


def channel_tiles(settings, contract):
    """The handover's channel tiles, documented starting navigations turned Navigable River."""
    root = contract.root/'navigation'
    tiles = {r['location']: r for r in pl.read_csv(root/'tiles.csv').iter_rows(named=True)}
    shores = list(pl.read_csv(root/'shores.csv').iter_rows(named=True))
    opened = opened_at_start(settings, contract.location_attributes, tiles, shores)
    return {t: ({**tile, 'state': 'navigable'} if t in opened else tile) for t, tile in tiles.items()}, shores, opened


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
    tiles,shores,opened=channel_tiles(settings,contract)
    edges=list(pl.read_csv(root/'edges.csv').iter_rows(named=True))
    validate_routes(tiles,edges)
    state={'settings':settings,'manifest':manifest,'tiles':tiles,'edges':edges,'opened_at_start':sorted(opened),
           'shallows':sorted(t for t,tile in tiles.items() if tile['state']=='improvable')}
    raw=dict(cfg.raw);raw['_navigation']=state
    cfg=replace(cfg,raw=raw)
    if write_blueprints:
        ensure_blueprints(repo,settings)
    return cfg


def ensure_blueprints(repo,settings):
    """Retired buildings lose their blueprint and manifest entry; linked buildings no longer touch the water roads."""
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
    path.write_text(yaml.safe_dump(manifest,sort_keys=False),encoding='utf-8')


RIVER_SIZES_LIVE='pp_navigation_river_sizes_live'  # set while pp_navigation_preserve_rivers runs, if river sizes read
# generated by earlier builds (navigation roads, River Navigation Canal); removed from the mod folder on every build
STALE_RUNTIME=('in_game/common/road_types/pp_navigation.txt',
               'in_game/gfx/map/spline_network/spline_styles/pp_navigation.txt',
               'in_game/common/scripted_effects/pp_navigation_routes.txt',
               'in_game/common/advances/pp_navigation.txt',
               'main_menu/localization/english/pp_navigation_roads_l_english.yml')


def write_topographies(mod_root,vanilla_root,contract,settings,repo=None):
    """Channel tiles take the topography of their state; the three water topographies with their own icons (drawn by
    assets/icons/topography/draw.py), their own Topography map mode colours, proximity modifier types (the engine
    requires <topography>_proximity_impact) and names."""
    import re
    from pathlib import Path

    from PIL import Image
    topos=settings['topographies']
    repo=Path(repo) if repo else Path(__file__).resolve().parents[3]
    tiles={tag:tile['state'] for tag,tile in channel_tiles(settings,contract)[0].items()}
    path=mod_root/'in_game/map_data/location_templates.txt'
    text=path.read_text(encoding='utf-8-sig');count=Counter()
    def sub(m):
        state=tiles.get(m.group(1))
        if state not in topos:return m.group(0)
        count[topos[state]['key']]+=1
        return re.sub(r'topography\s*=\s*\w+',f"topography = {topos[state]['key']}",m.group(0),count=1)
    text=re.sub(r'^(pp_nav_\d+)\s*=\s*\{[^\n]*\}',sub,text,flags=re.M)
    path.write_text('﻿'+text,encoding='utf-8',newline='\n')
    blocks=[];types=[];icons=[];capitals=[];loc=['﻿l_english:']
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
        # the engine looks up capital_in_<topography> for every topography (EU5 1.4); empty, like vanilla's water ones
        capitals.append(f"capital_in_{k} = {{\n\tgame_data = {{\n\t\tcategory = country\n\t}}\n}}")
        loc+=[f' {k}: "{spec["name"]}"',f' {k}_desc: "{spec["description"]}"',
              f' MODIFIER_TYPE_NAME_{k}_proximity_impact: "{spec["name"]} Proximity"',
              f' MODIFIER_TYPE_DESC_{k}_proximity_impact: "How much a nearby {spec["name"].lower()} slows the spread of control."',
              f' STATIC_MODIFIER_NAME_capital_in_{k}: "Capital in {spec["name"]}"']
        # the location view reads topography icons from main_menu (vanilla has no in_game copy)
        dest=mod_root/'main_menu/gfx/interface/topography'/f'{k}.dds';dest.parent.mkdir(parents=True,exist_ok=True)
        with Image.open(repo/spec['icon']) as icon:
            if icon.size!=(64,64):raise ValueError(f"{spec['icon']}: topography icons are 64x64, got {icon.size}")
            icon.convert('RGBA').save(dest,format='DDS')
        (mod_root/'in_game/gfx/interface/topography'/f'{k}.dds').unlink(missing_ok=True)
    header='# Generated by ppc worldbuilder (navigation.py); do not edit by hand.\n'
    out={'in_game/common/topography/pp_river_topography.txt':'\n\n'.join(blocks),
         'main_menu/common/modifier_type_definitions/pp_river_topography_types.txt':'\n'.join(types),
         'main_menu/common/modifier_icons/pp_river_topography_icons.txt':'\n'.join(icons),
         'main_menu/common/static_modifiers/pp_river_topography_capitals.txt':'\n'.join(capitals)}
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
    for rel in STALE_RUNTIME:
        (mod_root/rel).unlink(missing_ok=True)
    # the vanilla network plus strips for the land adjacencies of the mod's map that vanilla has none for
    spline_report=spline_network.write(mod_root,vanilla_root,[],land_cache=repo/'artifacts/data/worldbuilder/land_adjacency.json')
    lost=list(pl.read_csv(contract.root/'navigation/lost_river_effects.csv').iter_rows(named=True))
    shores=list(pl.read_csv(contract.root/'navigation/shores.csv').iter_rows(named=True))
    river_levels={row['location_tag']:int(row['river_level'] or 0) for row in contract.location_attributes.select('location_tag','river_level').iter_rows(named=True)}
    # A location gets its river back only where it has no river size at all: modifier:irrigant_cap_modifier is N on
    # every river_flowing_through_N, the engine's own statics included (has_location_modifier does not see those), so
    # nothing ever carries two. has_river is no test: banks that keep stray river pixels but get no size from the
    # engine (Yangtze: Hanyang, Jiangling, Jinhua) have has_river = yes and were left without a river.
    # Probes: big-river locations away from the channels, where the engine has its river size. If none of them reads a
    # size at game start, the modifier values are not live yet and the restore falls back to has_river.
    probes=sorted((t for t,lv in river_levels.items() if lv>=3 and t not in {s['location_tag'] for s in shores}
                   and t not in {r['location_tag'] for r in lost}),key=lambda t:(-river_levels[t],t))[:8]
    bonus=['pp_navigation_preserve_rivers = {',
           ' if = { limit = { OR = { '+' '.join(f'location:{t} = {{ modifier:irrigant_cap_modifier > 0.5 }}' for t in probes)+' } }',
           f'  set_global_variable = {{ name = {RIVER_SIZES_LIVE} value = yes }}',' }']
    for row in lost:
        tag=row['location_tag'];level=int(row['river_level'])
        coast=f' add_location_modifier = {{ modifier = river_flowing_through_coast_{level} days = -1 mode = replace }}' if row['original_coastal'] else ''
        bonus.append(f' location:{tag} = {{ if = {{ limit = {{ pp_navigation_river_missing = yes }} add_location_modifier = {{ modifier = river_flowing_through_{level} days = -1 mode = replace }}{coast} }} }}')
    # The engine traces its river sizes from rivers.png and drops some bank remnants the navigation export keeps
    # (Hanyang, Mechelen), while the World Builder still gives them a river level. Such a location gets its level
    # back; one the engine sized differently keeps the engine's (no double bonus).
    lost_tags={row['location_tag'] for row in lost}
    for tag,level in river_levels.items():
        if level and tag not in lost_tags:
            bonus.append(f" location:{tag} = {{ if = {{ limit = {{ pp_navigation_river_missing = yes }} add_location_modifier = {{ modifier = river_flowing_through_{level} days = -1 mode = replace }} }} }}")
    bonus+=[f' remove_global_variable = {RIVER_SIZES_LIVE}','}']
    write('in_game/common/scripted_effects/pp_navigation_river_bonuses.txt','\n'.join(bonus)+'\n')
    write('in_game/common/scripted_effects/pp_navigation_discovery.txt',discovery_effect(state['tiles'],shores))
    # Starting building levels that need the river are added after the rivers are restored (start_simulation).
    write('in_game/common/on_action/pp_navigation.txt','\n'.join([
        'on_game_start = { on_actions = { pp_navigation_start } }','pp_navigation_start = { effect = {',
        ' pp_navigation_discovery = yes',
        ' pp_navigation_preserve_rivers = yes',' pp_start_river_topup = yes',' pp_navigation_map_seed = yes','} }'])+'\n')
    triggers=[]
    for n in range(1,6):
        triggers.append(f'pp_navigation_river_level_{n} = {{ has_location_modifier = river_flowing_through_{n} }}')
    # has_river reads the engine's own river (its river_flowing_through_N static modifier is invisible to
    # has_location_modifier): without it every river location got its river modifier a second time at game start
    # (seen 2026-09-30: Anji listed "Stream Flowing Through" twice).
    triggers.append('pp_navigation_has_river = { OR = { has_river = yes '+' '.join(f'pp_navigation_river_level_{n} = yes' for n in range(1,6))+' } }')
    # no river size at all (engine or script): irrigant_cap_modifier = N on every river_flowing_through_N
    triggers.append('pp_navigation_river_missing = { OR = { '
                    f'AND = {{ has_global_variable = {RIVER_SIZES_LIVE} modifier:irrigant_cap_modifier < 0.5 }} '
                    f'AND = {{ NOT = {{ has_global_variable = {RIVER_SIZES_LIVE} }} NOT = {{ pp_navigation_has_river = yes }} }} }} }}')
    write('in_game/common/scripted_triggers/pp_navigation_rivers.txt','\n'.join(triggers)+'\n')
    from .navigation_map_modes import write_map_modes
    write_map_modes(mod_root,state)
    report={'enabled':True,'tiles':len(state['tiles']),'edges':len(state['edges']),'shallows':len(state['shallows']),
            'opened_at_start':state['opened_at_start'],
            'river_effects_restored':len(lost), 'native_bank_pixels_preserved':state['manifest'].get('preserved_river_pixels',0), 'ocean_connected_passable_tiles':state['manifest']['ocean_connected_passable_tiles'], 'river_ports_changed':state['manifest']['ports_changed'], 'spline_network':spline_report}
    output=repo/'artifacts/data/worldbuilder/navigation';output.mkdir(parents=True,exist_ok=True)
    for stale in ('building_inventory.csv','sites.json'):
        (output/stale).unlink(missing_ok=True)
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def write_bonus_compensation(state,mod_root,vanilla_root):
    """Native bank pixels own river effects; never add scripted duplicates."""
    if state['manifest'].get('river_preservation')!='native_bank_pixel':
        raise ValueError('Rebuild World Builder navigation: native river preservation contract required')
    (mod_root/'main_menu/common/static_modifiers/pp_navigation_preservation.txt').unlink(missing_ok=True)
    stale=mod_root/'main_menu/localization/english/pp_navigation_preservation_l_english.yml'
    if stale.exists():stale.unlink()
    return {}
