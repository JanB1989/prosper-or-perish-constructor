from prosper_or_perish_constructor.worldbuilder.navigation import exchange_levels


def test_starting_works_transfer_capacity_without_adding_it():
    levels={'irrigation_systems':(3,5),'other':(2,4)}
    count=exchange_levels(levels,{'family':'irrigation_systems','building':'canal_lock_works','start_levels':1})
    assert count==1
    assert levels=={'irrigation_systems':(2,5),'other':(2,4),'canal_lock_works':(1,1)}
    assert sum(value[0] for value in levels.values())==5


def test_no_starting_capacity_means_no_free_navigation_building():
    levels={'irrigation_systems':(0,5)}
    assert exchange_levels(levels,{'family':'irrigation_systems','building':'canal_lock_works','start_levels':1})==0
    assert 'canal_lock_works' not in levels


def test_native_pixel_preservation_never_stacks_scripted_bonuses(tmp_path):
    from prosper_or_perish_constructor.worldbuilder.navigation import write_bonus_compensation
    (tmp_path/'main_menu/common/static_modifiers').mkdir(parents=True)
    (tmp_path/'main_menu/localization/english').mkdir(parents=True)
    assert write_bonus_compensation({'manifest':{'river_preservation':'native_bank_pixel'}},tmp_path,tmp_path)=={}
    text=(tmp_path/'main_menu/common/static_modifiers/pp_navigation_preservation.txt').read_text()
    assert 'cancel' not in text and 'river_flowing_through_' not in text


def test_site_markers_are_defined_and_placed_on_each_site(tmp_path):
    from prosper_or_perish_constructor.worldbuilder.navigation import site_markers, write_bonus_compensation
    (tmp_path/'main_menu/common/static_modifiers').mkdir(parents=True)
    (tmp_path/'main_menu/localization/english').mkdir(parents=True)
    state={'manifest':{'river_preservation':'native_bank_pixel'},'settings':{'building_types':{'river_navigation_works':{'name':'River Works'}}},
           'sites':{'a':{'building':'river_navigation_works'},'b':{'building':'canal_lock_works'}}}
    assert site_markers(state)=={'a':['pp_navigation_site_river_navigation_works'],'b':['pp_navigation_site_canal_lock_works']}
    write_bonus_compensation(state,tmp_path,tmp_path)
    assert 'pp_navigation_site_river_navigation_works = {' in (tmp_path/'main_menu/common/static_modifiers/pp_navigation_preservation.txt').read_text()
    assert 'STATIC_MODIFIER_NAME_pp_navigation_site_river_navigation_works' in (tmp_path/'main_menu/localization/english/pp_navigation_preservation_l_english.yml').read_text(encoding='utf-8')


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


def test_historical_host_preference_requires_the_matching_building():
    from prosper_or_perish_constructor.worldbuilder.navigation import historical_evidence
    entry={'id':'documented','bounds':[0,0,10,10],'building':'sluices'}
    settings={'starting_evidence':[entry]}
    attrs={'calibrated_lon':5,'calibrated_lat':5}
    assert historical_evidence(settings,attrs,'locks') is None
    assert historical_evidence(settings,attrs,'sluices') == entry


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
