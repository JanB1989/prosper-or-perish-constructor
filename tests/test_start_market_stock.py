"""Start market stock: the formula, the plan and the generated on_action (src/prosper_or_perish_constructor/start_market_stock.py)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import re

import pytest

from prosper_or_perish_constructor import start_market_stock as sms
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
MOD = ROOT / "mod" / "pp"
CONFIG = sms.Config(existing_months=2.0, min_amount=1.0, not_goods=frozenset({"offset"}))


@pytest.mark.parametrize("x", [0.25, 0.3, 0.38, 0.5, 0.7, 0.9])
def test_the_stock_puts_the_target_at_the_settled_price(x: float) -> None:
    """Flows in balance, no offsets: months(x) of flow in stock give exactly x."""
    flow = 1_000_000.0  # the .5 offsets vanish against this
    assert sms.target_price(flow, flow, sms.stock_months(x) * flow) == pytest.approx(x, abs=1e-3)


def test_a_dear_good_needs_no_stock() -> None:
    assert sms.stock_months(1.0) == pytest.approx(0.0)
    assert sms.stock_months(1.4) < 0


def test_plan_uses_the_larger_flow_and_the_existing_stock() -> None:
    flows = sms.Flows(pop=Counter({("a", "wheat"): 10.0}), rgo=Counter({("a", "wheat"): 30.0, ("b", "wheat"): 1.0}), people=Counter({"a": 5.0, "b": 5.0}))
    table = {"wheat": sms.Row(settled_price=0.5, pop_factor=2.0, rgo_factor=1.0)}
    months = sms.stock_months(0.5) - CONFIG.existing_months
    stock = sms.plan(flows, table, CONFIG)
    assert stock[("a", "wheat")] == pytest.approx(30.0 * months, abs=0.1)   # make 30 beats use 20
    assert stock[("b", "wheat")] == pytest.approx(1.0 * months, abs=0.1)


def test_plan_skips_small_amounts_dear_goods_and_dummy_goods() -> None:
    flows = sms.Flows(rgo=Counter({("a", "wheat"): 0.01, ("a", "gems"): 50.0, ("a", "offset"): 50.0}), people=Counter({"a": 1.0}))
    table = {"wheat": sms.Row(0.5, rgo_factor=1.0), "gems": sms.Row(1.3, rgo_factor=1.0), "offset": sms.Row(0.5, rgo_factor=1.0)}
    assert sms.plan(flows, table, CONFIG) == {}


def test_stock_stays_below_the_ceiling() -> None:
    flows = sms.Flows(rgo=Counter({("a", "clay"): 1000.0}), people=Counter({"a": 1.0}), ceiling={"a": 2000.0})
    stock = sms.plan(flows, {"clay": sms.Row(0.25, rgo_factor=1.0)}, sms.Config(existing_months=0.0, min_amount=1.0, not_goods=frozenset()))
    assert stock[("a", "clay")] == pytest.approx(sms.CEILING_SHARE * 2000.0)


def test_nothing_is_added_to_a_market_already_over_the_ceiling_share() -> None:
    flows = sms.Flows(rgo=Counter({("a", "clay"): 1000.0}), people=Counter({"a": 1.0}), ceiling={"a": 100.0})
    assert sms.plan(flows, {"clay": sms.Row(0.25, rgo_factor=1.0)}, CONFIG) == {}


def test_ceiling_numbers_match_the_mod() -> None:
    text = (MOD / "main_menu/common/static_modifiers/pp_location_modifier_adjustments.txt").read_text(encoding="utf-8-sig")
    assert f"maximum_stockpile_capacity = {sms.CEILING_PER_DEVELOPMENT:g} " in text
    assert "TRY_INJECT:market_center" in text and "maximum_stockpile_capacity = 250 " in text


def test_rest_goes_by_people() -> None:
    flows = sms.Flows(people=Counter({"a": 10.0}))
    stock = sms.plan(flows, {"tea": sms.Row(0.5, rest_per_k=2.0)}, CONFIG)
    assert stock[("a", "tea")] == pytest.approx(20.0 * (sms.stock_months(0.5) - 2.0), abs=0.1)


def test_render_scopes_each_market_once() -> None:
    text = sms.render({("kyoto", "wheat"): 12.5, ("kyoto", "lumber"): 3.0, ("akita", "wheat"): 1.0})
    assert text.count("location:kyoto.market = {") == 1
    assert "add_goods_supply = { goods = goods:wheat amount = 12.5 }" in text
    assert text.count("{") == text.count("}")


def test_it_runs_after_the_first_days_and_before_the_first_price_step() -> None:
    """Prices step on the 1st; a new game starts on 1 April."""
    assert 1 <= sms.DELAY_DAYS <= 29
    hook = sms.render({("kyoto", "wheat"): 1.0}).split(f"{sms.ON_ACTION} = {{")[0]
    assert re.search(rf"delay = \{{ days = {sms.DELAY_DAYS} \}}\s+{sms.ON_ACTION}", hook)


def test_table_is_sane() -> None:
    table = sms.load_table(ROOT)
    assert len(table) > 60
    for good, row in table.items():
        assert 0.2 <= row.settled_price <= 3, good
        assert min(row.pop_factor, row.input_factor, row.rgo_factor, row.output_factor, row.rest_per_k) >= 0, good


def test_a_new_table_does_not_rerun_the_start_setup() -> None:
    from prosper_or_perish_constructor.cli import WORLDBUILDER_CODE_AND_DATA

    assert not any(sms.TABLE.is_relative_to(stage_input) for stage_input in WORLDBUILDER_CODE_AND_DATA)


def test_generated_file_matches_the_build() -> None:
    result = sms.apply(ROOT, PROJECT, MOD, vanilla_root(ROOT, PROJECT), write=False)
    assert not result.changed, "run ppc start-stock apply"
    assert not result.missing_goods, "run ppc start-stock calibrate"
    assert result.markets > 100
    assert result.lines > 3000


def test_every_market_and_good_exists() -> None:
    text = (MOD / sms.OUTPUT).read_text(encoding="utf-8-sig")
    markets = set(re.findall(r"location:(\w+)\.market", text))
    vanilla = (vanilla_root(ROOT, PROJECT) / "game/main_menu/setup/1337/03_markets.txt").read_text(encoding="utf-8-sig")
    assert markets <= set(re.findall(r"add_market = (\w+)", vanilla))
    goods = set(re.findall(r"goods:(\w+)", text))
    assert goods <= set(sms.load_table(ROOT))
    assert not goods & sms.load_project_config(PROJECT).not_goods
