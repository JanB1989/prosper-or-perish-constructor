from pathlib import Path

MOD = Path(__file__).resolve().parents[1]/'mod/Prosper or Perish (Population Growth & Food Rework)'


def test_documented_starting_navigation_turns_shallows_navigable():
    import polars as pl
    from prosper_or_perish_constructor.worldbuilder.navigation import opened_at_start
    settings={'starting_evidence':[{'id':'documented','bounds':[0,0,10,10]}]}
    attrs=pl.DataFrame({'location_tag':['inside','outside'],'calibrated_lon':[5.0,15.0],'calibrated_lat':[5.0,5.0]})
    tiles={'s1':{'state':'improvable'},'s2':{'state':'improvable'},'n':{'state':'navigable'}}
    shores=[{'location_tag':'inside','water_location':'s1'},{'location_tag':'outside','water_location':'s2'},
            {'location_tag':'inside','water_location':'n'},{'location_tag':'unowned','water_location':'s2'}]
    assert opened_at_start(settings,attrs,tiles,shores)=={'s1'}


def test_shipped_mod_has_no_navigation_roads_and_no_canal():
    """The River Navigation Canal and the hidden water roads were removed 2026-10-13: nothing creates a road onto a
    channel tile and the canal is gone from the blueprints and the mod."""
    root=Path(__file__).resolve().parents[1]
    assert not (MOD/'in_game/common/road_types/pp_navigation.txt').exists()
    assert not (MOD/'in_game/common/scripted_effects/pp_navigation_routes.txt').exists()
    assert not (root/'blueprints/accepted/buildings/river_navigation_canal.yml').exists()
    assert 'river_navigation_canal' not in (root/'blueprints/buildings.manifest.yml').read_text()
    for path in (MOD/'in_game').rglob('*.txt'):
        text=path.read_text(encoding='utf-8-sig',errors='replace')
        assert 'pp_navigation_' not in text or 'add_road_to' not in text, path
        assert 'river_navigation_canal' not in text, path
    start=(MOD/'in_game/common/on_action/pp_navigation.txt').read_text(encoding='utf-8-sig')
    assert 'pp_navigation_seed' not in start and 'pp_navigation_map_refresh' not in start


def test_native_pixel_preservation_never_stacks_scripted_bonuses(tmp_path):
    from prosper_or_perish_constructor.worldbuilder.navigation import write_bonus_compensation
    (tmp_path/'main_menu/common/static_modifiers').mkdir(parents=True)
    (tmp_path/'main_menu/localization/english').mkdir(parents=True)
    stale=tmp_path/'main_menu/common/static_modifiers/pp_navigation_preservation.txt'
    stale.write_text('pp_river_canal_open = {}\n')
    assert write_bonus_compensation({'manifest':{'river_preservation':'native_bank_pixel'},'settings':{}},tmp_path,tmp_path)=={}
    assert not stale.exists()


def test_river_port_modifier_goes_to_land_whose_port_faces_a_channel(tmp_path):
    from prosper_or_perish_constructor.worldbuilder.navigation import RIVER_PORT, write_bonus_compensation
    for rel in ('main_menu/common/static_modifiers','main_menu/localization/english','in_game/map_data'):
        (tmp_path/rel).mkdir(parents=True)
    (tmp_path/'in_game/map_data/ports.csv').write_text('LandProvince;SeaZone;x;y;\nbank;n1;1;1;x\ncoast;some_sea;2;2;x\n')
    settings={'modifiers':{'river_port':{'port_cost':-0.5,'name':'P','description':'p'}}}
    state={'manifest':{'river_preservation':'native_bank_pixel'},'settings':settings,
           'tiles':{'n1':{'state':'navigable'},'n2':{'state':'navigable'},'s1':{'state':'difficult'}},
           'edges':[{'from':'n1','to':'n2','cost_profile':'navigable'},{'from':'n2','to':'s1','cost_profile':'difficult'}]}
    assert write_bonus_compensation(state,tmp_path,tmp_path)=={'bank':[RIVER_PORT]}
    text=(tmp_path/'main_menu/common/static_modifiers/pp_navigation_modifiers.txt').read_text(encoding='utf-8-sig')
    assert 'local_port_cost_distance_impact = -0.5' in text and 'speed_propagation' not in text


def test_channel_kinds_two_passable_types_plus_falls(tmp_path):
    """Shallows and the navigable tiles of difficult routes are Difficult Waterway; documented starting navigation
    (Grand Canal) opens Shallows to Navigable River; Falls stay."""
    import polars as pl
    from types import SimpleNamespace
    from prosper_or_perish_constructor.worldbuilder.navigation import channel_tiles
    nav=tmp_path/'navigation';nav.mkdir()
    pl.DataFrame({'location':['n','r','s','g','f'],'state':['navigable','navigable','improvable','improvable','barrier']}).write_csv(nav/'tiles.csv')
    pl.DataFrame({'location_tag':['bank'],'water_location':['g'],'state':['improvable'],'shore_pixels':[5]}).write_csv(nav/'shores.csv')
    pl.DataFrame({'from':['n','r'],'to':['r','s'],'state':['navigable','improvable'],'cost_profile':['navigable','difficult'],
                  'shore':[False,False]}).write_csv(nav/'edges.csv')
    attrs=pl.DataFrame({'location_tag':['bank'],'calibrated_lon':[5.0],'calibrated_lat':[5.0]})
    contract=SimpleNamespace(root=tmp_path,location_attributes=attrs)
    tiles,_,opened=channel_tiles({'starting_evidence':[{'id':'x','bounds':[0,0,10,10]}]},contract)
    assert {t:v['state'] for t,v in tiles.items()}=={'n':'navigable','r':'difficult','s':'difficult','g':'navigable','f':'barrier'}
    assert opened=={'g'}


def test_shipped_channel_topographies_carry_proximity_efficiency():
    """A channel step costs a sea step divided by 1 + the efficiency of the tile left (EU5 1.4, verified in game
    2026-10-13): Navigable River +1.5 (a vanilla river leg on land), Difficult Waterway +0.75, Falls none."""
    text=(MOD/'in_game/common/topography/pp_river_topography.txt').read_text(encoding='utf-8-sig')
    block=lambda k:text.split(f'{k} = {{',1)[1].split('\n}',1)[0]
    assert 'local_distance_from_capital_speed_propagation = 1.5' in block('pp_river_channel')
    assert 'local_distance_from_capital_speed_propagation = 0.75' in block('pp_river_difficult')
    assert 'pp_river_shallows' not in text
    assert 'local_distance_from_capital_speed_propagation' not in block('pp_river_falls')


def test_legacy_compensation_contract_requires_rebuild(tmp_path):
    import pytest
    from prosper_or_perish_constructor.worldbuilder.navigation import write_bonus_compensation
    with pytest.raises(ValueError,match='Rebuild World Builder'):
        write_bonus_compensation({'manifest':{}},tmp_path,tmp_path)


def test_map_mode_emits_only_documented_refresh_counters_and_native_levels(tmp_path):
    from prosper_or_perish_constructor.worldbuilder.navigation_map_modes import write_map_modes
    write_map_modes(tmp_path,{'tiles':{'water':{'state':'difficult'}},'edges':[{'from':'water','to':'bank','shore':True,'state':'improvable'}]})
    text=(tmp_path/'in_game/gfx/map/map_modes/pp_navigable_rivers.txt').read_text()
    assert 'LocationRoadsChanged' in text
    assert 'LocationBuildingChanged' not in text
    assert 'pp_navigation_has_river = yes' in text
    assert 'is_port = yes' in text

    loc=(tmp_path/'main_menu/localization/english/pp_navigable_rivers_map_l_english.yml').read_text()
    assert chr(92)*2+'n' not in loc and 'Canal' not in loc

    # the map state is seeded once: no canal state, no refresh effects
    effects=(tmp_path/'in_game/common/scripted_effects/pp_navigation_map.txt').read_text()
    assert 'location:water = { set_variable = { name = pp_navigation_map_state value = 5 }' in effects
    assert 'has_road_of_type_to' not in effects and 'pp_navigation_map_refresh' not in effects
    assert 'value = 4' not in effects and 'value = 6' not in effects


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


def test_route_validation_rejects_duplicate_undirected_edges():
    import pytest
    from prosper_or_perish_constructor.worldbuilder.navigation import validate_routes
    tiles={'water':{'state':'navigable'},'falls':{'state':'barrier'}}
    edge={'from':'water','to':'falls','state':'barrier','shore':False}
    validate_routes(tiles,[edge])
    with pytest.raises(ValueError,match='Duplicate'):
        validate_routes(tiles,[edge,{**edge,'from':'falls','to':'water'}])
    with pytest.raises(ValueError,match='Unknown navigation source'):
        validate_routes(tiles,[{**edge,'from':'ocean'}])


def test_map_mode_shows_difficult_waterway_tiles(tmp_path):
    from prosper_or_perish_constructor.worldbuilder.navigation_map_modes import write_map_modes
    write_map_modes(tmp_path,{'tiles':{'a':{'state':'difficult'},'b':{'state':'difficult'}},
        'edges':[{'from':'a','to':'b','shore':False,'state':'navigable','cost_profile':'difficult'}]})
    effects=(tmp_path/'in_game/common/scripted_effects/pp_navigation_map.txt').read_text()
    assert 'location:a = { set_variable = { name = pp_navigation_map_state value = 5 }' in effects
    assert 'location:b = { set_variable = { name = pp_navigation_map_state value = 5 }' in effects
    loc=(tmp_path/'main_menu/localization/english/pp_navigable_rivers_map_l_english.yml').read_text()
    assert 'PP_NAVMAP_DIFFICULT_OPEN_TT' in loc and 'PP_NAVMAP_DIFFICULT_INLAND_TT' in loc


def test_navigable_rivers_map_mode_ships_for_players():
    """The shipped map mode: in Geography beside vanilla's Rivers (no index = Rivers' group), its own icon, the concept
    of the same key points at it, every tooltip and legend key has a text, the old debug view is gone, and the cut-off
    waterways are striped."""
    import re
    from PIL import Image
    from prosper_or_perish_constructor.worldbuilder.navigation_map_modes import MAP_MODE
    text=(MOD/f'in_game/gfx/map/map_modes/{MAP_MODE}.txt').read_text(encoding='utf-8-sig')
    assert text.count('{')==text.count('}')
    assert 'category = geography' in text and 'index =' not in text
    assert 'secondary_map_color = {' in text and 'var:pp_navigation_ocean_connected = 1' in text
    loc=(MOD/f'main_menu/localization/english/{MAP_MODE}_map_l_english.yml').read_text(encoding='utf-8-sig')
    keys=set(re.findall(r'value = (PP_NAVMAP_\w+)',text))|set(re.findall(r'desc = "(PP_NAVMAP_\w+)"',text))
    assert len(keys)>15 and not sorted(k for k in keys if f' {k}:' not in loc)
    assert f'mapmode_{MAP_MODE}_name:' in loc and f'MAPMODE_{MAP_MODE.upper()}:' in loc
    with Image.open(MOD/f'main_menu/gfx/interface/icons/map_modes/{MAP_MODE}.dds') as icon:
        assert icon.size==(128,128)
    concept=(MOD/f'main_menu/common/game_concepts/{MAP_MODE}.txt').read_text(encoding='utf-8-sig')
    assert f'texture = "map_modes/{MAP_MODE}"' in concept
    assert not (MOD/'in_game/gfx/map/map_modes/pp_river_navigation.txt').exists()


def test_touching_channel_tiles_get_different_shades(tmp_path):
    from prosper_or_perish_constructor.worldbuilder.navigation_map_modes import shades, write_map_modes
    # a confluence: c touches a, b and d; a bank edge never counts
    tiles = {t: {"state": "navigable"} for t in "abcd"}
    edges = [{"from": x, "to": y, "shore": False} for x, y in ("ca", "cb", "cd", "ab")] + [{"from": "a", "to": "land", "shore": True, "state": "navigable"}]
    shade = shades({"tiles": tiles, "edges": edges})
    assert all(shade[x] != shade[y] for x, y in ("ca", "cb", "cd", "ab")) and set(shade.values()) <= {1, 2, 3, 4}
    write_map_modes(tmp_path, {"tiles": tiles, "edges": edges})
    text = (tmp_path / "in_game/gfx/map/map_modes/pp_navigable_rivers.txt").read_text()
    assert "var:pp_navigation_map_shade = 2 } value = rgb { 0 40 120 }" in text
    effects = (tmp_path / "in_game/common/scripted_effects/pp_navigation_map.txt").read_text()
    c = shade.get("c")
    assert f"location:c = {{ set_variable = {{ name = pp_navigation_map_state value = 1 }} set_variable = {{ name = pp_navigation_map_shade value = {c} }}" in effects
