"""The Navigable Rivers map mode and the per-location navigation state it reads (seeded at game start; fixed for the
   whole game since the River Navigation Canal was removed, 2026-10-13)."""
from collections import defaultdict, deque


def write_map_modes(root,state):
    def write(rel,text):
        path=root/rel;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('\ufeff'+text+'\n',encoding='utf-8')
    shores=defaultdict(set)
    for e in state['edges']:
        if e['shore']:shores[e['to']].add(e['state'])
    seed=['pp_navigation_map_seed = {']
    shade=shades(state)
    for tag,tile in sorted(state['tiles'].items()):
        status={'navigable':1,'difficult':5,'barrier':3}[tile['state']]
        seed.append(f' location:{tag} = {{ set_variable = {{ name = pp_navigation_map_state value = {status} }} set_variable = {{ name = pp_navigation_map_shade value = {shade[tag]} }} set_variable = {{ name = pp_navigation_water_level value = {tile.get('river_level',0)} }} set_variable = {{ name = pp_navigation_ocean_connected value = {int(bool(tile.get('ocean_connected',False)))} }} }}')
    for tag,kinds in sorted(shores.items()):
        seed.append(f' location:{tag} = {{ set_variable = {{ name = pp_navigation_bank value = {1 if kinds-set(["barrier"]) else 2} }} }}')
    seed.append('}')
    write('in_game/common/scripted_effects/pp_navigation_map.txt','\n'.join(seed))
    write(f'in_game/gfx/map/map_modes/{MAP_MODE}.txt',map_mode_text())
    write(f'main_menu/localization/english/{MAP_MODE}_map_l_english.yml',map_mode_localization())


def shades(state):
    """Shade 1..SHADES per channel tile so that touching tiles differ: greedy colouring along each waterway (breadth
    first), avoiding the shades of the neighbours first and of the tiles two steps away second, so a river cycles
    through several shades instead of two. 0 would read as an unset variable."""
    tiles=state['tiles'];nb=defaultdict(set)
    for e in state['edges']:
        if not e['shore'] and e['from'] in tiles and e['to'] in tiles and e['from']!=e['to']:
            nb[e['from']].add(e['to']);nb[e['to']].add(e['from'])
    shade={}
    for start in sorted(tiles):
        if start in shade:continue
        queue=deque([start]);seen={start}
        while queue:
            tag=queue.popleft()
            near=[shade[n] for n in nb[tag] if n in shade]
            far=[shade[m] for n in nb[tag] for m in nb[n] if m!=tag and m in shade]
            shade[tag]=min(range(1,SHADES+1),key=lambda k:(near.count(k),far.count(k),k))
            for n in sorted(nb[tag]-seen):
                seen.add(n);queue.append(n)
    return shade


# The Navigable Rivers map mode (Geography, beside vanilla's Rivers; no index puts it in Rivers' group). The water
# colours the channels by kind, dark stripes mark waterways cut off from the open sea, the land shows river ports,
# other banks and the rivers no boat can sail; everything else stays dark so the network stands out. Its icon is drawn
# by tools/build_navigable_rivers_icon.py; the concept of the same key (the Europedia card) carries the icon texture.
MAP_MODE='pp_navigable_rivers'
_STATE='has_variable = pp_navigation_map_state var:pp_navigation_map_state = {}'
_OPEN='has_variable = pp_navigation_ocean_connected var:pp_navigation_ocean_connected = 1'
# map state (set by pp_navigation_map_seed / _refresh): key, colour, name, what it means. Each water kind is drawn in
# SHADES clearly different shades of its colour (WATER_SHADES; the first is the legend colour), so touching tiles
# stand apart. The map's lighting blend halves the contrast, hence the wide spread (dark, pale, a hue shift).
SHADES=4
WATER_SHADES={1:['30 140 230','0 40 120','160 230 255','0 190 160'],
              5:['150 90 200','75 20 120','230 185 255','215 60 165'],
              3:['215 45 45']*SHADES}
WATER=[(1,'navigable','30 140 230','Navigable River','Fleets sail it, and goods travel along it far more cheaply than over land.'),
       (5,'difficult','150 90 200','Difficult Waterway','Shoals and weirs, or a great tropical or strongly seasonal river: boats get through, but slowly.'),
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
LEGEND=[('navigable','30 140 230','Navigable River'),('difficult','150 90 200','Difficult Waterway'),
        ('falls','215 45 45','Falls'),
        ('cut_off',CUT_OFF,'Does not reach the open sea (striped)'),('port','245 205 70','River Port'),
        ('bank','205 185 140','Riverbank'),('river','110 140 130','River no boat can sail')]


def _key(name):
    return f'PP_NAVMAP_{name.upper()}'


def map_mode_text():
    colors=[];tips=[]
    for state,key,color,_,_ in WATER:
        for k,shade in enumerate(WATER_SHADES[state][1:],2):
            if shade!=color:
                colors.append(f'{_STATE.format(state)} has_variable = pp_navigation_map_shade var:pp_navigation_map_shade = {k}|{shade}')
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
    stripes=[f'  if = {{ limit = {{ has_variable = pp_navigation_map_state NOT = {{ var:pp_navigation_map_state = 3 }} '
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
         'difficult water slows them and falls stop them, which waterways reach the open sea and which banks have a [port|e]."']
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
