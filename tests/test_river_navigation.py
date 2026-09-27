from prosper_or_perish_constructor.worldbuilder.navigation import exchange_levels


def test_starting_canal_is_one_level_outside_the_capacity_families():
    levels={}
    assert exchange_levels(levels,{'building':'river_navigation_canal','start_levels':1})==1
    assert levels=={'river_navigation_canal':(1,1)}


def test_no_starting_evidence_means_no_starting_canal():
    levels={}
    assert exchange_levels(levels,{'building':'river_navigation_canal','start_levels':0})==0
    assert exchange_levels(levels,None)==0
    assert levels=={}


def _canal_state():
    settings={'canal':{'key':'river_navigation_canal'},'topographies':{'improvable':{'key':'pp_river_shallows'}}}
    tiles={'s1':{'state':'improvable'},'s2':{'state':'improvable'},'n':{'state':'navigable'}}
    edges=[{'from':'n','to':'s1','state':'improvable','cost_profile':'improvable','shore':False},
           {'from':'s1','to':'s2','state':'improvable','cost_profile':'improvable','shore':False},
           {'from':'s1','to':'bank','state':'improvable','cost_profile':'improvable','shore':True}]
    return {'canal':'river_navigation_canal','shallows':['s1','s2'],'settings':settings,'tiles':tiles,'edges':edges,
            'sites':{'bank':{'building':'river_navigation_canal'}}}


def _edge_line(e,improved=False):
    kind='improved' if improved else e.get('cost_profile',e['state'])
    return f" location:{e['from']} = {{ add_road_to = {{ target = location:{e['to']} type = pp_navigation_{kind} }} }}"


def test_canal_recomputes_each_shallows_tile_from_the_canals_that_exist():
    from prosper_or_perish_constructor.worldbuilder.navigation import CANAL_OPEN, canal_effects
    lines,start=canal_effects(_canal_state(),_edge_line,{})
    text='\n'.join(lines)
    tile=text.split('pp_river_canal_tile_s1 = {')[1].split('\n}')[0]
    # open while any bank has the canal, except the location being destroyed
    assert 'any_neighbor_location = { has_building = building_type:river_navigation_canal NOT = { this = scope:pp_canal_closing } }' in tile
    assert f'remove_location_modifier = {CANAL_OPEN}' in tile
    # a road between two shallows is improved only while both are open; otherwise it keeps its own profile
    assert (f'limit = {{ location:s1 = {{ has_location_modifier = {CANAL_OPEN} }} location:s2 = {{ has_location_modifier = {CANAL_OPEN} }} }}'
            ' location:s1 = { add_road_to = { target = location:s2 type = pp_navigation_improved } }') in tile
    assert 'else = { location:s1 = { add_road_to = { target = location:s2 type = pp_navigation_improvable } } }' in tile
    # destruction skips the destroyed location (on_destroyed runs while its canal still counts)
    destroyed=text.split('pp_river_canal_destroyed = {')[1].split('\n}')[0]
    assert destroyed.index('save_scope_as = pp_canal_closing') < destroyed.index('pp_river_canal_refresh_tile = yes')
    assert 'limit = { this = location:s2 } pp_river_canal_tile_s2 = yes' in text
    assert start==[' location:bank = { if = { limit = { has_building = building_type:river_navigation_canal } pp_river_canal_built = yes } }']


def test_canal_blueprint_gate_reads_the_map_and_has_one_level():
    from prosper_or_perish_constructor.worldbuilder.navigation import CANAL_OPEN, canal_body
    settings={'canal':{'key':'river_navigation_canal','construction_days':540,'upkeep':{'lumber':0.04}},
              'topographies':{'improvable':{'key':'pp_river_shallows'}}}
    body=canal_body(settings)
    assert 'max_levels = 1' in body and 'pp_navigation_site_' not in body
    assert f'any_neighbor_location = {{ topography = pp_river_shallows NOT = {{ has_location_modifier = {CANAL_OPEN} }} }}' in body
    assert 'has_building = building_type:river_navigation_canal' in body   # an existing canal never turns invalid
    assert 'local_population_capacity' not in body


def test_native_pixel_preservation_never_stacks_scripted_bonuses(tmp_path):
    from prosper_or_perish_constructor.worldbuilder.navigation import write_bonus_compensation
    (tmp_path/'main_menu/common/static_modifiers').mkdir(parents=True)
    (tmp_path/'main_menu/localization/english').mkdir(parents=True)
    assert write_bonus_compensation({'manifest':{'river_preservation':'native_bank_pixel'}},tmp_path,tmp_path)=={}
    text=(tmp_path/'main_menu/common/static_modifiers/pp_navigation_preservation.txt').read_text()
    assert 'cancel' not in text and 'river_flowing_through_' not in text


def test_canal_tile_modifier_is_defined_and_no_site_markers_remain(tmp_path):
    from prosper_or_perish_constructor.worldbuilder.navigation import CANAL_OPEN, site_markers, write_bonus_compensation
    (tmp_path/'main_menu/common/static_modifiers').mkdir(parents=True)
    state={'manifest':{'river_preservation':'native_bank_pixel'},'sites':{'a':{'building':'river_navigation_canal'}}}
    assert site_markers(state)=={}
    write_bonus_compensation(state,tmp_path,tmp_path)
    text=(tmp_path/'main_menu/common/static_modifiers/pp_navigation_preservation.txt').read_text()
    assert f'{CANAL_OPEN} = {{' in text and 'pp_navigation_site_' not in text


def test_legacy_compensation_contract_requires_rebuild(tmp_path):
    import pytest
    from prosper_or_perish_constructor.worldbuilder.navigation import write_bonus_compensation
    with pytest.raises(ValueError,match='Rebuild World Builder'):
        write_bonus_compensation({'manifest':{}},tmp_path,tmp_path)


def test_map_mode_emits_only_documented_refresh_counters_and_native_levels(tmp_path):
    from prosper_or_perish_constructor.worldbuilder.navigation_map_modes import write_map_modes
    write_map_modes(tmp_path,{'tiles':{'water':{'state':'improvable'}},'edges':[{'from':'water','to':'bank','shore':True,'state':'improvable'}]})
    text=(tmp_path/'in_game/gfx/map/map_modes/pp_river_navigation.txt').read_text()
    assert 'LocationRoadsChanged' in text
    assert 'LocationBuildingChanged' not in text
    assert 'has_location_modifier = river_flowing_through_5' in text
    assert 'is_port = yes' in text

    loc=(tmp_path/'main_menu/localization/english/pp_river_navigation_map_l_english.yml').read_text()
    assert chr(92)*2+'n' not in loc

    effects=(tmp_path/'in_game/common/scripted_effects/pp_navigation_map.txt').read_text()
    assert 'has_road_of_type_to = { target = location:bank type = road_type:pp_navigation_improved }' in effects
    assert 'value = 6' in effects


def test_regional_envelopes_do_not_leak_into_neighbouring_regions():
    from prosper_or_perish_constructor.worldbuilder.navigation import regional_match
    spec={'bounds':[105,20,123,41], 'regions':['south_china_region']}
    attributes={'calibrated_lon':106,'calibrated_lat':22,'region':'indochina_region'}
    assert not regional_match(attributes,spec)
    assert regional_match({**attributes,'region':'south_china_region'},spec)
    assert not regional_match({**attributes,'region':'south_china_region','calibrated_lon':100},spec)
    assert not regional_match({'calibrated_lon':106,'calibrated_lat':22},spec)


def test_historical_evidence_is_any_documented_envelope():
    from prosper_or_perish_constructor.worldbuilder.navigation import historical_evidence
    entry={'id':'documented','bounds':[0,0,10,10]}
    settings={'starting_evidence':[entry]}
    assert historical_evidence(settings,{'calibrated_lon':5,'calibrated_lat':5}) == entry
    assert historical_evidence(settings,{'calibrated_lon':15,'calibrated_lat':5}) is None


def test_route_validation_rejects_barrier_upgrades_and_duplicate_undirected_edges():
    import pytest
    from prosper_or_perish_constructor.worldbuilder.navigation import validate_routes
    tiles={'water':{'state':'navigable'},'falls':{'state':'barrier'}}
    sites={'bank':{'water_tiles':['water']}}
    edge={'from':'water','to':'falls','state':'barrier','shore':False,'host':''}
    validate_routes(tiles,[edge],sites)
    with pytest.raises(ValueError,match='open a barrier'):
        validate_routes(tiles,[{**edge,'host':'bank'}],sites)
    with pytest.raises(ValueError,match='Duplicate'):
        validate_routes(tiles,[edge,{**edge,'from':'falls','to':'water'}],sites)
    with pytest.raises(ValueError,match='no assigned endpoint'):
        validate_routes(tiles,[{**edge,'to':'ocean','state':'navigable','host':'other'}],sites)
    validate_routes(tiles,[{**edge,'to':'ocean','state':'navigable','host':'bank'}],sites)


def test_map_mode_difficult_routes_count_both_water_endpoints(tmp_path):
    from prosper_or_perish_constructor.worldbuilder.navigation_map_modes import write_map_modes
    write_map_modes(tmp_path,{'tiles':{'a':{'state':'navigable'},'b':{'state':'navigable'}},
        'edges':[{'from':'a','to':'b','shore':False,'state':'navigable','cost_profile':'difficult'}]})
    effects=(tmp_path/'in_game/common/scripted_effects/pp_navigation_map.txt').read_text()
    assert 'location:b = { set_variable = { name = pp_navigation_map_state value = 5 }' in effects
    assert 'else = { set_variable = { name = pp_navigation_map_state value = 5 } }' in effects.split('pp_navigation_map_refresh_b = {')[1]
    loc=(tmp_path/'main_menu/localization/english/pp_river_navigation_map_l_english.yml').read_text()
    assert 'existing coastal port may face the sea' in loc
