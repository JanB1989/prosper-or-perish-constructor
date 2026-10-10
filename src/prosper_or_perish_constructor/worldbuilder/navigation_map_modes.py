"""The Navigable Rivers map mode and the per-location navigation state it reads (seeded at game start, refreshed when a
   River Navigation Canal is built or destroyed)."""
from collections import defaultdict


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
    write(f'in_game/gfx/map/map_modes/{MAP_MODE}.txt',map_mode_text())
    write(f'main_menu/localization/english/{MAP_MODE}_map_l_english.yml',map_mode_localization())


# The Navigable Rivers map mode (Geography, beside vanilla's Rivers; no index puts it in Rivers' group). The water
# colours the channels by kind, dark stripes mark waterways cut off from the open sea, the land shows river ports,
# other banks and the rivers no boat can sail; everything else stays dark so the network stands out. Its icon is drawn
# by tools/build_navigable_rivers_icon.py; the concept of the same key (the Europedia card) carries the icon texture.
MAP_MODE='pp_navigable_rivers'
_STATE='has_variable = pp_navigation_map_state var:pp_navigation_map_state = {}'
_OPEN='has_variable = pp_navigation_ocean_connected var:pp_navigation_ocean_connected = 1'
# map state (set by pp_navigation_map_seed / _refresh): key, colour, name, what it means
WATER=[(4,'canal','40 200 170','Canal Passage','Shallows kept open by a River Navigation Canal on a bank: the easiest waterway of all.'),
       (6,'partial','40 200 170','Partly Opened Shallows','A River Navigation Canal keeps some of these shallows open; the rest still slow boats down.'),
       (1,'navigable','30 140 230','Navigable River','Fleets sail it, and goods travel along it far more cheaply than over land.'),
       (5,'difficult','150 90 200','Difficult Waterway','A great tropical or strongly seasonal river: boats get through, but slowly and at a cost.'),
       (2,'shallows','240 165 40','Shallows','Boats pass slowly and at a cost until a River Navigation Canal is built on a bank.'),
       (3,'falls','215 45 45','Falls','Falls or great rapids that no boat passes and no canal opens.')]
REACH={1:'It reaches the open sea.',0:'It does not reach the open sea: fleets on it cannot sail out.'}
LAND=[('port','has_variable = pp_navigation_bank is_port = yes','245 205 70','River Port',
       'A bank of a navigable river with a port: fleets can land here. It counts as coastal and keeps its river bonuses.'),
      ('bank','has_variable = pp_navigation_bank','205 185 140','Riverbank',
       'A bank of a navigable river without a port. It counts as coastal and keeps its river bonuses.'),
      ('river','is_land = yes pp_navigation_has_river = yes','110 140 130','River',
       'Boats cannot sail this river. It brings its river bonuses only.'),
      ('water','is_land = no','50 68 88','Sea or Lake','')]
OTHER='88 84 78'
CUT_OFF='20 30 50'       # stripes: a waterway that does not reach the open sea
PARTIAL_STRIPE='240 165 40'
LEGEND=[('navigable','30 140 230','Navigable River'),('difficult','150 90 200','Difficult Waterway'),
        ('shallows','240 165 40','Shallows'),('canal','40 200 170','Canal Passage'),
        ('partial',PARTIAL_STRIPE,'Partly opened shallows (striped)'),('falls','215 45 45','Falls'),
        ('cut_off',CUT_OFF,'Does not reach the open sea (striped)'),('port','245 205 70','River Port'),
        ('bank','205 185 140','Riverbank'),('river','110 140 130','River no boat can sail')]


def _key(name):
    return f'PP_NAVMAP_{name.upper()}'


def map_mode_text():
    colors=[];tips=[]
    for state,key,color,_,_ in WATER:
        colors.append(f'{_STATE.format(state)}|{color}')
        if state==3:tips.append(f'{_STATE.format(state)}|{_key(key)}_TT')
        else:
            tips.append(f'{_STATE.format(state)} {_OPEN}|{_key(key)}_OPEN_TT')
            tips.append(f'{_STATE.format(state)}|{_key(key)}_INLAND_TT')
    for key,condition,color,_,_ in LAND:
        colors.append(f'{condition}|{color}');tips.append(f'{condition}|{_key(key)}_TT')
    def chain(rows,last):
        out=[]
        for i,row in enumerate(rows):
            condition,value=row.split('|')
            out.append(f'  {"if" if i==0 else "else_if"} = {{ limit = {{ {condition} }} value = {value} }}')
        return out+[f'  else = {{ value = {last} }}']
    stripes=[f'  if = {{ limit = {{ {_STATE.format(6)} }} value = rgb {{ {PARTIAL_STRIPE} }} }}',
             f'  else_if = {{ limit = {{ has_variable = pp_navigation_map_state NOT = {{ var:pp_navigation_map_state = 3 }} '
             f'NOT = {{ {_OPEN} }} }} value = rgb {{ {CUT_OFF} }} }}']
    lines=[f'{MAP_MODE} = {{',' map_color = {',
           *chain([r.rsplit('|',1)[0]+'|rgb { '+r.rsplit('|',1)[1]+' }' for r in colors],f'rgb {{ {OTHER} }}'),' }',
           ' secondary_map_color = {',*stripes,' }',
           ' tooltip_key = {',*chain(tips,_key('none')+'_TT'),' }',
           *[f' legend_key = {{ desc = "{_key("legend_"+key)}" color = rgb {{ {color} }} }}' for key,color,_ in LEGEND],
           ' small_map_names = location',' medium_map_names = none',' large_map_names = none',
           ' small_tooltip_context = location',' medium_tooltip_context = location',' large_tooltip_context = location',
           ' fill_in_impassable = yes',' enable_snow = no',
           # the vanilla river surface is drawn over the channel locations and would hide their colour
           ' enable_rivers = no',' flatmap_behaviour = always',' use_fow = no',' category = geography',
           ' allow_allocate_hotkey = yes',' map_markers = { all = no }',
           ' gradient_parameters = { zoom_step = 2 gradient_alpha_inside = 1 gradient_alpha_outside = 1 gradient_width = 0.25'
           ' gradient_color_mult = 0.9 edge_width = 0 edge_sharpness = 0.01 edge_alpha = 0 edge_color_mult = 0'
           ' before_lighting_blend = 0.5 after_lighting_blend = 0.5 }',
           ' color_refresh_counters = { LocationRoadsChanged LocationOwnerChanged Day }','}']
    return '\n'.join(lines)


def map_mode_localization():
    # plain text in the map tooltips and the legend (formatter tags there spam error.log); links only in the picker
    loc=['l_english:',
         f' mapmode_{MAP_MODE}_name: "Navigable Rivers"',
         f' MAPMODE_{MAP_MODE.upper()}: "#T $mapmode_{MAP_MODE}_name$#!\\nShows the rivers [navies|e] can sail, where '
         'shallows and falls stop them, which waterways reach the open sea and which banks have a [port|e]."']
    for state,key,_,name,text in WATER:
        if state==3:loc.append(f' {_key(key)}_TT: "{name}\\n{text}"')
        else:
            for connected,suffix in ((1,'OPEN'),(0,'INLAND')):
                loc.append(f' {_key(key)}_{suffix}_TT: "{name}\\n{text} {REACH[connected]}"')
    for key,_,_,name,text in LAND:
        loc.append(f' {_key(key)}_TT: "{name}' + (f'\\n{text}' if text else '') + '"')
    loc.append(f' {_key("none")}_TT: "No river here."')
    loc += [f' {_key("legend_"+key)}: "{name}"' for key,_,name in LEGEND]
    return '\n'.join(loc)
