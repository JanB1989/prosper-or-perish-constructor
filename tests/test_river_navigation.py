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
