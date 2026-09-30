from __future__ import annotations

from collections import Counter
from pathlib import Path
import re

import pytest

from prosper_or_perish_constructor import logistics as lg
from prosper_or_perish_constructor import yaml_io

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
VARIANTS = {
    "pp_caravanserai": "pp_logistics_zone_caravan",
    "pp_oasis_caravan_station": "pp_logistics_zone_oasis",
    "pp_yam_station": "pp_logistics_zone_yam",
    "pp_banjara_tanda": "pp_logistics_zone_banjara",
    "pp_llama_caravan_post": "pp_logistics_zone_llama",
}

CONFIG = """
[logistics]
good = "logistics"
input_cost = 3.0
market_access = 0.10
gate_max_market_access = 0.85
gate_min_building_levels = 15
improved_method_bonus = 0.05
bulky_goods = ["stone", "iron"]
bulky_half_goods = ["lumber"]
flavour = { local_supply_limit_modifier = 0.05 }

[logistics.classes]
overland = { output = 1.18, bulky_cut = 0.010, increase_per_level_cost = 0.25 }
"""

PRICES = {"manual_labor": 1.0, "victuals": 3.0, "horses": 3.0, "lumber": 1.75, "stone": 1.0, "iron": 3.5, "logistics": 1.0}

INN = """version: 2
tag: inn
labour:
  class: logistics
logistics:
  class: overland
  bulky_scale: 1.5
building:
  key: inn
  mode: CREATE
  body: |2-
    max_levels = 100
    increase_per_level_cost = 0.30
    pop_type = peasants
    employment_size = 3
    location_potential = {
      num_roads > 0
    }
    allow = {
      development >= 5
      market_access < 0.5
    }
    unique_production_methods = {
      pp_inn_horses = {
        victuals = 0.30 # rations
        horses = 0.15
        manual_labor = 0.74
        category = building_maintenance
      }
      pp_inn_carts = {
        victuals = 0.25
        lumber = 0.20
        manual_labor = 0.56
        category = building_maintenance
      }
    }

    raw_modifier = {
      free_building_levels = 10
    }
localization:
  entries:
    inn: Inn
"""


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "constructor.toml").write_text(CONFIG, encoding="utf-8")
    folder = tmp_path / lg.BLUEPRINT_ROOT_RELATIVE / "buildings"
    folder.mkdir(parents=True)
    (folder / "inn.yml").write_text(INN, encoding="utf-8")
    (tmp_path / lg.MANIFEST_RELATIVE).write_text("enabled:\n  buildings/inn.yml: true\n", encoding="utf-8")
    return tmp_path


def _body(repo: Path) -> str:
    data = yaml_io.safe_load((repo / lg.BLUEPRINT_ROOT_RELATIVE / "buildings/inn.yml").read_text(encoding="utf-8"))
    return data["building"]["body"]


def _block(body: str, key: str) -> list[str]:
    match = re.search(rf"(?m)^{key} = \{{\n(?P<inner>.*?)\n\}}", body, re.S)
    assert match is not None, key
    return [line.strip() for line in match.group("inner").split("\n") if line.strip()]


def _method(body: str, name: str) -> dict[str, str]:
    match = re.search(rf"{name} = \{{\n(?P<inner>.*?)\n\s*\}}", body, re.S)
    assert match is not None, name
    return dict(re.findall(r"^\s*(\w+) = ([^\s#]+)", match.group("inner"), re.M))


def test_apply_scales_every_method_to_the_input_cost_and_sets_the_output(repo: Path) -> None:
    result = lg.apply(repo, repo / "constructor.toml", PRICES)
    assert result.problems == []
    body = _body(repo)
    for name, output in (("pp_inn_horses", "3.54"), ("pp_inn_carts", "3.69")):  # the last method is the improved one
        method = _method(body, name)
        cost = sum(float(v) * PRICES[g] for g, v in method.items() if g in PRICES)
        assert cost == pytest.approx(3.0, abs=lg.COST_TOLERANCE)
        assert method["produced"] == "logistics"
        assert method["output"] == output
        assert method["category"] == "building_maintenance"
    horses = _method(body, "pp_inn_horses")
    # each good keeps its share of the cost: victuals twice the horses
    assert float(horses["victuals"]) == pytest.approx(2 * float(horses["horses"]), abs=0.011)
    assert "victuals = 0.43 # rations" in body  # comments survive


def test_apply_sets_market_access_gates_bulky_cuts_and_scalars(repo: Path) -> None:
    lg.apply(repo, repo / "constructor.toml", PRICES)
    body = _body(repo)
    assert _block(body, "raw_modifier") == ["local_market_access = 0.1"]  # the old free building levels are gone
    assert _block(body, "modifier") == [
        "local_stone_output_modifier = -0.015",  # class cut 0.01 x bulky_scale 1.5
        "local_iron_output_modifier = -0.015",
        "local_lumber_output_modifier = -0.0075",  # half
        "local_supply_limit_modifier = 0.05",
    ]
    # the building's own allow conditions stay, the logistics gates replace older ones
    assert _block(body, "allow") == ["development >= 5", "market_access < 0.85", "total_building_levels >= 15"]
    assert "increase_per_level_cost = 0.25" in body
    assert "pop_type = laborers" in body
    assert "employment_size = 1" in body
    assert _block(body, "location_potential") == ["num_roads > 0"]


def test_apply_is_stable(repo: Path) -> None:
    first = lg.apply(repo, repo / "constructor.toml", PRICES)
    assert [p.building for p in first.changed] == ["inn"]
    text = (repo / lg.BLUEPRINT_ROOT_RELATIVE / "buildings/inn.yml").read_text(encoding="utf-8")
    assert not lg.apply(repo, repo / "constructor.toml", PRICES, write=False).changed
    assert not lg.apply(repo, repo / "constructor.toml", PRICES).changed
    assert (repo / lg.BLUEPRINT_ROOT_RELATIVE / "buildings/inn.yml").read_text(encoding="utf-8") == text


def test_check_reports_unknown_classes_and_untagged_producers(repo: Path) -> None:
    path = repo / lg.BLUEPRINT_ROOT_RELATIVE / "buildings/inn.yml"
    path.write_text(INN.replace("class: overland", "class: nowhere"), encoding="utf-8")
    result = lg.apply(repo, repo / "constructor.toml", PRICES, write=False)
    assert any("'nowhere' is not in" in p for p in result.problems)
    path.write_text(INN.replace("logistics:\n  class: overland\n  bulky_scale: 1.5\n", "").replace(
        "category = building_maintenance\n      }\n      pp_inn_carts", "produced = logistics\n        category = building_maintenance\n      }\n      pp_inn_carts"
    ), encoding="utf-8")
    result = lg.apply(repo, repo / "constructor.toml", PRICES, write=False)
    assert any("without a logistics tag" in p for p in result.problems)


def test_every_logistics_blueprint_is_on_its_class() -> None:
    result = lg.apply(ROOT, ROOT / "constructor.toml", write=False)
    assert result.problems == []
    assert [p.blueprint.name for p in result.changed] == []
    assert {p.building for p in result.plans} == {
        "river_boatmen_yard", "coastal_shipping_office", "carrier_inn", "transport_office", *VARIANTS,
    }


# ---------------------------------------------------------------- zones


@pytest.fixture(scope="module")
def zones() -> dict[str, list[str]]:
    triggers = lg.load_zone_triggers(MOD_ROOT / lg.ZONE_TRIGGERS_RELATIVE)
    return lg.zone_membership(lg.load_locations(ROOT, ROOT / "constructor.toml"), triggers)


def test_logistics_zones_never_overlap(zones: dict[str, list[str]]) -> None:
    counts = Counter(tag for tags in zones.values() for tag in tags)
    assert [tag for tag, n in counts.items() if n > 1] == []
    assert set(zones) == set(VARIANTS.values())
    sizes = {zone: len(tags) for zone, tags in zones.items()}
    print("logistics zone sizes:", sizes)
    assert all(size > 100 for size in sizes.values()), sizes


def test_zone_any_is_the_union_of_the_zones(zones: dict[str, list[str]]) -> None:
    triggers = lg.load_zone_triggers(MOD_ROOT / lg.ZONE_TRIGGERS_RELATIVE)
    locations = lg.load_locations(ROOT, ROOT / "constructor.toml")
    union = {tag for tags in zones.values() for tag in tags}
    any_zone = {loc.tag for loc in locations if lg.evaluate(triggers[lg.ZONE_ANY], loc, triggers)}
    assert any_zone == union


def test_zones_follow_their_lands(zones: dict[str, list[str]]) -> None:
    locations = {loc.tag: loc for loc in lg.load_locations(ROOT, ROOT / "constructor.toml")}
    llama = [locations[t] for t in zones["pp_logistics_zone_llama"]]
    assert {loc.region for loc in llama} == {"andes_region"}  # no llamas in Mesoamerica
    assert {loc.sub_continent for loc in (locations[t] for t in zones["pp_logistics_zone_banjara"])} == {"south_asia"}
    caravan = Counter(locations[t].region for t in zones["pp_logistics_zone_caravan"])
    for region in ("anatolia_region", "persia_region", "crescent_region", "arabia_region", "khorasan_region", "maghreb_region"):
        assert caravan[region] > 0, region
    oasis = Counter(locations[t].region for t in zones["pp_logistics_zone_oasis"])
    assert oasis["sahel_region"] > 0 and oasis["maghreb_region"] > 0  # the Sahara part of the Maghreb
    yam = Counter(locations[t].region for t in zones["pp_logistics_zone_yam"])
    for region in ("russian_region", "steppes_region", "mongolia_region", "east_siberia_region"):
        assert yam[region] > 0, region


def test_variants_are_gated_by_their_zone_and_the_carrier_inn_by_none() -> None:
    root = ROOT / "blueprints/accepted/buildings"
    for building, zone in VARIANTS.items():
        body = yaml_io.safe_load((root / f"{building}.yml").read_text(encoding="utf-8"))["building"]["body"]
        assert _block(body, "location_potential") == [f"{zone} = yes"]
    inn = yaml_io.safe_load((root / "carrier_inn.yml").read_text(encoding="utf-8"))["building"]["body"]
    assert _block(inn, "location_potential") == ["num_roads > 0", f"NOT = {{ {lg.ZONE_ANY} = yes }}"]


def test_zone_triggers_use_geography_only() -> None:
    text = (MOD_ROOT / lg.ZONE_TRIGGERS_RELATIVE).read_text(encoding="utf-8-sig")
    keys = set(re.findall(r"(?m)^\s*([A-Za-z_]+)\s*=", text))
    # map hierarchy only (2026-09-30): no climate, topography or vegetation, so zones follow whole regions
    allowed = {"OR", "AND", "NOT", "area", "region", "sub_continent", "continent"}
    assert keys - allowed - {k for k in keys if k.startswith(lg.ZONE_PREFIX)} == set()


# ---------------------------------------------------------------- mod files


def test_logistics_good_is_a_pinned_dummy_like_offset() -> None:
    goods = MOD_ROOT / "in_game/common/goods"
    offset = dict(re.findall(r"(?m)^\s*(\w+) = (\S+)", (goods / "pp_goods_offset.txt").read_text(encoding="utf-8-sig")))
    good = dict(re.findall(r"(?m)^\s*(\w+) = (\S+)", (goods / "pp_goods_logistics.txt").read_text(encoding="utf-8-sig")))
    assert {k: v for k, v in good.items() if k not in {"logistics", "color"}} == {
        k: v for k, v in offset.items() if k not in {"offset", "color"}
    }
    assert good["color"] == "goods_logistics"
    types = (MOD_ROOT / "main_menu/common/modifier_type_definitions/pp_logistics_modifier_types.txt").read_text(encoding="utf-8-sig")
    icons = (MOD_ROOT / "main_menu/common/modifier_icons/pp_logistics_modifier_icons.txt").read_text(encoding="utf-8-sig")
    for key in ("local_logistics_output_modifier", "global_logistics_output_modifier"):
        assert f"{key}={{" in types and f"{key} = {{" in icons
    loc = (MOD_ROOT / "main_menu/localization/english/pp_goods_l_english.yml").read_text(encoding="utf-8-sig")
    assert '  logistics: "Logistics"' in loc
    assert not re.search(r"logistics_desc: \"[^\"]*\d", loc)  # no balance numbers


def test_market_access_defines_and_the_overbuilding_penalty() -> None:
    defines = (MOD_ROOT / "loading_screen/common/defines/pp_defines_adjustments.txt").read_text(encoding="utf-8-sig")
    assert re.search(r"(?m)^\s*MARKET_BASE_ACCESS = 1\.3\b", defines)
    modifiers = (MOD_ROOT / "main_menu/common/static_modifiers/pp_location_modifier_adjustments.txt").read_text(encoding="utf-8-sig")
    block = modifiers.split("TRY_REPLACE:unsupported_building_levels = {", 1)[1].split("\n}", 1)[0]
    lines = [line.strip() for line in block.split("\n") if line.strip() and not line.strip().startswith("#")]
    assert lines == ["game_data = {", "category = location", "}", "local_market_access = -0.01"]


def test_the_scripted_logistics_builder_is_gone() -> None:
    assert not (MOD_ROOT / "in_game/common/scripted_effects/pp_ai_logistics_building_effects.txt").exists()
    assert not (MOD_ROOT / "in_game/events/debug/pp_logistics_debug.txt").exists()
    for path in (MOD_ROOT / "in_game").rglob("*.txt"):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        assert "pp_ai_logistics" not in text, path
    assert "pp_logistics_debug" not in (MOD_ROOT / "main_menu/localization/english/pp_debug_l_english.yml").read_text(encoding="utf-8-sig")
