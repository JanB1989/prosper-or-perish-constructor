from prosper_or_perish_constructor.worldbuilder.navigation import exchange_levels, river_bonus_plan


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


def test_river_conversion_restores_losses_and_cancels_only_new_bonuses():
    result=river_bonus_plan([{'location_tag':'bank','original_levels':'1,3','remaining_levels':'3,5','original_coastal':False,'new_coastal':True}])['bank']
    assert 'river_flowing_through_1' in result
    assert 'river_flowing_through_3' not in result
    assert 'pp_nav_cancel_river_5' in result
    assert 'pp_nav_cancel_mouth_3' in result
    assert 'pp_nav_cancel_mouth_5' in result
    assert 'pp_nav_original_level_1' in result
    assert 'pp_nav_original_level_5' not in result


def test_original_coastal_river_bonus_is_restored():
    result=river_bonus_plan([{'location_tag':'bank','original_levels':'5','remaining_levels':None,'original_coastal':True,'new_coastal':True}])['bank']
    assert 'river_flowing_through_5' in result
    assert 'river_flowing_through_coast_5' in result
    assert not any('cancel' in k for k in result)


def test_compensation_negates_effects_but_not_metadata(tmp_path):
    from prosper_or_perish_constructor.worldbuilder.navigation import write_bonus_compensation
    from prosper_or_perish_constructor.worldbuilder.modifiers import RIVER_MODIFIERS_PATH
    mod=tmp_path/'mod';vanilla=tmp_path/'vanilla'
    river=mod/RIVER_MODIFIERS_PATH;river.parent.mkdir(parents=True)
    river.write_text('\n'.join(f'TRY_REPLACE:river_flowing_through_{n} = {{\n game_data = {{\n category = location\n }}\n local_supply_limit_modifier = 0.1\n local_wine_output_modifier = -0.08\n}}' for n in range(1,6)))
    coast=vanilla/'game/main_menu/common/static_modifiers/location.txt';coast.parent.mkdir(parents=True)
    coast.write_text('\n'.join(f'river_flowing_through_coast_{n} = {{\n game_data = {{\n category = location\n }}\n natural_harbor_suitability = 0.25\n}}' for n in range(1,6)))
    (mod/'main_menu/localization/english').mkdir(parents=True)
    write_bonus_compensation({'river_changes':[]},mod,vanilla)
    text=(mod/'main_menu/common/static_modifiers/pp_navigation_preservation.txt').read_text()
    assert text.count('local_supply_limit_modifier = -0.1')==5
    assert text.count('local_wine_output_modifier = 0.08')==5
    assert text.count('natural_harbor_suitability = -0.25')==5
    assert 'category = -' not in text
