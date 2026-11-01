"""[stockpile_prices] -> in_game/common/goods/zz_pp_goods_stockpile_prices.txt (src/prosper_or_perish_constructor/stockpile_prices.py)."""

from __future__ import annotations

from pathlib import Path
import tomllib

import pytest

from prosper_or_perish_constructor import stockpile_prices as sp
from prosper_or_perish_constructor.staple_foods import staple_foods

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"


def test_goods_file_is_in_step_with_the_config() -> None:
    goods, changed = sp.apply(ROOT, PROJECT, write=False)
    assert not changed, "run ppc stockpile apply"
    assert goods > 70


def test_render_raises_prices_and_multiplies_pop_demand() -> None:
    raw = {"stockpile_prices": {"base_price_mult": 1.5, "keep_base_price": ["offset"], "price_factor": {"fur": 1.2}, "pop_demand": {"tea": 0.5}}}
    lines = sp.render(raw, {"offset": 5.0, "fur": 2.0, "tea": 4.0, "iron": 3.5}).splitlines()
    assert "TRY_INJECT:fur = { default_market_price = 3.6 } # 2 x 1.2" in lines
    assert "TRY_INJECT:iron = { default_market_price = 5.25 } # 3.5" in lines
    assert "TRY_INJECT:tea = { default_market_price = 6 demand_multiply = { all = 0.5 } } # 4" in lines
    assert not any(line.startswith("TRY_INJECT:offset") for line in lines)


@pytest.mark.parametrize("table", ["price_factor", "pop_demand"])
def test_a_config_entry_without_a_raised_good_is_an_error(table: str) -> None:
    raw = {"stockpile_prices": {"base_price_mult": 1.5, "keep_base_price": ["offset"], table: {"offset": 0.5}}}
    with pytest.raises(ValueError, match=table):
        sp.render(raw, {"offset": 5.0, "iron": 3.5})


def test_pop_demand_factors_cut_and_leave_staple_foods_alone() -> None:
    raw = tomllib.loads(PROJECT.read_text(encoding="utf-8-sig"))
    factors = raw["stockpile_prices"]["pop_demand"]
    assert factors and all(0 < v < 1 for v in factors.values())
    assert not set(factors) & set(staple_foods())
