"""In-game river diagnostics using native river levels and live works status."""
from collections import defaultdict
import shutil


def write_map_modes(root,state):
    def write(rel,text):
        path=root/rel;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('\ufeff'+text+'\n',encoding='utf-8')
    shores=defaultdict(set)
    for e in state['edges']:
        if e['shore']:shores[e['to']].add(e['state'])
    seed=['pp_navigation_map_seed = {']
    rough={tag for e in state['edges'] if e.get('cost_profile')=='difficult'
           for tag in (e['from'],e['to']) if tag in state['tiles']}
    for tag,tile in sorted(state['tiles'].items()):
        status={'navigable':1,'improvable':2,'barrier':3}[tile['state']]
        if status==1 and tag in rough:status=5
        seed.append(f' location:{tag} = {{ set_variable = {{ name = pp_navigation_map_state value = {status} }} set_variable = {{ name = pp_navigation_water_level value = {tile.get('river_level',0)} }} set_variable = {{ name = pp_navigation_ocean_connected value = {int(bool(tile.get('ocean_connected',False)))} }} }}')
    for tag,kinds in sorted(shores.items()):
        seed.append(f' location:{tag} = {{ set_variable = {{ name = pp_navigation_bank value = {1 if kinds-set(["barrier"]) else 2} }} }}')
    seed.append('}')
    targets=defaultdict(set)
    for e in state['edges']:
        if e['state']=='barrier':continue
        for a,b in [(e['from'],e['to']),(e['to'],e['from'])]:
            if a in state['tiles']:targets[a].add(b)
    global_refresh=['pp_navigation_map_refresh = {']
    for tag,tile in sorted(state['tiles'].items()):
        if tile['state']=='barrier':continue
        status=2 if tile['state']=='improvable' else 5 if tag in rough else 1
        checks=[f'has_road_of_type_to = {{ target = location:{other} type = road_type:pp_navigation_improved }}' for other in sorted(targets[tag])]
        if not checks:continue
        seed.extend([f'pp_navigation_map_refresh_{tag} = {{',
                     ' if = { limit = { '+' '.join(checks)+' } set_variable = { name = pp_navigation_map_state value = 4 } }',
                     ' else_if = { limit = { OR = { '+' '.join(checks)+' } } set_variable = { name = pp_navigation_map_state value = 6 } }',
                     f' else = {{ set_variable = {{ name = pp_navigation_map_state value = {status} }} }}','}'])
        global_refresh.append(f' location:{tag} = {{ pp_navigation_map_refresh_{tag} = yes }}')
    global_refresh.append('}');seed.extend(global_refresh)
    write('in_game/common/scripted_effects/pp_navigation_map.txt','\n'.join(seed))
    categories=[
      ('maintained','has_variable = pp_navigation_map_state var:pp_navigation_map_state = 4','65 245 170','Maintained waterway','All mapped passable connections at this waterway have the maintained navigation route type.'),
      ('partial','has_variable = pp_navigation_map_state var:pp_navigation_map_state = 6','170 225 85','Partly maintained waterway','Some mapped connections are maintained; others retain their baseline transport costs. Inspect individual routes for details.'),
      ('barrier','has_variable = pp_navigation_map_state var:pp_navigation_map_state = 3','225 65 65','River barrier','This converted river zone blocks fleet passage. Navigation works cannot remove this natural barrier.'),
      ('improvable','has_variable = pp_navigation_map_state var:pp_navigation_map_state = 2','245 180 60','Unimproved waterway','Fleets can pass at high cost. Local navigation works improve the maintained connections.'),
      ('difficult','has_variable = pp_navigation_map_state var:pp_navigation_map_state = 5','190 115 200','Difficult waterway','Large tropical or strongly seasonal waterway. Baseline movement and market-access costs are higher; navigation works can improve maintained connections.'),
      ('navigable','has_variable = pp_navigation_map_state var:pp_navigation_map_state = 1','35 180 245','Navigable waterway','Converted river zone open to fleets. Inspect route connections for movement and market-access costs.')]
    colors={1:'130 180 170',2:'100 170 130',3:'65 155 100',4:'35 130 70',5:'20 100 45'}
    for n in range(5,0,-1):
        categories.append((f'level_{n}',f'has_location_modifier = river_flowing_through_{n}',colors[n],f'River level {n}',f'Native river level {n}. River bonuses and river-dependent building limits use this level, including preserved banks of converted waterways.'))
    colorscript=[];tooltips=[];loc=['l_english:', ' MAPMODE_PP_RIVER_NAVIGATION: "Rivers and Navigation"',' mapmode_pp_river_navigation_name: "Rivers and Navigation"',' MAPMODE_PP_RIVER_NAVIGATION_DESC: "River levels, converted waterways, barriers and navigation works."']
    for i,(key,condition,color,name,desc) in enumerate(categories):
        branch='if' if i==0 else 'else_if';lk='PP_NAV_MAP_'+key.upper()
        colorscript.append(f' {branch} = {{ limit = {{ {condition} }} value = rgb {{ {color} }} }}')
        tooltips.append(f' {branch} = {{ limit = {{ {condition} }} value = {lk}_TT }}')
        loc += [f' {lk}: "{name}"',f' {lk}_TT: "{name}\\n{desc}"']
    # Bank tooltip distinguishes an actual port from an impassable frontage.
    # Level is still the map colour; the tooltip supplies the landing status.
    banktips=[]
    for n in range(5,0,-1):
        for port in (True,False):
            k=f'PP_NAV_BANK_{n}_{int(port)}'
            condition=f'has_variable = pp_navigation_bank has_location_modifier = river_flowing_through_{n} is_port = {"yes" if port else "no"}'
            banktips.append(f' {"if" if not banktips else "else_if"} = {{ limit = {{ {condition} }} value = {k} }}')
            desc='Port location: a fleet landing is defined. An existing coastal port may face the sea instead of this river.' if port else 'Riverbank without a usable fleet landing; check the adjacent waterway for barriers.'
            loc.append(f' {k}: "River level {n}\\n{desc}\\nNormal river bonuses and river-dependent building limits are preserved."')
    watertips=[]
    for key,condition,_,name,desc in categories[:6]:
        for n in range(6):
            for connected in (0,1):
                k=f'PP_NAV_WATER_{key.upper()}_{n}_{connected}'
                test=f'{condition} has_variable = pp_navigation_water_level var:pp_navigation_water_level = {n} has_variable = pp_navigation_ocean_connected var:pp_navigation_ocean_connected = {connected}'
                watertips.append(f' else_if = {{ limit = {{ {test} }} value = {k} }}')
                access='Connected to the open sea.' if connected else 'Inland reach: no continuous passable connection to the open sea.'
                level=f'Original river level {n}.' if n else 'River mouth alignment.'
                loc.append(f' {k}: "{name}\\n{level} {access}\\n{desc}"')
    if banktips:tooltips[0]=tooltips[0].replace(' if =',' else_if =',1)
    colorscript.append(' else = { value = rgb { 45 60 72 } }')
    tooltips.append(' else = { value = PP_NAV_MAP_NONE_TT }')
    loc += [' PP_NAV_MAP_NONE_TT: "No native river level or converted waterway at this location."']
    legend=[f' legend_key = {{ desc = "PP_NAV_MAP_{key.upper()}" color = rgb {{ {color} }} }}' for key,_,color,_,_ in categories]
    text='pp_river_navigation = {\n map_color = {\n'+'\n'.join(colorscript)+'\n }\n tooltip_key = {\n'+'\n'.join(banktips+watertips+tooltips)+'\n }\n'+'\n'.join(legend)+\
    '\n small_map_names = location\n medium_map_names = location\n large_map_names = none\n small_tooltip_context = location\n medium_tooltip_context = location\n large_tooltip_context = location\n fill_in_impassable = yes\n enable_snow = no\n enable_rivers = yes\n flatmap_behaviour = always\n use_fow = no\n category = geography\n index = 4\n allow_allocate_hotkey = yes\n map_markers = { all = no }\n gradient_parameters = { zoom_step = 2 gradient_alpha_inside = 1 gradient_alpha_outside = 1 gradient_width = 0.25 gradient_color_mult = 0.9 edge_width = 0 edge_sharpness = 0.01 edge_alpha = 0 edge_color_mult = 0 before_lighting_blend = 0.5 after_lighting_blend = 0.5 }\n color_refresh_counters = { LocationRoadsChanged LocationOwnerChanged Day }\n}\n'
    write('in_game/gfx/map/map_modes/pp_river_navigation.txt',text)
    write('main_menu/localization/english/pp_river_navigation_map_l_english.yml','\n'.join(loc))
    # Reuse the existing geography icon; no new art dependency for this debug view.
    for folder in ('main_menu','in_game'):
        dest=root/folder/'gfx/interface/icons/map_modes/pp_river_navigation.dds'
        source=root/folder/'gfx/interface/icons/map_modes/ha1300_soil_types.dds'
        if source.exists():dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
