from __future__ import annotations

from pathlib import Path

import pytest

from prosper_or_perish_constructor import production_gate as pg
from prosper_or_perish_constructor import yaml_io

ROOT = Path(__file__).resolve().parents[1]

CONFIG = """
[production_gate]
threshold = 1.2
dynamic_goods = ["province_food_sales"]

[blueprint_evaluation]
base_method_input_goods = ["manual_labor"]

[blueprint_evaluation.price_overrides]
manual_labor = 1.0
"""

PRICES = {"manual_labor": 1.0, "victuals": 3.0, "pottery": 1.0, "steel": 4.0, "offset": 1.0, "province_food_sales": 1.0, "wheat": 1.0, "livestock": 1.5}

GRANGE = """version: 2
tag: grange
footprint: trade
labour:
  class: keep
building:
  key: grange
  mode: CREATE
  production_method_slots:
    - name: slot_0
      methods:
        - pp_grange_porters
        - pp_grange_ox_carts
    - name: slot_1
      methods:
        - pp_grange_surplus_sales
    - name: slot_2
      methods:
        - pp_grange_loose_stores
        - pp_grange_tin_cans
        - pp_grange_pottery_jars
  possible_production_methods: []
  body: |2-
    pop_type = nobles
    # slot 0: how the store reaches the market
    unique_production_methods = {
      pp_grange_porters = {
        produced = victuals
        manual_labor = 0.2
        output = 1.5
      }
      pp_grange_ox_carts = { livestock = 0.04 manual_labor = 0.1 produced = victuals output = 1.5 }
    }
    # slot 1: surplus sales, the storage leg
    unique_production_methods = {
      pp_grange_surplus_sales = {
        produced = province_food_sales
        offset = 30.52
        output = 2.0
      }
    }
    # slot 2: packing goods
    unique_production_methods = {
      pp_grange_loose_stores = {
        category = building_maintenance
      }
      pp_grange_tin_cans = { steel = 0.26 produced = victuals output = 0.5 }
      # jars: the cheap packing
      pp_grange_pottery_jars = {
        pottery = 0.65
        produced = victuals
        output = 0.25
      }
    }

    modifier = {
      local_monthly_food = -60.0
    }
localization:
  entries:
    grange: Grange
    grange_slot_0: Haulage
    grange_slot_1: Surplus Sales
    grange_slot_2: Packing
    pp_grange_porters: Porters
"""


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "constructor.toml").write_text(CONFIG, encoding="utf-8")
    folder = tmp_path / pg.BLUEPRINT_ROOT_RELATIVE / "buildings"
    folder.mkdir(parents=True)
    (folder / "grange.yml").write_text(GRANGE, encoding="utf-8")
    (tmp_path / pg.MANIFEST_RELATIVE).write_text("enabled:\n  buildings/grange.yml: true\n", encoding="utf-8")
    return tmp_path


def _grange(repo: Path) -> dict:
    return yaml_io.safe_load((repo / pg.BLUEPRINT_ROOT_RELATIVE / "buildings/grange.yml").read_text(encoding="utf-8"))


def test_unflagged_blueprint_is_reported_and_flagged_by_the_rule(repo: Path) -> None:
    assert pg.structural_problems(repo) == {"grange.yml": ["no gate_method"]}
    check = pg.apply(repo, repo / "constructor.toml", PRICES, write=False)
    assert [p.gate for p in check.pending] == ["pp_grange_surplus_sales"]  # the dynamic slot wins
    pg.apply(repo, repo / "constructor.toml", PRICES)
    data = _grange(repo)
    assert data["gate_method"] == "pp_grange_surplus_sales"
    assert list(data)[:5] == ["version", "tag", "footprint", "labour", "gate_method"]
    assert pg.structural_problems(repo) == {}


def test_apply_moves_the_gate_slot_last_and_orders_the_rest_by_importance(repo: Path) -> None:
    before = _grange(repo)
    pg.apply(repo, repo / "constructor.toml", PRICES)
    after = _grange(repo)
    slots, _ = pg.body_slots(after["building"]["body"])
    # packing (0.5 x 3 victuals) above haulage (1.5 x 3), the dynamic gate slot last;
    # inside packing the output-less method first, then by output value
    assert [s.names() for s in slots] == [
        ["pp_grange_loose_stores", "pp_grange_pottery_jars", "pp_grange_tin_cans"],
        ["pp_grange_porters", "pp_grange_ox_carts"],  # equal output: file order
        ["pp_grange_surplus_sales"],
    ]
    assert [s["methods"] for s in after["building"]["production_method_slots"]] == [s.names() for s in slots]
    assert [s["name"] for s in after["building"]["production_method_slots"]] == ["slot_0", "slot_1", "slot_2"]
    entries = after["localization"]["entries"]
    assert (entries["grange_slot_0"], entries["grange_slot_1"], entries["grange_slot_2"]) == ("Packing", "Haulage", "Surplus Sales")
    body = after["building"]["body"]
    # comments travel with their slot and method; slot numbers in them follow
    assert "# slot 0: packing goods\nunique_production_methods" in body
    assert "# slot 2: surplus sales, the storage leg" in body
    assert "  # jars: the cheap packing\n  pp_grange_pottery_jars = {" in body
    # nothing but the order changed
    assert sorted(body.split("\n")) != sorted(before["building"]["body"].split("\n"))  # comments renumbered
    strip = lambda text: sorted(line for line in text.split("\n") if not line.strip().startswith("#"))  # noqa: E731
    assert strip(body) == strip(before["building"]["body"])
    assert body.endswith("modifier = {\n  local_monthly_food = -60.0\n}")


def test_apply_is_stable(repo: Path) -> None:
    pg.apply(repo, repo / "constructor.toml", PRICES)
    text = (repo / pg.BLUEPRINT_ROOT_RELATIVE / "buildings/grange.yml").read_text(encoding="utf-8")
    assert not pg.apply(repo, repo / "constructor.toml", PRICES, write=False).pending
    pg.apply(repo, repo / "constructor.toml", PRICES)
    assert (repo / pg.BLUEPRINT_ROOT_RELATIVE / "buildings/grange.yml").read_text(encoding="utf-8") == text


def test_an_explicit_flag_wins_over_the_rule(repo: Path) -> None:
    path = repo / pg.BLUEPRINT_ROOT_RELATIVE / "buildings/grange.yml"
    path.write_text(path.read_text(encoding="utf-8").replace("building:\n", "gate_method: pp_grange_porters\nbuilding:\n", 1), encoding="utf-8")
    pg.apply(repo, repo / "constructor.toml", PRICES)
    slots, _ = pg.body_slots(_grange(repo)["building"]["body"])
    assert slots[-1].names() == ["pp_grange_ox_carts", "pp_grange_porters"]
    assert slots[-2].names() == ["pp_grange_surplus_sales"]  # the dynamic slot stays as low as it can


def test_flag_problems() -> None:
    slots, _ = pg.body_slots(yaml_io.safe_load(GRANGE)["building"]["body"])
    assert pg.gate_problems(slots, "pp_grange_loose_stores", False)[0].endswith("has no output good, so it never sets the margin")
    assert "not in the last slot" in pg.gate_problems(slots, "pp_grange_ox_carts", False)[0]
    assert pg.gate_problems(slots, "pp_grange_tin_cans", False) == ["pp_grange_tin_cans is not listed last in its slot"]
    assert pg.gate_problems(slots, "pp_grange_pottery_jars", False) == []
    assert pg.gate_problems(slots, "pp_nothing", False) == ["gate_method pp_nothing is not a unique production method of the building"]


def test_provisioning_gate_is_provision_not_the_dummy() -> None:
    body = """unique_production_methods = {
    pp_x_base = { manual_labor = 0.012 produced = wheat output = 0.06 }
}
unique_production_methods = {
    pp_x_provision = { wheat = 0.08 produced = local_food output = 0.96 }
    pp_x_sell_surplus = { produced = province_food_sales output = 0.005 }
}"""
    slots, _ = pg.body_slots(body)
    config = pg.GateConfig()
    assert pg.suggest_gate(slots, config, {"wheat": 1.0, "local_food": 0.1, "province_food_sales": 5.0}) == "pp_x_provision"
    order = pg.plan_order(slots, "pp_x_provision", config, {"wheat": 1.0, "local_food": 0.1, "province_food_sales": 5.0})
    assert [s.names() for s in pg.ordered_slots(slots, order)][-1] == ["pp_x_sell_surplus", "pp_x_provision"]


# ---------------------------------------------------------------- the gate leg

LEG_CONFIG = """
[production_gate]
threshold = 1.2
dynamic_goods = ["province_food_sales"]
pinned_goods = ["local_food", "offset", "logistics"]
strategic_goods = ["stone"]

[blueprint_evaluation]
base_method_input_goods = ["manual_labor"]

[production_gate.leg]
margin = 1.0
value = 0.01
input = "offset"
slot_label = "Market"
method_name = "Market Sales"
method_desc = "A few hands carry a small share of the produce straight to market."
"""

FARM = """version: 2
tag: rye_farm
footprint: farm_land
labour:
  class: primary_medieval
gate_method: pp_rye_farm_provision
building:
  key: rye_farm
  mode: CREATE
  production_method_slots:
  - name: slot_0
    methods:
    - pp_rye_farm_base
  - name: slot_1
    methods:
    - pp_rye_farm_no_cultivation
    - pp_rye_farm_plough
  - name: slot_2
    methods:
    - pp_rye_farm_sell_surplus
    - pp_rye_farm_provision
  possible_production_methods: []
  body: |-
    pop_type = peasants
    unique_production_methods = {
        pp_rye_farm_base = {
            manual_labor = 0.012
            produced = wheat
            output = 0.06
        }
    }
    unique_production_methods = {
        pp_rye_farm_no_cultivation = {
            category = building_maintenance
        }
        pp_rye_farm_plough = {
            livestock = 0.037
            manual_labor = 0.022
            produced = wheat
            output = 0.15
        }
    }
    unique_production_methods = {
        pp_rye_farm_sell_surplus = {
            produced = province_food_sales
            output = 0.005
        }
        pp_rye_farm_provision = {
            wheat = 0.08
            produced = local_food
            output = 0.96
        }
    }

    modifier = {
        local_monthly_food = 1.5
    }
localization:
  entries:
    rye_farm: Rye Farm
    rye_farm_slot_0: Fields
    rye_farm_slot_1: Cultivation
    rye_farm_slot_2: Provisioning
evaluation:
  allow_rules:
    profit_percent: kept
"""

LEG_PRICES = {**PRICES, "local_food": 0.1, "province_food_sales": 5.0}


@pytest.fixture
def leg_repo(tmp_path: Path) -> Path:
    (tmp_path / "constructor.toml").write_text(LEG_CONFIG, encoding="utf-8")
    folder = tmp_path / pg.BLUEPRINT_ROOT_RELATIVE / "buildings"
    folder.mkdir(parents=True)
    (folder / "rye_farm.yml").write_text(FARM, encoding="utf-8")
    (folder / "grange.yml").write_text(GRANGE.replace("building:\n", "gate_method: pp_grange_surplus_sales\nbuilding:\n", 1), encoding="utf-8")
    (tmp_path / pg.MANIFEST_RELATIVE).write_text(
        "enabled:\n  buildings/rye_farm.yml: true\n  buildings/grange.yml: true\n", encoding="utf-8"
    )
    return tmp_path


def _load(repo: Path, name: str) -> dict:
    return yaml_io.safe_load((repo / pg.BLUEPRINT_ROOT_RELATIVE / "buildings" / f"{name}.yml").read_text(encoding="utf-8"))


def test_a_market_good_building_gets_a_gate_leg_as_its_last_one_method_slot(leg_repo: Path) -> None:
    pg.apply(leg_repo, leg_repo / "constructor.toml", LEG_PRICES)
    data = _load(leg_repo, "rye_farm")
    slots, _ = pg.body_slots(data["building"]["body"])
    leg = slots[-1].methods
    assert data["gate_method"] == "pp_rye_farm_market_sales"
    assert [m.name for m in leg] == ["pp_rye_farm_market_sales"]  # one method: the AI always reads it
    assert leg[0].produced == "wheat" and leg[0].inputs == {"offset": 0.01} and leg[0].output == 0.01
    assert leg[0].margin(LEG_PRICES) == pytest.approx(1.0)
    # the Provision gate that bought the crop is gone; the other slots keep their importance order
    assert [s.names() for s in slots[:-1]] == [
        ["pp_rye_farm_base"],
        ["pp_rye_farm_no_cultivation", "pp_rye_farm_plough"],
        ["pp_rye_farm_sell_surplus", "pp_rye_farm_provision"],
    ]
    assert data["building"]["production_method_slots"][-1] == {"name": "slot_3", "methods": ["pp_rye_farm_market_sales"]}
    entries = data["localization"]["entries"]
    assert entries["rye_farm_slot_3"] == "Market" and entries["pp_rye_farm_market_sales"] == "Market Sales"
    assert entries["rye_farm_slot_2"] == "Provisioning"
    assert data["evaluation"]["allow_rules"] == {"profit_percent": "kept"}
    assert data["evaluation"]["production_methods"]["pp_rye_farm_market_sales"]["allow_rules"] == pg.LEG_ALLOW_RULES
    assert data["building"]["body"].rstrip().endswith("modifier = {\n    local_monthly_food = 1.5\n}")
    # stable, and a changed price only rewrites the leg's amounts
    assert not pg.apply(leg_repo, leg_repo / "constructor.toml", LEG_PRICES, write=False).pending
    pg.apply(leg_repo, leg_repo / "constructor.toml", {**LEG_PRICES, "wheat": 2.0})
    slots, _ = pg.body_slots(_load(leg_repo, "rye_farm")["building"]["body"])
    assert len(slots) == 4 and slots[-1].methods[0].output == 0.005 and slots[-1].methods[0].inputs == {"offset": 0.01}


def test_a_storage_leg_gate_keeps_its_own_gate(leg_repo: Path) -> None:
    pg.apply(leg_repo, leg_repo / "constructor.toml", LEG_PRICES)
    data = _load(leg_repo, "grange")
    assert data["gate_method"] == "pp_grange_surplus_sales"
    assert not any(pg.is_leg(m.name) for s in pg.body_slots(data["building"]["body"])[0] for m in s.methods)


def test_main_good_is_the_base_good_not_a_dearer_side_good() -> None:
    body = """unique_production_methods = {
    pp_x_base = { manual_labor = 0.012 produced = olives output = 0.06 }
}
unique_production_methods = {
    pp_x_no_hives = { category = building_maintenance }
    pp_x_hives = { manual_labor = 0.01 produced = beeswax output = 0.05 }
}"""
    slots, _ = pg.body_slots(body)
    config = pg.GateConfig(leg=pg.LegConfig())
    assert pg.main_good(slots, config, {"olives": 1.0, "beeswax": 5.0, "manual_labor": 1.0}) == "olives"
    leg = pg.plan_leg("x", slots, None, config, {"olives": 1.0, "beeswax": 5.0, "manual_labor": 1.0, "offset": 1.0})
    assert leg is not None and leg.good == "olives"
    assert pg.plan_leg("x", slots, None, pg.GateConfig(leg=pg.LegConfig(), strategic_goods=frozenset({"olives"})), {"olives": 1.0, "offset": 1.0}) is None


def test_the_gate_leg_is_a_labour_free_technical_method() -> None:
    from prosper_or_perish_constructor import production_labour

    assert pg.is_leg("pp_wheat_farm_market_sales") and not pg.is_leg("pp_wheat_farm_sell_surplus")
    assert production_labour.is_leg is pg.is_leg


# ---------------------------------------------------------------- the repo


def test_every_production_blueprint_names_a_gate_that_decides_the_margin() -> None:
    """Every enabled blueprint with a producing unique method has gate_method; the method has an output good, sits in
    the last unique slot and is listed last in it."""
    assert pg.structural_problems(ROOT) == {}


def test_every_production_blueprint_is_in_gate_order() -> None:
    result = pg.apply(ROOT, ROOT / "constructor.toml", write=False)
    assert not result.problems
    assert [p.blueprint.name for p in result.pending] == [], "run uv run ppc gate apply"


def test_every_market_good_building_gates_on_its_leg_and_no_gate_buys_its_main_good() -> None:
    """Engine rule (AI rulebook 2.4i): the last method the AI reads decides the margin check, and a one-method slot is
    always read. So every building with a market main good ends in its gate leg; no remaining gate buys its main good,
    except the crop farms' Provision (farm v3): it takes only a token of the crop, so its margin stays several times
    the threshold at any crop price, and the farm's price response is its ai_construct_weight."""
    from prosper_or_perish_constructor import provisioning

    config = pg.load_config(ROOT / "constructor.toml")
    prices = pg.load_prices(ROOT, ROOT / "constructor.toml", config)
    result = pg.apply(ROOT, ROOT / "constructor.toml", prices, write=False)
    legs = 0
    for plan in result.plans:
        good = pg.main_good(pg.without_legs(plan.slots), config, prices)
        if plan.leg is not None:
            legs += 1
            assert plan.gate == plan.leg.name and plan.slots[-1].methods == (plan.leg.method(),), plan.building
            assert plan.leg.method().margin(prices) == pytest.approx(config.leg.margin, rel=0.02), plan.building
        else:
            where = pg.locate(plan.slots, plan.gate)
            gate = plan.slots[where[0]].methods[where[1]]
            if plan.building in provisioning.CROP_FARM_GOODS:
                assert plan.gate == provisioning.provision_method(plan.building), plan.building
                assert gate.margin(prices) >= 4 * config.threshold, plan.building  # open up to ~4x the crop price
                continue
            assert not (good and gate.inputs.get(good, 0) > 0), plan.building
    assert legs > 150
    by_name = {p.building: p for p in result.plans}
    assert by_name["wheat_farm"].gate == "pp_wheat_farm_provision" and by_name["wheat_farm"].leg is None
    assert by_name["fishing_village"].gate == "pp_fishing_village_market_sales"
    assert by_name["grange"].gate == "pp_grange_surplus_sales" and by_name["tavern"].leg is None
