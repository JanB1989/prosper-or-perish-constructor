"""Market membership rules (worldbuilder/markets.py) against in-game values (2026-09-27, pp_mkt_v12, 1338.3.19).

The market tooltip of thisted (Denmark) listed Lübeck 88.94 %, Oslo 88.14 %; the parts are the dumped modifiers.
"""

import pytest

from prosper_or_perish_constructor.worldbuilder import markets as mk

FAMILY = {"scandinavian_language": "germanic_language_family", "german_language": "germanic_language_family",
          "french_language": "romance_language_family"}

LUBECK = mk.Market("lubeck", "lubeck", "LUB", power=0.17974, language="german_language", language_power=0.07327,
                   province="lubeck_province", area="holstein_area")
OSLO = mk.Market("oslo", "oslo", "NOR", power=0.04158, language="scandinavian_language", language_power=0.01604,
                 province="akershus_province", area="ostlandet_area")
THISTED = mk.Place("thisted", "DAN", "vendsyssel_thy_province", "denmark_area", "scandinavian_language",
                   "scandinavian_language", protection=0.0945, market="lubeck")


def test_tooltip_values():
    assert mk.attraction(THISTED, LUBECK, 0.77692, FAMILY) == pytest.approx(0.8894, abs=1e-4)
    assert mk.attraction(THISTED, OSLO, 0.83274, FAMILY) == pytest.approx(0.8814, abs=1e-4)


def test_argmax_and_ties():
    access = {"thisted": {"lubeck": 0.77692, "oslo": 0.83274}}
    assert mk.assign([THISTED], {"lubeck": LUBECK, "oslo": OSLO}, access, FAMILY) == {"thisted": "lubeck"}
    # one more point of control (protection) is irrelevant: both markets are foreign
    more = mk.Place(**{**THISTED.__dict__, "protection": 0.5})
    assert mk.assign([more], {"lubeck": LUBECK, "oslo": OSLO}, access, FAMILY) == {"thisted": "lubeck"}


def test_geography_does_not_stack_and_protection_spares_own_and_overlord():
    home = mk.Place("norrtalje", "SWE", "uppland_province", "svealand_area", "scandinavian_language",
                    "scandinavian_language", protection=0.2999)
    stockholm = mk.Market("stockholm", "stockholm", "SWE", 0.04648, "scandinavian_language", 0.01604,
                          "uppland_province", "svealand_area")
    t = mk.terms(home, stockholm, 0.92661, FAMILY)
    assert t["geography"] == 0.2 and t["protection"] == 0.0
    assert sum(t.values()) == pytest.approx(1.2747, abs=1e-4)          # saved 1.27451
    vassal = mk.Place("bitov", "MVA", "p", "a", None, None, protection=0.09461, overlords=frozenset({"BOH"}))
    boh = mk.Market("prague", "prague", "BOH", 0.1, None)
    assert mk.terms(vassal, boh, 0.5, FAMILY)["protection"] == 0.0
    assert mk.terms(vassal, mk.Market("x", "x", "HUN", 0.1, None), 0.5, FAMILY)["protection"] == -0.09461


def test_unowned_has_no_country_language_or_protection():
    wild = mk.Place("rana", None, "p", "a", "scandinavian_language", None, protection=0.3)
    t = mk.terms(wild, OSLO, 0.2, FAMILY)
    assert t["country_language"] == 0.0 and t["protection"] == 0.0 and t["location_language"] == 0.05


def test_food_sim_engine_markets(tmp_path):
    from prosper_or_perish_constructor.worldbuilder import food_sim as fs

    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "start_markets.csv").write_text(
        "# header\nowner,province,market\nDAN,vendsyssel_thy_province,lubeck\n", encoding="utf-8")
    base = dict(pop0=10.0, tribesmen=0.0, demand0=1.0, workers0=5.0, jobs0=2.0, yield_=1.0, flat_food=0.0,
                provision_food=0.0, serve_food=0.0, cookshop_levels=0.0, taverns=0.0, yards=0.0, capacity=10.0,
                start_food=5.0, victuals_demand=0.0)
    pools = [fs.Pool(owner="DAN", province="vendsyssel_thy_province", catchment="oslo", **base),
             fs.Pool(owner="DAN", province="jutland_province", catchment="oslo", **base),
             fs.Pool(owner=fs.UNOWNED, province="vendsyssel_thy_province", catchment=fs.UNOWNED, **base)]
    assert fs.engine_markets(tmp_path, pools) == 1
    assert [p.catchment for p in pools] == ["lubeck", "oslo", fs.UNOWNED]
