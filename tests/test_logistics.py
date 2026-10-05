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
network_output = 0.30
bulky_goods = ["stone", "iron"]
bulky_half_goods = ["lumber"]
flavour = { local_supply_limit_modifier = 0.05 }

[logistics.classes]
overland = { output = 1.30, bulky_cut = 0.010, increase_per_level_cost = 0.25 }

[logistics.network]
inn = { slot = "Road Network", method = "Carrier Network", desc = "Regular carriers call at the inn, so some traffic keeps moving." }
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
  production_method_slots:
    - name: slot_0
      methods:
        - pp_inn_horses
        - pp_inn_carts
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
    inn_slot_0: Inn Crews
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
    for name, output in (("pp_inn_horses", "3.9"), ("pp_inn_carts", "4.05")):  # the last method is the improved one
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


def _unique_blocks(body: str) -> list[str]:
    return re.findall(r"(?ms)^unique_production_methods = \{\n(.*?)\n\}", body)


def test_apply_adds_an_input_less_network_slot_first(repo: Path) -> None:
    result = lg.apply(repo, repo / "constructor.toml", PRICES)
    assert result.problems == []
    data = yaml_io.safe_load((repo / lg.BLUEPRINT_ROOT_RELATIVE / "buildings/inn.yml").read_text(encoding="utf-8"))
    body = data["building"]["body"]
    blocks = _unique_blocks(body)
    assert len(blocks) == 2
    # slot 0: the network method alone, no goods inputs at all (no manual labour either)
    assert [line.strip() for line in blocks[0].split("\n")] == [
        "pp_inn_logistics_network = {", "produced = logistics", "output = 0.3", "category = building_maintenance", "}",
    ]
    assert "pp_inn_horses" in blocks[1] and "pp_inn_carts" in blocks[1]
    assert data["building"]["production_method_slots"] == [
        {"name": "slot_0", "methods": ["pp_inn_logistics_network"]},
        {"name": "slot_1", "methods": ["pp_inn_horses", "pp_inn_carts"]},
    ]
    entries = data["localization"]["entries"]
    assert entries["inn_slot_0"] == "Road Network"
    assert entries["inn_slot_1"] == "Inn Crews"  # the main slot keeps its label
    assert entries["pp_inn_logistics_network"] == "Carrier Network"
    assert entries["pp_inn_logistics_network_desc"].startswith("Regular carriers")
    network = next(p for p in result.plans).network
    assert network is not None and network.cost == 0 and network.output == 0.3
    assert not lg.apply(repo, repo / "constructor.toml", PRICES, write=False).changed


def test_apply_repairs_a_supplied_or_misplaced_network_slot(repo: Path) -> None:
    lg.apply(repo, repo / "constructor.toml", PRICES)
    path = repo / lg.BLUEPRINT_ROOT_RELATIVE / "buildings/inn.yml"
    good = path.read_text(encoding="utf-8")
    body = yaml_io.safe_load(good)["building"]["body"]
    network, main = re.findall(r"(?ms)^unique_production_methods = \{\n.*?\n\}", body)
    swapped = body.replace(network + "\n" + main, main + "\n" + network.replace("produced = logistics", "manual_labor = 0.2\n    produced = logistics"))
    assert swapped != body
    labels = "    inn_slot_0: Road Network\n    inn_slot_1: Inn Crews\n"
    assert labels in good
    moved = good.replace(_indent_body(body), _indent_body(swapped)).replace(
        labels, "    inn_slot_0: Inn Crews\n    inn_slot_1: Road Network\n"  # the labels follow their slots
    )
    path.write_text(moved, encoding="utf-8")
    result = lg.apply(repo, repo / "constructor.toml", PRICES, write=False)
    assert [p.building for p in result.changed] == ["inn"]
    lg.apply(repo, repo / "constructor.toml", PRICES)
    assert path.read_text(encoding="utf-8") == good


def _indent_body(body: str) -> str:
    return "\n".join(("    " + line) if line.strip() else "" for line in body.split("\n"))


def test_a_building_without_network_names_is_a_problem(repo: Path) -> None:
    config = repo / "constructor.toml"
    config.write_text(CONFIG.split("[logistics.network]")[0], encoding="utf-8")
    result = lg.apply(repo, config, PRICES, write=False)
    assert any("network" in p for p in result.problems)


def test_every_logistics_blueprint_is_on_its_class() -> None:
    result = lg.apply(ROOT, ROOT / "constructor.toml", write=False)
    assert result.problems == []
    assert [p.blueprint.name for p in result.changed] == []
    assert {p.building for p in result.plans} == {
        "river_boatmen_yard", "coastal_shipping_office", "carrier_inn", "transport_office", *VARIANTS,
    }


def test_every_logistics_building_has_exactly_one_input_less_network_slot() -> None:
    config = lg.load_config(ROOT / "constructor.toml")
    for plan in lg.apply(ROOT, ROOT / "constructor.toml", write=False).plans:
        body = yaml_io.safe_load(plan.blueprint.read_text(encoding="utf-8"))["building"]["body"]
        network = lg.network_method_name(plan.building)
        blocks = _unique_blocks(body)
        assert len(blocks) == 2, plan.building
        holders = [block for block in blocks if any(lg.is_network_method(n) for n in re.findall(r"(?m)^\s*(\w+) = \{", block))]
        assert holders == [blocks[0]], plan.building
        method = _method(body, network)
        assert method == {"produced": "logistics", "output": lg.format_amount(config.network_output), "category": "building_maintenance"}
        # the main slot always buys goods, so the network slot is the only one that never starves
        assert all(m.cost == pytest.approx(config.input_cost, abs=lg.COST_TOLERANCE) for m in plan.methods)


def test_the_labour_pass_leaves_the_network_method_without_labour() -> None:
    from prosper_or_perish_constructor import production_labour

    result = production_labour.apply(ROOT, ROOT / "constructor.toml", write=False)
    assert not [p for p in result.plans if lg.is_network_method(p.method.name)]
    assert not [p for p in result.problems if "logistics_network" in p]


def test_the_gate_stays_on_the_main_slot_after_the_network_slot() -> None:
    from prosper_or_perish_constructor import production_gate as gate

    for building in ("carrier_inn", "river_boatmen_yard", *VARIANTS):
        data = yaml_io.safe_load((ROOT / "blueprints/accepted/buildings" / f"{building}.yml").read_text(encoding="utf-8"))
        slots, has_possible = gate.body_slots(data["building"]["body"])
        assert gate.gate_problems(slots, data[gate.FLAG], has_possible) == []
        assert not lg.is_network_method(data[gate.FLAG])
        assert [m.name for m in slots[0].methods] == [lg.network_method_name(building)]


def test_the_rendered_network_method_has_no_inputs() -> None:
    text = "\n".join(p.read_text(encoding="utf-8-sig") for p in (MOD_ROOT / "in_game/common/building_types").glob("*.txt"))
    for building in ("river_boatmen_yard", "coastal_shipping_office", "carrier_inn", "transport_office", *VARIANTS):
        network = lg.network_method_name(building)
        found = re.findall(rf"(?ms)^\s*{network} = \{{\n(.*?)\n\s*\}}", text)
        assert len(found) == 1, network
        keys = sorted(line.split("=")[0].strip() for line in found[0].split("\n") if line.strip())
        # EU5 1.4 method icons (icon_type/icon, written by the finalize step) are display keys, not inputs
        assert [key for key in keys if key not in {"icon_type", "icon"}] == ["category", "output", "produced"]


# ---------------------------------------------------------------- AI urgency

URGENCY = '\n[project]\nmod_root = "mod"\n' + CONFIG.replace(
    "network_output = 0.30\n", "network_output = 0.30\nurgency_per_level = 2.0\nurgency_levels_cap = 60\nurgency_level_step = 5\n"
)


def test_apply_writes_the_urgency_weight_and_its_script_value(repo: Path) -> None:
    (repo / "constructor.toml").write_text(URGENCY, encoding="utf-8")
    result = lg.apply(repo, repo / "constructor.toml", PRICES)
    assert result.problems == [] and not result.urgency_stale
    assert _block(_body(repo), "ai_construct_weight") == [
        "# heavily built locations at low market access first (flat, ppc logistics)",
        f"value = {lg.URGENCY_VALUE}",
    ]
    text = (repo / "mod" / lg.URGENCY_RELATIVE).read_text(encoding="utf-8")
    assert text.startswith("﻿")
    assert text.count("total_building_levels >=") == 12  # 5, 10, ... 60
    assert "multiply = { value = 0.85 subtract = market_access min = 0 divide = 0.85 }" in text
    again = lg.apply(repo, repo / "constructor.toml", PRICES, write=False)
    assert not again.changed and not again.urgency_stale
    (repo / "mod" / lg.URGENCY_RELATIVE).write_text("edited by hand", encoding="utf-8")
    assert lg.apply(repo, repo / "constructor.toml", PRICES, write=False).urgency_stale


def test_no_urgency_weight_without_the_numbers(repo: Path) -> None:
    lg.apply(repo, repo / "constructor.toml", PRICES)
    assert "ai_construct_weight" not in _body(repo)


def test_urgency_weight_grows_with_building_levels_and_the_access_gap() -> None:
    config = lg.load_config(ROOT / "constructor.toml")
    # the 1834 cases of run 4f95382e: Dingbian 70 levels at 0.20, Kurchum 77 at 0.37; a typical 15-level place at 0.75
    assert lg.urgency_weight(config, 70, 0.20) == pytest.approx(91.8, abs=0.1)
    assert lg.urgency_weight(config, 77, 0.37) == pytest.approx(67.8, abs=0.1)
    assert lg.urgency_weight(config, 15, 0.75) == pytest.approx(3.5, abs=0.1)
    assert lg.urgency_weight(config, 200, 0.0) == pytest.approx(120.0)  # the cap; the food urgency peaks at 90
    assert lg.urgency_weight(config, 60, 0.85) == 0.0  # the allow gate's line
    assert lg.urgency_weight(config, 60, 1.10) == 0.0


def test_every_logistics_building_weighs_the_urgency_and_the_value_is_current() -> None:
    result = lg.apply(ROOT, ROOT / "constructor.toml", write=False)
    assert not result.urgency_stale
    for plan in result.plans:
        body = yaml_io.safe_load(plan.blueprint.read_text(encoding="utf-8"))["building"]["body"]
        assert f"value = {lg.URGENCY_VALUE}" in _block(body, "ai_construct_weight"), plan.building


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
    # 2026-10-01: overbuilt locations also pay logistics a little more (a nudge for the AI to build them there)
    assert lines == [
        "game_data = {", "category = location", "}", "local_market_access = -0.01", "local_logistics_output_modifier = 0.001",
    ]


def test_the_scripted_logistics_builder_is_gone() -> None:
    assert not (MOD_ROOT / "in_game/common/scripted_effects/pp_ai_logistics_building_effects.txt").exists()
    assert not (MOD_ROOT / "in_game/events/debug/pp_logistics_debug.txt").exists()
    for path in (MOD_ROOT / "in_game").rglob("*.txt"):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        assert "pp_ai_logistics" not in text, path
    assert "pp_logistics_debug" not in (MOD_ROOT / "main_menu/localization/english/pp_debug_l_english.yml").read_text(encoding="utf-8-sig")
