from dataclasses import replace
from pathlib import Path

import polars as pl
import pytest

from prosper_or_perish_constructor.worldbuilder import buildings as b
from prosper_or_perish_constructor.worldbuilder.contract import load_config
from prosper_or_perish_constructor.worldbuilder.start_placement import Pop, dominant_cultures
from test_worldbuilder_stage import _contract, _cfg
from prosper_or_perish_constructor import yaml_io


ROOT = Path(__file__).resolve().parents[1]


def test_jiangnan_scope_uses_region_culture_terrain_and_water():
    cfg = load_config(ROOT, ROOT / 'constructor.toml')
    canal = cfg.niche['jiangnan_canal_network']['gate']
    terrace = cfg.niche['jiangnan_hill_terraces']['gate']
    delta = dict(culture='wu_culture', province='jiaxing_province', climate='subtropical',
                 topography='deltas', river_level='3', is_coastal='false', is_adjacent_to_lake='true')
    assert b.gate_matches(canal, delta)
    for field, value in [('culture', 'english'), ('province', 'cairo_province'),
                         ('climate', 'arid'), ('topography', 'hills')]:
        assert not b.gate_matches(canal, {**delta, field: value})
    dry = {**delta, 'river_level': '0', 'is_adjacent_to_lake': 'false'}
    assert not b.gate_matches(canal, dry)
    assert b.gate_matches(canal, {**dry, 'is_coastal': True})
    hill = {**delta, 'province': 'hangzhou_province', 'culture': 'yue_wu_culture', 'topography': 'hills'}
    assert b.gate_matches(terrace, hill)
    assert b.gate_matches(terrace, {**hill, 'province': 'jinhua_province', 'culture': 'wuzhou_culture', 'topography': 'mountains'})
    assert not b.gate_matches(terrace, delta)


def test_starting_niche_replaces_family_and_never_exceeds_shared_cap(tmp_path):
    c = _contract(tmp_path)
    cfg = _cfg(tmp_path, {'regional': {'family': 'land_clearance', 'strength': 1.5,
                                      'place_at_start': True, 'gate': [{'culture': ['local']} ]}})
    caps = b.write_caps(c, cfg, tmp_path)
    out = b.write_setup(c, cfg, caps, {'a': 'SWE', 'b': 'SWE'}, tmp_path,
                        demand={'a': 1000000, 'b': 1000000}, cultures={'a': 'local', 'b': 'other'})
    text = (tmp_path / b.SETUP_PATH).read_text(encoding='utf-8-sig')
    assert 'regional = { tag = SWE level = 3 location = a }' in text
    assert 'land_clearance = { tag = SWE level = 5 location = b }' in text
    assert 'land_clearance = { tag = SWE level = 3 location = a }' not in text
    assert 'regional = { tag = SWE level = 5 location = b }' not in text
    assert out['locations_still_short'] == 2
    # Culture alone cannot bypass the family's own geography gate.
    c = replace(c, location_attributes=c.location_attributes.with_columns(pl.lit('polar').alias('climate')))
    b.write_setup(c, cfg, caps, {'a': 'SWE'}, tmp_path, cultures={'a': 'local'})
    assert 'regional =' not in (tmp_path / b.SETUP_PATH).read_text(encoding='utf-8-sig')


def test_setup_rejects_uninterpreted_locks(tmp_path):
    c = _contract(tmp_path)
    cfg = _cfg(tmp_path, {'regional': {'family': 'land_clearance', 'strength': 1.5,
                                      'place_at_start': True, 'lock': ['always = no']}})
    caps = b.write_caps(c, cfg, tmp_path)
    with pytest.raises(ValueError, match='structured gate'):
        b.write_setup(c, cfg, caps, {'a': 'SWE'}, tmp_path)


def test_dominant_culture_aggregates_all_pop_types():
    assert dominant_cultures({'a': [Pop('nobles', 0.004, 'foreign', ''),
                                    Pop('peasants', 5, 'local', ''), Pop('burghers', 4, 'local', ''),
                                    Pop('peasants', 8, 'other', '')]}) == {'a': 'local'}


def test_capacity_check_counts_regional_levels(tmp_path, monkeypatch):
    from prosper_or_perish_constructor.worldbuilder import stage

    c = _contract(tmp_path)
    cfg = _cfg(tmp_path, {'regional': {'family': 'land_clearance', 'strength': 1.5}})
    monkeypatch.setattr(stage, 'load_config', lambda *_: cfg)
    monkeypatch.setattr(stage, 'load_contract', lambda *_: c)
    target = tmp_path / b.SETUP_PATH
    target.parent.mkdir(parents=True)
    target.write_text('building_manager = {\n regional = { tag = SWE level = 3 location = a }\n}\n')
    result = stage.check(tmp_path, tmp_path / 'constructor.toml', tmp_path)
    assert result['total_model'] == pytest.approx((11000 + 3 * 7800) * 1.2 + 22400 * 1.4)


def test_new_niches_are_complete_buildings_with_upkeep_and_owned_icons(tmp_path):
    cfg = load_config(ROOT, ROOT / 'constructor.toml')
    for key in ('jiangnan_canal_network', 'jiangnan_hill_terraces'):
        data = yaml_io.safe_load((ROOT / b.BLUEPRINTS / f'{key}.yml').read_text())
        assert data['building']['mode'] == 'CREATE'
        assert data['footprint'] == 'capacity_source'
        assert 'manual_labor = 0.1' in data['building']['body']
        assert 'employment_size = 0.075' in data['building']['body']
        assert cfg.niche[key]['strength'] == {'jiangnan_canal_network': 2.5, 'jiangnan_hill_terraces': 3.0}[key]
        assert (ROOT / b.BLUEPRINTS / data['icon']['source_png']).resolve().is_file()
